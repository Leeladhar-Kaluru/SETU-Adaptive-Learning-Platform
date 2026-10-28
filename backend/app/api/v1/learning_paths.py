import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.documents import Document, DocumentPage, DocumentChunk
from app.models.learning import LearningPath, PathLesson, LessonVersion
from app.models.jobs import GenerationJob
from app.services.lesson_generator import lesson_generator_service

router = APIRouter()

class OutlineRequest(BaseModel):
    document_id: uuid.UUID
    grade: Optional[int] = 9
    subject_id: Optional[str] = "SCIENCE"

class CreatePathRequest(BaseModel):
    document_id: Optional[uuid.UUID] = None
    grade: int = 9
    subject_id: str = "SCIENCE"
    language_tag: str = "en-IN"
    goal: str = "concept_understanding"
    outline: Dict[str, Any]

@router.post("/outline")
async def generate_path_outline(
    req: OutlineRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == req.document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()
    p_data = [{"page_number": p.page_number, "text": p.extracted_text} for p in pages]

    outline = await lesson_generator_service.generate_outline(
        document_title=doc.original_filename,
        extracted_pages=p_data,
        grade=req.grade,
        subject=req.subject_id
    )
    return outline

@router.post("")
async def create_learning_path(
    req: CreatePathRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Creates learning path, eagerly generates and validates the first 2-3 lessons immediately,
    and enqueues subsequent lessons onto the durable PostgreSQL background queue.
    """
    path = LearningPath(
        owner_id=owner_id,
        document_id=req.document_id,
        grade=req.grade,
        subject_id=req.subject_id,
        language_tag=req.language_tag,
        goal=req.goal,
        status="active",
        outline_json=req.outline,
        rationale="Source-grounded curriculum path"
    )
    db.add(path)
    db.commit()
    db.refresh(path)

    # Collect chunks for immediate generation
    chunks = []
    if req.document_id:
        c_rows = db.query(DocumentChunk).filter(DocumentChunk.document_id == req.document_id).limit(5).all()
        chunks = [
            {
                "citationId": f"cite_{str(c.id)[:8]}",
                "chunkId": str(c.id),
                "documentVersionId": str(c.document_id),
                "pageStart": c.page_start,
                "pageEnd": c.page_end,
                "headingPath": c.heading_path or [],
                "text": c.text
            }
            for c in c_rows
        ]

    # Create lessons from outline chapters
    chapters = req.outline.get("chapters", [])
    seq = 1
    lessons_to_generate_eagerly = []

    for ch_idx, ch in enumerate(chapters):
        ch_title = ch.get("chapterTitle", f"Unit {ch_idx + 1}")
        concepts = ch.get("concepts", [f"{ch_title} Part 1", f"{ch_title} Part 2"])
        for c_idx, c_title in enumerate(concepts):
            lesson_key = f"lesson_{seq}"
            plesson = PathLesson(
                path_id=path.id,
                lesson_key=lesson_key,
                title=f"{c_title}",
                sequence=seq,
                status="queued"
            )
            db.add(plesson)
            db.commit()
            db.refresh(plesson)

            if seq <= 3:
                lessons_to_generate_eagerly.append(plesson)
            else:
                # Enqueue onto durable background queue
                job = GenerationJob(
                    job_type="generate_lesson",
                    owner_id=owner_id,
                    path_id=path.id,
                    lesson_id=plesson.id,
                    priority=10 + seq,
                    status="queued",
                    idempotency_key=f"gen_{path.id}_{plesson.id}_v1"
                )
                db.add(job)
            seq += 1

    db.commit()

    # Eagerly generate lessons 1, 2, 3
    for plesson in lessons_to_generate_eagerly:
        plesson.status = "generating"
        db.commit()

        package = await lesson_generator_service.generate_lesson_package(
            lesson_id=plesson.lesson_key,
            lesson_title=plesson.title,
            path_id=str(path.id),
            grade=path.grade,
            subject=path.subject_id,
            evidence_chunks=chunks
        )

        validation_status = package.get("validation", {}).get("status", "draft")
        version = LessonVersion(
            path_lesson_id=plesson.id,
            version_number=1,
            lesson_package_json=package,
            validation_status=validation_status
        )
        db.add(version)
        plesson.status = "ready" if validation_status == "ready" else "failed"
        db.commit()

    return {
        "id": str(path.id),
        "grade": path.grade,
        "subjectId": path.subject_id,
        "goal": path.goal,
        "totalLessons": seq - 1,
        "eagerlyReadyLessons": len(lessons_to_generate_eagerly),
        "status": path.status
    }

@router.get("/{path_id}")
def get_learning_path(
    path_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    path = db.query(LearningPath).filter(LearningPath.id == path_id, LearningPath.owner_id == owner_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    lessons = db.query(PathLesson).filter(PathLesson.path_id == path.id).order_by(PathLesson.sequence.asc()).all()

    return {
        "id": str(path.id),
        "documentId": str(path.document_id) if path.document_id else None,
        "grade": path.grade,
        "subjectId": path.subject_id,
        "goal": path.goal,
        "outline": path.outline_json,
        "lessons": [
            {
                "id": str(l.id),
                "lessonKey": l.lesson_key,
                "title": l.title,
                "sequence": l.sequence,
                "status": l.status
            }
            for l in lessons
        ]
    }

@router.get("/{path_id}/lessons/{lesson_key}")
def get_lesson_package(
    path_id: uuid.UUID,
    lesson_key: str,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    path = db.query(LearningPath).filter(LearningPath.id == path_id, LearningPath.owner_id == owner_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Learning path not found")

    lesson = db.query(PathLesson).filter(PathLesson.path_id == path.id, PathLesson.lesson_key == lesson_key).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    version = db.query(LessonVersion).filter(LessonVersion.path_lesson_id == lesson.id).order_by(LessonVersion.version_number.desc()).first()
    if not version:
        raise HTTPException(status_code=404, detail="Lesson package not generated yet")

    return version.lesson_package_json
