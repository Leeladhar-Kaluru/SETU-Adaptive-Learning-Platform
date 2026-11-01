import copy
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.curriculum import Subject
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.learning import LearningPath, PathLesson, LessonVersion
from app.services.generation_queue import enqueue_lesson_generation, requeue_failed_lessons
from app.services.lesson_generator import lesson_generator_service
from app.services.pipeline_runner import notify_pipeline
from app.services.text_sanitize import sanitize_tree

router = APIRouter()


def _redact_answer_keys(package: dict) -> dict:
    sanitized = copy.deepcopy(package)
    for section in ("practice", "checkpointTest"):
        for question in sanitized.get(section, []) or []:
            question.pop("answerKey", None)
    return sanitized


def _document_page_payload(db: Session, doc: Document) -> list[dict]:
    """Return page-shaped text for outline building.

    Documents ingested before page-level extraction existed only have chunks.
    Their chunk text is still real extracted source, so group it by source page
    instead of rejecting the document.
    """
    pages = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == doc.id)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )
    if pages:
        return [{"page_number": page.page_number, "text": page.extracted_text} for page in pages]

    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == doc.id,
            DocumentChunk.embedding.isnot(None),
        )
        .order_by(DocumentChunk.page_start.asc(), DocumentChunk.chunk_index.asc())
        .all()
    )
    grouped: dict[int, list[str]] = {}
    for chunk in chunks:
        text = (chunk.text or "").strip()
        if not text:
            continue
        page_number = int(chunk.page_start or chunk.chunk_index + 1)
        grouped.setdefault(page_number, []).append(text)
    return [
        {"page_number": page_number, "text": "\n".join(grouped[page_number])}
        for page_number in sorted(grouped)
    ]


class OutlineRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_id: uuid.UUID = Field(alias="documentId")
    grade: int = Field(ge=6, le=10)
    subject_id: str = Field(alias="subjectId", min_length=3)
    language_tag: Optional[str] = None

class CreatePathRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_id: uuid.UUID = Field(alias="documentId")
    grade: int = Field(ge=6, le=10)
    subject_id: str = Field(alias="subjectId", min_length=3)
    title: Optional[str] = None
    language_tag: Optional[str] = None
    goal: str = "concept_understanding"

@router.post("/outline")
async def generate_path_outline(
    req: OutlineRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == req.document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    subject = db.query(Subject).filter(
        Subject.id == req.subject_id, Subject.active == True
    ).first()
    if not subject:
        raise HTTPException(status_code=422, detail="Choose a subject from the curriculum catalogue.")

    pages = _document_page_payload(db, doc)
    p_data = pages

    outline = await lesson_generator_service.generate_outline(
        document_title=doc.original_filename,
        extracted_pages=p_data,
        grade=req.grade,
        subject=req.subject_id,
    )
    return outline

@router.post("")
@router.post("/create")
def create_learning_path(
    req: CreatePathRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Creates learning path from document outline or curriculum unit.
    Generates the first validated lesson with priority, enqueuing subsequent lessons
    on the durable PostgreSQL background queue.
    """
    doc = db.query(Document).filter(Document.id == req.document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status in ("failed", "needs_ocr"):
        raise HTTPException(status_code=409, detail=doc.safe_error_message or "Document processing did not finish.")
    if doc.status not in ("awaiting_review", "ready"):
        raise HTTPException(
            status_code=409,
            detail=f"Document is not ready for a learning path (status: {doc.status}).",
        )

    subject = db.query(Subject).filter(
        Subject.id == req.subject_id, Subject.active == True
    ).first()
    if not subject:
        raise HTTPException(status_code=422, detail="Choose a subject from the curriculum catalogue.")

    indexed_chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == doc.id,
        DocumentChunk.embedding.isnot(None),
        DocumentChunk.embedding_dimension == settings.EMBEDDING_DIMENSION,
    ).count()
    if indexed_chunks == 0:
        raise HTTPException(
            status_code=409,
            detail="This document has no indexed text yet. Wait for processing to finish or retry it.",
        )

    existing = db.query(LearningPath).filter(
        LearningPath.owner_id == owner_id,
        LearningPath.document_id == doc.id,
        LearningPath.grade == req.grade,
        LearningPath.subject_id == req.subject_id,
        LearningPath.status.in_(["active", "generating"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "path_exists", "pathId": str(existing.id), "message": "A learning path already exists for this document and class."},
        )

    pages = _document_page_payload(db, doc)
    page_payload = pages
    try:
        outline_data = lesson_generator_service.build_outline_from_pages(
            document_title=doc.original_filename,
            extracted_pages=page_payload,
            grade=req.grade,
            subject=req.subject_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path = LearningPath(
        owner_id=owner_id,
        document_id=doc.id,
        grade=req.grade,
        subject_id=req.subject_id,
        language_tag=req.language_tag or doc.language_tag,
        goal=req.goal,
        status="generating",
        outline_json=outline_data,
        rationale="Outline built from extracted headings and page ranges",
    )
    db.add(path)
    db.flush()

    chapters = outline_data.get("chapters", [])
    seq = 1
    created_lessons = []
    for chapter in chapters:
        lesson_title = (
            chapter.get("title")
            or chapter.get("chapterTitle")
            or chapter.get("name")
            or chapter.get("heading")
            or f"Lesson {seq}"
        )
        plesson = PathLesson(
            path_id=path.id,
            lesson_key=f"lesson_{seq}",
            title=lesson_title,
            sequence=seq,
            status="queued",
        )
        db.add(plesson)
        db.flush()
        created_lessons.append(plesson)
        seq += 1

    if not created_lessons:
        db.rollback()
        raise HTTPException(status_code=400, detail="No sections could be read from this document.")

    first_lesson = created_lessons[0]
    enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=created_lessons)
    notify_pipeline()

    return {
        "pathId": str(path.id),
        "id": str(path.id),
        "firstLessonId": str(first_lesson.id),
        "lessonKey": first_lesson.lesson_key,
        "totalLessons": len(created_lessons),
        "title": outline_data.get("title", doc.original_filename),
        "status": path.status,
    }

@router.get("")
def list_learning_paths(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    paths = (
        db.query(LearningPath)
        .filter(
            LearningPath.owner_id == owner_id,
            LearningPath.status != "archived",
        )
        .order_by(LearningPath.created_at.desc())
        .all()
    )
    results = []
    for p in paths:
        lessons = db.query(PathLesson).filter(PathLesson.path_id == p.id).order_by(PathLesson.sequence.asc()).all()
        ready_count = sum(1 for l in lessons if l.status == "ready")
        first_l = lessons[0] if lessons else None
        results.append({
            "id": str(p.id),
            "documentId": str(p.document_id) if p.document_id else None,
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

@router.post("/{path_id}/requeue-failed")
def requeue_failed_path_lessons(
    path_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    path = db.query(LearningPath).filter(LearningPath.id == path_id, LearningPath.owner_id == owner_id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Learning path not found")
    requeued = requeue_failed_lessons(db, owner_id=owner_id, path=path)
    if requeued > 0:
        notify_pipeline()
    return {
        "pathId": str(path.id),
        "requeuedJobs": requeued,
    }

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

    package = _redact_answer_keys(dict(version.lesson_package_json))
    # Existing packages were generated before the plain-text policy; sanitize
    # LaTeX/markdown artifacts at read time so stored lessons render cleanly.
    package = sanitize_tree(package)
    package["lessonVersionId"] = str(version.id)
    return package
