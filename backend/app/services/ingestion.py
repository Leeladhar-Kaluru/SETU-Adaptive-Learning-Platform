"""Document ingestion that runs after the file is already in Storage."""

import asyncio
import datetime
import logging
import os
from typing import List

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.ai_provider import EmbeddingUnavailableError, ai_provider
from app.core.config import settings
from app.core.storage import storage_service
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.services.chunking import chunking_service
from app.services.extraction import extraction_service

logger = logging.getLogger(__name__)

LEASE_SECONDS = 600
OCR_MARKER = "[Image-only or empty page"


def _touch_lease(doc: Document) -> None:
    doc.lease_expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(seconds=LEASE_SECONDS)


def _usable_text(text: str) -> str:
    cleaned = (text or "").replace("\x00", "").strip()
    if not cleaned or cleaned.startswith(OCR_MARKER):
        return ""
    return cleaned


async def process_claimed_document(db: Session, doc: Document) -> None:
    """Extract, chunk, and embed a document that the worker has already claimed."""
    document_id = doc.id
    try:
        content = await storage_service.download_file(bucket=doc.storage_bucket, path=doc.storage_key)
        if not content:
            raise RuntimeError("Stored file could not be read back from private storage.")

        doc.status = "extracting"
        _touch_lease(doc)
        db.commit()

        def on_page_progress(current_page: int, total_pages: int, message: str):
            logger.info("Extracting document %s: page %d/%d (%s)", document_id, current_page, total_pages, message)

        pages = await asyncio.to_thread(
            extraction_service.extract_document,
            file_bytes=content,
            filename=doc.original_filename,
            mime_type=doc.mime_type,
            progress_callback=on_page_progress,
        )
        _touch_lease(doc)
        usable = [p for p in pages if _usable_text(p.get("text", ""))]
        scanned = [p for p in pages if p.get("is_scanned_ocr_needed")]

        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.query(DocumentPage).filter(DocumentPage.document_id == document_id).delete()

        diagram_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "diagrams",
            str(document_id),
        )
        os.makedirs(diagram_dir, exist_ok=True)

        for page in pages:
            safe_text = (page.get("text") or "").replace("\x00", "")
            page["text"] = safe_text
            metadata = dict(page.get("metadata") or {})

            saved_diagram_urls = []
            if page.get("diagrams"):
                for d in page["diagrams"]:
                    try:
                        d_name = f"page_{page['page_number']}_d{d['index']}.{d['format']}"
                        d_path = os.path.join(diagram_dir, d_name)
                        with open(d_path, "wb") as f:
                            f.write(d["bytes"])
                        saved_diagram_urls.append(f"/api/v1/documents/{document_id}/diagrams/{d_name}")
                    except Exception:
                        pass
            if saved_diagram_urls:
                metadata["diagrams"] = saved_diagram_urls

            db.add(
                DocumentPage(
                    document_id=document_id,
                    page_number=page["page_number"],
                    extracted_text=safe_text,
                    char_count=page["char_count"],
                    word_count=page["word_count"],
                    is_scanned_ocr_needed=page["is_scanned_ocr_needed"],
                    extraction_quality=page["extraction_quality"],
                    parser_metadata=metadata,
                )
            )

        doc.page_count = len(pages)
        if not usable or (pages and len(scanned) == len(pages)):
            doc.status = "needs_ocr"
            doc.safe_error_message = (
                "No readable text was found after text extraction and OCR. Upload a clearer copy or retry."
                if extraction_service.tessdata_path
                else "No readable text was found, and OCR is not installed on this worker. Upload a text-based copy or install Tesseract data."
            )
            doc.error_code = "needs_ocr"
            doc.lease_owner = None
            doc.lease_expires_at = None
            db.commit()
            return

        doc.status = "indexing"
        _touch_lease(doc)
        db.commit()

        chunks = chunking_service.create_chunks(pages)
        indexable = []
        for c in chunks:
            clean_chunk_text = _usable_text(c.get("text", ""))
            if clean_chunk_text:
                c["text"] = clean_chunk_text
                indexable.append(c)

        if not indexable:
            doc.status = "needs_ocr"
            doc.safe_error_message = "Extraction produced no text that can be indexed."
            doc.error_code = "needs_ocr"
            doc.lease_owner = None
            doc.lease_expires_at = None
            db.commit()
            return

        BATCH_SIZE = 16
        embedded_chunks = []
        for batch_start in range(0, len(indexable), BATCH_SIZE):
            batch = indexable[batch_start:batch_start + BATCH_SIZE]
            texts = [(chunk.get("text") or "").replace("\x00", "").strip() for chunk in batch]
            texts = [t for t in texts if t]
            if not texts:
                continue
            vectors = await ai_provider.get_embeddings_batch(texts)
            if len(vectors) != len(texts):
                raise ValueError("Embedding count does not match the chunk batch.")
            embedded_chunks.extend(zip(batch, vectors))

        for chunk, vector in embedded_chunks:
            stream_text = (chunk.get("text") or "").replace("\x00", "").strip()
            db.add(
                DocumentChunk(
                    document_id=document_id,
                    page_start=chunk["page_start"],
                    page_end=chunk["page_end"],
                    heading_path=chunk["heading_path"],
                    chunk_index=chunk["chunk_index"],
                    text=stream_text,
                    text_hash=chunk["text_hash"],
                    language_tag=doc.language_tag or "en-IN",
                    access_scope="private",
                    embedding_model_id=settings.EMBEDDING_MODEL,
                    embedding_dimension=settings.EMBEDDING_DIMENSION,
                    embedding=vector,
                )
            )
        db.commit()

        doc.status = "awaiting_review"
        doc.safe_error_message = None
        doc.error_code = None
        doc.lease_owner = None
        doc.lease_expires_at = None
        db.commit()
    except Exception as exc:
        logger.exception("Document %s processing failed with error: %s", document_id, exc)
        try:
            db.rollback()
        except Exception as rb_exc:
            logger.warning("Rollback failed for document %s: %s", document_id, rb_exc)

        try:
            failed = db.query(Document).filter(Document.id == document_id).first()
            if failed:
                # All-or-nothing: never leave partially embedded chunks behind after a failure.
                try:
                    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
                except Exception as del_exc:
                    logger.warning("Failed to clean document chunks on failure: %s", del_exc)

                failed.status = "failed"
                exc_str = str(exc).lower()
                if isinstance(exc, EmbeddingUnavailableError) or "embedding" in exc_str:
                    failed.error_code = "embedding_unavailable"
                    failed.safe_error_message = "The embedding service is unavailable. Retry when it is running."
                elif "extract" in exc_str or "pdf" in exc_str or "mupdf" in exc_str:
                    failed.error_code = "extraction_failed"
                    failed.safe_error_message = f"Document extraction failed: {str(exc)}"
                elif isinstance(exc, SQLAlchemyError) or "database" in exc_str or "operationalerror" in str(type(exc)).lower() or "pendingrollbackerror" in str(type(exc)).lower():
                    failed.error_code = "database_error"
                    failed.safe_error_message = f"Database error during processing: {str(exc)}"
                else:
                    failed.error_code = "processing_failed"
                    failed.safe_error_message = "The document could not be processed. Retry or upload a readable copy."
                failed.lease_owner = None
                failed.lease_expires_at = None
                db.commit()
        except Exception as handler_exc:
            logger.exception("Failed to update status for failed document %s: %s", document_id, handler_exc)
