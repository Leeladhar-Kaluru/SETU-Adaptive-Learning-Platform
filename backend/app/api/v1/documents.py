import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.storage import storage_service
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.services.lesson_generator import lesson_generator_service

router = APIRouter()

READY_FOR_REVIEW = {"awaiting_review", "ready"}


def validate_file_signature(ext: str, content: bytes) -> None:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file is empty.")
    if ext == "pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This file does not look like a PDF.")
    if ext in ("docx", "pptx") and not content.startswith(b"PK"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This file does not look like an Office document.",
        )
    if ext == "png" and not content.startswith(b"\x89PNG"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This file does not look like a PNG.")
    if ext in ("jpg", "jpeg") and not content.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This file does not look like a JPEG.")
    if ext in ("txt", "md") and b"\x00" in content[:1024]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This text file looks binary.")


def _document_payload(doc: Document, chunk_count: int = 0) -> dict:
    return {
        "id": str(doc.id),
        "documentId": str(doc.id),
        "versionId": str(doc.id),
        "title": doc.original_filename.rsplit(".", 1)[0].replace("_", " "),
        "filename": doc.original_filename,
        "sizeBytes": doc.size_bytes,
        "sizeMb": round((doc.size_bytes or 0) / (1024 * 1024), 2),
        "pageCount": doc.page_count,
        "chunkCount": chunk_count,
        "status": doc.status,
        "grade": doc.grade,
        "subjectId": doc.subject_id,
        "errorMessage": doc.safe_error_message,
        "createdAt": doc.created_at.isoformat() if doc.created_at else None,
    }


def _chapters_for(doc: Document, pages: list) -> list:
    if not pages:
        return []
    try:
        outline = lesson_generator_service.build_outline_from_pages(
            document_title=doc.original_filename,
            extracted_pages=[{"page_number": p.page_number, "text": p.extracted_text} for p in pages],
            grade=doc.grade or 0,
            subject=doc.subject_id or "",
        )
    except ValueError:
        return []
    return [
        {
            "title": chapter.get("chapterTitle"),
            "pageStart": chapter.get("pageStart"),
            "pageEnd": chapter.get("pageEnd"),
        }
        for chapter in outline.get("chapters", [])
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    grade: Optional[int] = Form(None),
    subject_id: Optional[str] = Form(None),
    language_tag: Optional[str] = Form("en-IN"),
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Store the original file and return. Extraction runs on the background worker."""
    filename = file.filename or "uploaded_document.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    size_bytes = len(content)
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds 50MB limit ({round(size_bytes / (1024 * 1024), 2)} MB provided)",
        )
    validate_file_signature(ext, content)

    sha256_hash = hashlib.sha256(content).hexdigest()
    existing = (
        db.query(Document)
        .filter(
            Document.owner_id == owner_id,
            Document.sha256 == sha256_hash,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.desc())
        .first()
    )
    if existing:
        chunks_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == existing.id).count()
        return _document_payload(existing, chunks_count)

    storage_key = f"documents/{owner_id}/{uuid.uuid4()}/{filename}"
    doc = Document(
        owner_id=owner_id,
        source_mode="upload",
        original_filename=filename,
        storage_bucket=settings.STORAGE_BUCKET_DOCUMENTS,
        storage_key=storage_key,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        sha256=sha256_hash,
        language_tag=language_tag or "en-IN",
        grade=grade,
        subject_id=subject_id,
        status="uploading",
        attempt_count=0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        stored = await storage_service.upload_file(
            bucket=settings.STORAGE_BUCKET_DOCUMENTS,
            path=storage_key,
            content=content,
            mime_type=doc.mime_type,
        )
    except Exception as exc:
        stored = False
        doc.safe_error_message = str(exc)[:400]

    if not stored:
        doc.status = "failed"
        doc.error_code = "storage_failed"
        if not doc.safe_error_message:
            doc.safe_error_message = "The file could not be saved to private storage."
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=doc.safe_error_message)

    doc.status = "stored"
    doc.safe_error_message = None
    db.commit()
    db.refresh(doc)
    return _document_payload(doc, 0)


@router.get("/{document_id}/status")
def get_document_status(
    document_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()
    chunks_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
    payload = _document_payload(doc, chunks_count)
    pages_read = sum(1 for page in pages if (page.extracted_text or "").strip())
    pages_needing_ocr = sum(1 for page in pages if page.is_scanned_ocr_needed)
    payload["pagesRead"] = pages_read
    payload["pagesNeedingOcr"] = pages_needing_ocr
    payload["pages"] = [
        {
            "pageNumber": page.page_number,
            "charCount": page.char_count,
            "wordCount": page.word_count,
            "quality": page.extraction_quality,
            "needsOcr": page.is_scanned_ocr_needed,
            "preview": (page.extracted_text or "")[:120],
        }
        for page in pages
    ]
    payload["chapters"] = _chapters_for(doc, pages) if doc.status in READY_FOR_REVIEW else []
    return payload


@router.post("/{document_id}/retry")
def retry_document(
    document_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status not in ("failed", "needs_ocr"):
        raise HTTPException(status_code=409, detail=f"Document cannot be retried from status {doc.status}.")

    doc.status = "stored"
    doc.safe_error_message = None
    doc.error_code = None
    doc.lease_owner = None
    doc.lease_expires_at = None
    doc.attempt_count = 0
    db.commit()
    return _document_payload(doc, 0)


@router.get("")
def list_user_documents(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(Document)
        .filter(Document.owner_id == owner_id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_document_payload(doc) for doc in docs]


@router.delete("/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.storage_key:
        try:
            await storage_service.delete_file(bucket=doc.storage_bucket, path=doc.storage_key)
        except Exception:
            pass

    db.delete(doc)
    db.commit()
    return {"status": "deleted", "success": True, "documentId": str(document_id)}


@router.get("/{document_id}/diagrams/{filename}")
def get_extracted_diagram(
    document_id: uuid.UUID,
    filename: str,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(
        Document.id == document_id, Document.owner_id == owner_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Diagram not found")

    clean_name = os.path.basename(filename)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    filepath = os.path.join(base_dir, "diagrams", str(document_id), clean_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Diagram not found")
    media_type = "image/png"
    if clean_name.lower().endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    return FileResponse(filepath, media_type=media_type)
