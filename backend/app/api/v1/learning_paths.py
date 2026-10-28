import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.documents import Document, DocumentPage
from app.models.learning import LearningPath, PathLesson, LessonVersion
from app.models.jobs import GenerationJob
from app.services.lesson_generator import lesson_generator_service

router = APIRouter()

class OutlineRequest(BaseModel):
    document_id: Optional[uuid.UUID] = None
    documentVersionId: Optional[uuid.UUID] = None
    grade: Optional[int] = 9
    subject_id: Optional[str] = "subject-science"

class CreatePathRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: Optional[uuid.UUID] = Field(default=None, alias="documentId")
    documentVersionId: Optional[uuid.UUID] = None
    title: Optional[str] = None
    grade: Optional[int] = None
    subject_id: Optional[str] = None
    subject: Optional[str] = None
    language_tag: str = "en-IN"
    goal: str = "concept_understanding"
    outline: Optional[Dict[str, Any]] = None

@router.post("/outline")
async def generate_path_outline(
    req: OutlineRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc_id = req.document_id or req.documentVersionId
    if not doc_id:
        raise HTTPException(status_code=400, detail="document_id or documentVersionId is required")

    doc = db.query(Document).filter(Document.id == doc_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()
    p_data = [{"page_number": p.page_number, "text": p.extracted_text} for p in pages]

    outline = await lesson_generator_service.generate_outline(
        document_title=doc.original_filename,
        extracted_pages=p_data,
        grade=req.grade or 9,
        subject=req.subject_id or "SCIENCE"
    )
    return outline

@router.post("")
@router.post("/create")
async def create_learning_path(
    req: CreatePathRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Creates learning path from document outline or curriculum unit.
    Generates the first validated lesson with priority, enqueuing subsequent lessons
    on the durable PostgreSQL background queue.
    """
    doc_id = req.document_id or req.documentVersionId
    if not doc_id:
        raise HTTPException(status_code=400, detail="documentId is required. Upload a document before building a path.")

    doc = db.query(Document).filter(Document.id == doc_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status in ("failed", "needs_ocr"):
        raise HTTPException(status_code=409, detail=doc.safe_error_message or "Document processing did not finish.")
    if doc.status not in ("awaiting_review", "ready"):
        raise HTTPException(
            status_code=409,
            detail=f"Document is not ready for a learning path (status: {doc.status}).",
        )

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()
    page_payload = [{"page_number": page.page_number, "text": page.extracted_text} for page in pages]
    subject_val = doc.subject_id or req.subject_id or req.subject or "subject-general"
    grade_val = doc.grade or req.grade or 0
    try:
        outline_data = lesson_generator_service.build_outline_from_pages(
            document_title=doc.original_filename,
            extracted_pages=page_payload,
            grade=grade_val,
            subject=subject_val,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path = LearningPath(
        owner_id=owner_id,
        document_id=doc.id,
        grade=grade_val,
        subject_id=subject_val,
        language_tag=doc.language_tag or req.language_tag,
        goal=req.goal,
        status="generating",
        outline_json=outline_data,
        rationale="Outline built from extracted headings and page ranges",
    )
    db.add(path)
    db.flush()

    chapters = outline_data.get("chapters", [])
    seq = 1
    first_lesson = None
    for chapter in chapters:
        lesson_title = chapter.get("chapterTitle") or f"Section {seq}"
        plesson = PathLesson(
            path_id=path.id,
            lesson_key=f"lesson_{seq}",
            title=lesson_title,
            sequence=seq,
            status="queued",
        )
        db.add(plesson)
        db.flush()
        if first_lesson is None:
            first_lesson = plesson
        priority = seq if seq <= 2 else 20 + seq
        db.add(
            GenerationJob(
                job_type="generate_lesson",
                owner_id=owner_id,
                path_id=path.id,
                lesson_id=plesson.id,
                priority=priority,
                status="queued",
                idempotency_key=f"gen_{path.id}_{plesson.id}_v1",
            )
        )
        seq += 1

    if not first_lesson:
        db.rollback()
        raise HTTPException(status_code=400, detail="No sections could be read from this document.")

    db.commit()

    return {
        "pathId": str(path.id),
        "id": str(path.id),
        "firstLessonId": str(first_lesson.id),
        "lessonKey": first_lesson.lesson_key,
        "totalLessons": seq - 1,
        "title": outline_data.get("title", doc.original_filename),
        "status": path.status,
    }

@router.get("")
def list_learning_paths(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    paths = db.query(LearningPath).filter(LearningPath.owner_id == owner_id).order_by(LearningPath.created_at.desc()).all()
    results = []
    for p in paths:
        lessons = db.query(PathLesson).filter(PathLesson.path_id == p.id).order_by(PathLesson.sequence.asc()).all()
        ready_count = sum(1 for l in lessons if l.status == "ready")
        first_l = lessons[0] if lessons else None
        results.append({
            "id": str(p.id),
            "title": p.outline_json.get("title", f"Class {p.grade} {p.subject_id}"),
            "grade": p.grade,
            "subjectId": p.subject_id,
            "status": p.status,
            "totalLessons": len(lessons),
            "readyLessons": ready_count,
            "progressPercent": int(round(100 * ready_count / len(lessons))) if lessons else 0,
            "firstLessonId": str(first_l.id) if first_l else None,
            "lessons": [
                {
                    "id": str(lesson.id),
                    "title": lesson.title,
                    "status": lesson.status,
                    "sequence": lesson.sequence,
                }
                for lesson in lessons
            ],
            "createdAt": p.created_at.isoformat()
        })
    return results

@router.get("/{path_id}")
def get_learning_path_detail(
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
        "title": path.outline_json.get("title", f"Class {path.grade} {path.subject_id}"),
        "grade": path.grade,
        "subjectId": path.subject_id,
        "goal": path.goal,
        "outline": path.outline_json,
        "status": path.status,
        "lessons": [
            {
                "id": str(l.id),
                "sequence": l.sequence,
                "lessonKey": l.lesson_key,
                "title": l.title,
                "status": l.status
            }
            for l in lessons
        ]
    }

@router.get("/lessons/{lesson_id}")
def get_lesson_package(
    lesson_id: str,
    pathId: Optional[str] = None,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Returns full lesson package JSON. Supports lookup by UUID or lesson_key.
    Only the learning path owner can read the lesson; any other caller gets 404
    so the response never confirms that the lesson exists.
    """
    lesson = None
    try:
        l_uuid = uuid.UUID(lesson_id)
        lesson = (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(PathLesson.id == l_uuid, LearningPath.owner_id == owner_id)
            .first()
        )
    except Exception:
        # Lookup by lesson_key
        q = (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(PathLesson.lesson_key == lesson_id, LearningPath.owner_id == owner_id)
        )
        if pathId:
            try:
                p_uuid = uuid.UUID(pathId)
                q = q.filter(PathLesson.path_id == p_uuid)
            except Exception:
                pass
        lesson = q.first()

    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    version = db.query(LessonVersion).filter(LessonVersion.path_lesson_id == lesson.id).order_by(LessonVersion.version_number.desc()).first()
    if not version or not version.lesson_package_json:
        raise HTTPException(status_code=404, detail="Lesson package content not ready")

    package = dict(version.lesson_package_json)
    package["lessonVersionId"] = str(version.id)
    return package
