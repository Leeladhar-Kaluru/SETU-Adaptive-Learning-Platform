import logging
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import OperationalError

from app.core.ai_provider import EmbeddingUnavailableError
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.services import ingestion as ingestion_module
from app.services.ingestion import process_claimed_document, _touch_lease, _usable_text


def _create_test_doc(db):
    doc = Document(
        owner_id=uuid.uuid4(),
        original_filename="sample_textbook.pdf",
        storage_key="documents/sample_textbook.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        status="stored",
        lease_owner="worker-1",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_touch_lease_uses_naive_utc():
    doc = Document()
    _touch_lease(doc)
    assert doc.lease_expires_at is not None
    assert doc.lease_expires_at.tzinfo is None


def test_usable_text_strips_null_bytes():
    assert _usable_text("Hello\x00World") == "HelloWorld"
    assert _usable_text("\x00   \x00") == ""
    assert _usable_text(None) == ""
    assert _usable_text("[Image-only or empty page 1]") == ""


@pytest.mark.asyncio
async def test_extraction_failure_is_categorized_and_logged(db, monkeypatch):
    doc = _create_test_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-corrupt"

    def failing_extract(**kwargs):
        # Invoke progress callback to ensure it does not crash or commit
        cb = kwargs.get("progress_callback")
        if cb:
            cb(1, 10, "Extracting page 1")
        raise RuntimeError("MuPDF extraction failed: damaged structure")

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", failing_extract)

    logged_errors = []
    original_exception = ingestion_module.logger.exception

    def spy_exception(msg, *args, **kwargs):
        logged_errors.append(msg % args if args else msg)
        original_exception(msg, *args, **kwargs)

    monkeypatch.setattr(ingestion_module.logger, "exception", spy_exception)

    await process_claimed_document(db, doc)

    db.refresh(doc)
    assert doc.status == "failed"
    assert doc.error_code == "extraction_failed"
    assert "damaged structure" in doc.safe_error_message
    assert any("processing failed with error" in msg for msg in logged_errors)
    assert any(str(doc.id) in msg for msg in logged_errors)


@pytest.mark.asyncio
async def test_embedding_failure_is_categorized_and_logged(db, monkeypatch):
    doc = _create_test_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-valid"

    def valid_extract(**kwargs):
        return [{
            "page_number": 1,
            "text": "Valid extractable textbook content.",
            "char_count": 35,
            "word_count": 4,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }]

    async def failing_embeddings(texts):
        raise EmbeddingUnavailableError("Local embedding server refused connection")

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", valid_extract)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", failing_embeddings)

    logged_errors = []
    original_exception = ingestion_module.logger.exception

    def spy_exception(msg, *args, **kwargs):
        logged_errors.append(msg % args if args else msg)
        original_exception(msg, *args, **kwargs)

    monkeypatch.setattr(ingestion_module.logger, "exception", spy_exception)

    await process_claimed_document(db, doc)

    db.refresh(doc)
    assert doc.status == "failed"
    assert doc.error_code == "embedding_unavailable"
    assert "embedding service is unavailable" in doc.safe_error_message.lower()
    assert any("processing failed with error" in msg for msg in logged_errors)
    assert any(str(doc.id) in msg for msg in logged_errors)


@pytest.mark.asyncio
async def test_chunk_sanitization_filters_null_and_empty_strings(db, monkeypatch):
    doc = _create_test_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-valid"

    def extract_with_nul_bytes(**kwargs):
        return [{
            "page_number": 1,
            "text": "Clean chapter line.\n\x00\nMore text.",
            "char_count": 30,
            "word_count": 5,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }]

    received_embedding_texts = []

    async def inspect_embeddings(texts):
        received_embedding_texts.extend(texts)
        assert all(t.strip() for t in texts)
        assert all("\x00" not in t for t in texts)
        return [[0.1] * 768 for _ in texts]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", extract_with_nul_bytes)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", inspect_embeddings)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "awaiting_review"
    assert received_embedding_texts
    assert all("\x00" not in t for t in received_embedding_texts)
