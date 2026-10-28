import uuid
import pytest

from app.core.ai_provider import EmbeddingUnavailableError
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.services import ingestion as ingestion_module
from app.services.ingestion import process_claimed_document


def _document(db):
    doc = Document(
        owner_id=uuid.uuid4(), original_filename="book.pdf",
        storage_key="documents/book.pdf", mime_type="application/pdf",
        size_bytes=100, status="stored", lease_owner="test-worker",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _page(text="Cells are the fundamental unit of life.", needs_ocr=False):
    return {
        "page_number": 1, "text": text, "char_count": len(text),
        "word_count": len(text.split()), "is_scanned_ocr_needed": needs_ocr,
        "extraction_quality": "low" if needs_ocr else "high", "metadata": {},
    }


@pytest.mark.asyncio
async def test_unreadable_document_is_needs_ocr_and_indexes_nothing(db, monkeypatch):
    doc = _document(db)

    async def fake_download(**kwargs):
        return b"not really a pdf"

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kwargs: [_page("", True)])
    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "needs_ocr"
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


@pytest.mark.asyncio
async def test_embedding_failure_leaves_no_partial_chunks(db, monkeypatch):
    doc = _document(db)

    async def fake_download(**kwargs):
        return b"pdf"

    async def failing_embeddings(texts):
        raise EmbeddingUnavailableError("provider down")

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kwargs: [_page()])
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", failing_embeddings)
    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "failed"
    assert doc.error_code == "embedding_unavailable"
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


@pytest.mark.asyncio
async def test_valid_document_indexes_only_valid_vectors(db, monkeypatch):
    doc = _document(db)

    async def fake_download(**kwargs):
        return b"pdf"

    async def valid_embeddings(texts):
        assert all(text.strip() for text in texts)
        return [[0.25] * 768 for _ in texts]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kwargs: [_page()])
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", valid_embeddings)
    await process_claimed_document(db, doc)
    db.refresh(doc)

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert doc.status == "awaiting_review"
    assert chunks
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(chunk.embedding_dimension == 768 for chunk in chunks)


def test_status_reports_all_pages_and_ocr_counts(client, db):
    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id, original_filename="book.pdf", storage_key="documents/book.pdf",
        mime_type="application/pdf", size_bytes=100, status="awaiting_review", page_count=2,
    )
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentPage(document_id=doc.id, page_number=1, extracted_text="Readable text", char_count=13, word_count=2),
        DocumentPage(document_id=doc.id, page_number=2, extracted_text="", char_count=0, word_count=0, is_scanned_ocr_needed=True, extraction_quality="low"),
    ])
    db.commit()

    response = client.get(f"/api/v1/documents/{doc.id}/status", headers={"X-User-Id": str(owner_id)})
    assert response.status_code == 200
    body = response.json()
    assert body["pagesRead"] == 1
    assert body["pagesNeedingOcr"] == 1
    assert len(body["pages"]) == 2
