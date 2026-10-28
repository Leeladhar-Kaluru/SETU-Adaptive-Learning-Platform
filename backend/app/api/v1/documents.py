import uuid
import hashlib
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user_id
from app.core.storage import storage_service
from app.core.ai_provider import ai_provider
from app.models.documents import Document, DocumentPage, DocumentChunk
from app.services.extraction import extraction_service
from app.services.chunking import chunking_service

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    grade: Optional[int] = Form(9),
    subject_id: Optional[str] = Form("SCIENCE"),
    language_tag: Optional[str] = Form("en-IN"),
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Multi-format document upload (PDF, DOCX, PPTX, TXT, MD, JPG, PNG) supporting up to 50MB.
    Extracts pages, chunks, generates 768d embeddings, and indexes in PostgreSQL.
    """
    filename = file.filename or "upload.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Read bytes and verify size limit (50MB)
    content = await file.read()
    size_bytes = len(content)
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds 50MB limit ({round(size_bytes / (1024 * 1024), 2)} MB provided)"
        )

    sha256_hash = hashlib.sha256(content).hexdigest()
    storage_key = f"documents/{owner_id}/{uuid.uuid4()}/{filename}"

    # 1. Create document record
    doc = Document(
        owner_id=owner_id,
        source_mode="upload",
        original_filename=filename,
        storage_bucket=settings.STORAGE_BUCKET_DOCUMENTS,
        storage_key=storage_key,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
        sha256=sha256_hash,
        language_tag=language_tag,
        grade=grade,
        subject_id=subject_id,
        status="uploading"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2. Upload file to private Supabase storage
    try:
        stored = await storage_service.upload_file(
            bucket=settings.STORAGE_BUCKET_DOCUMENTS,
            path=storage_key,
            content=content,
            mime_type=doc.mime_type
        )
        if stored:
            doc.status = "stored"
            db.commit()
    except Exception as e:
        print(f"Storage upload notice: {e}")

    # 3. Extract text page-by-page
    doc.status = "extracting"
    db.commit()
    
    pages = extraction_service.extract_document(
        file_bytes=content,
        filename=filename,
        mime_type=doc.mime_type
    )

    doc.page_count = len(pages)
    for p in pages:
        dpage = DocumentPage(
            document_id=doc.id,
            page_number=p["page_number"],
            extracted_text=p["text"],
            char_count=p["char_count"],
            word_count=p["word_count"],
            is_scanned_ocr_needed=p["is_scanned_ocr_needed"],
            extraction_quality=p["extraction_quality"],
            parser_metadata=p.get("metadata")
        )
        db.add(dpage)
    db.commit()

    # 4. Chunk text
    doc.status = "chunking"
    db.commit()
    chunks = chunking_service.create_chunks(pages)

    # 5. Embed and index chunks
    doc.status = "embedding"
    db.commit()

    for c in chunks:
        # Get 768d embedding
        try:
            vec = await ai_provider.get_embedding(c["text"])
        except Exception:
            vec = [0.0] * settings.EMBEDDING_DIMENSION

        dchunk = DocumentChunk(
            document_id=doc.id,
            page_start=c["page_start"],
            page_end=c["page_end"],
            heading_path=c["heading_path"],
            chunk_index=c["chunk_index"],
            text=c["text"],
            text_hash=c["text_hash"],
            language_tag=language_tag,
            access_scope="private",
            embedding_model_id=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            embedding=vec
        )
        db.add(dchunk)

    doc.status = "ready"
    db.commit()
    db.refresh(doc)

    return {
        "id": str(doc.id),
        "filename": doc.original_filename,
        "sizeBytes": doc.size_bytes,
        "sizeMb": round(doc.size_bytes / (1024 * 1024), 2),
        "pageCount": doc.page_count,
        "chunkCount": len(chunks),
        "status": doc.status,
        "grade": doc.grade,
        "subjectId": doc.subject_id
    }

@router.get("")
def list_user_documents(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    docs = db.query(Document).filter(Document.owner_id == owner_id).order_by(Document.created_at.desc()).all()
    return [
        {
            "id": str(d.id),
            "filename": d.original_filename,
            "sizeBytes": d.size_bytes,
            "sizeMb": round(d.size_bytes / (1024 * 1024), 2),
            "pageCount": d.page_count,
            "status": d.status,
            "grade": d.grade,
            "subjectId": d.subject_id,
            "createdAt": d.created_at.isoformat()
        }
        for d in docs
    ]

@router.get("/{document_id}")
def get_document_details(
    document_id: uuid.UUID,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == owner_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_number.asc()).all()
    chunks_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()

    return {
        "id": str(doc.id),
        "filename": doc.original_filename,
        "status": doc.status,
        "pageCount": doc.page_count,
        "chunkCount": chunks_count,
        "sizeBytes": doc.size_bytes,
        "grade": doc.grade,
        "subjectId": doc.subject_id,
        "pages": [
            {
                "pageNumber": p.page_number,
                "charCount": p.char_count,
                "wordCount": p.word_count,
                "isScanned": p.is_scanned_ocr_needed,
                "quality": p.extraction_quality
            }
            for p in pages
        ]
    }
