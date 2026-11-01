"""Adversarial challenge tests for backend/app/services/ingestion.py.

Empirically stress-tests:
1. Null byte (\x00) sanitization in texts, headings, and all-null documents.
2. Embedding failure isolation, error codes, traceback logging, and complete chunk purge.
3. Scanned documents needing OCR without crashing.
4. Transaction rollback hygiene and absence of PendingRollbackError.
"""

import logging
import uuid
import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.ai_provider import EmbeddingUnavailableError
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.services import ingestion as ingestion_module
from app.services.ingestion import process_claimed_document, _usable_text


def _create_claimed_doc(db, filename="test_doc.pdf"):
    doc = Document(
        owner_id=uuid.uuid4(),
        original_filename=filename,
        storage_key=f"documents/{filename}",
        mime_type="application/pdf",
        size_bytes=4096,
        status="stored",
        lease_owner="challenger-worker",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ----------------------------------------------------------------------
# 1. Null byte (\x00) adversarial tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adversarial_null_bytes_in_body_and_headings(db, monkeypatch):
    """Verify that null bytes sprinkled across headings and bodies are stripped everywhere:
    in pages, chunks, embeddings input, and database columns."""
    doc = _create_claimed_doc(db)

    pages_with_nulls = [
        {
            "page_number": 1,
            "text": "# Chapter \x001: The Null\x00 Hazard\nParagraph with \x00null\x00 bytes scattered throughout\x00.",
            "char_count": 80,
            "word_count": 10,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        },
        {
            "page_number": 2,
            "text": "Page 2 has trailing nulls\x00\x00\x00 and internal\x00 tokens.",
            "char_count": 50,
            "word_count": 7,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }
    ]

    async def fake_download(**kwargs):
        return b"%PDF-nulls"

    texts_received_by_embedder = []

    async def fake_embeddings(texts):
        texts_received_by_embedder.extend(texts)
        for t in texts:
            assert "\x00" not in t, f"Embedder received string with null byte: {repr(t)}"
        return [[0.05] * 768 for _ in texts]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: pages_with_nulls)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", fake_embeddings)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "awaiting_review"
    assert doc.error_code is None

    # Check pages in DB
    pages_in_db = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).all()
    assert len(pages_in_db) == 2
    for p in pages_in_db:
        assert "\x00" not in p.extracted_text

    # Check chunks in DB
    chunks_in_db = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert len(chunks_in_db) > 0
    for c in chunks_in_db:
        assert "\x00" not in c.text
        for h in c.heading_path:
            assert "\x00" not in h

    assert len(texts_received_by_embedder) > 0


@pytest.mark.asyncio
async def test_adversarial_document_with_only_null_bytes(db, monkeypatch):
    """A document containing only null bytes and spaces must degrade cleanly to needs_ocr."""
    doc = _create_claimed_doc(db)

    async def fake_download(**kwargs):
        return b"\x00" * 500

    all_null_pages = [
        {
            "page_number": 1,
            "text": "\x00\x00\x00   \x00\t\x00\n\x00",
            "char_count": 10,
            "word_count": 0,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "low",
            "metadata": {},
        }
    ]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: all_null_pages)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "needs_ocr"
    assert doc.error_code == "needs_ocr"
    assert doc.lease_owner is None
    # No chunks should have been created
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


# ----------------------------------------------------------------------
# 2. Embedding failure adversarial tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adversarial_embedding_failure_cleans_partial_chunks_and_logs(db, monkeypatch):
    """When embedding provider fails after some chunks existed or during multi-batch processing,
    verify document is marked failed with embedding_unavailable, exception is logged,
    and database contains 0 chunks."""
    doc = _create_claimed_doc(db)

    # Pre-populate some dummy chunks to simulate dirty DB state
    dirty_chunk = DocumentChunk(
        document_id=doc.id,
        page_start=1,
        page_end=1,
        heading_path=[],
        chunk_index=99,
        text="Leftover stale chunk from earlier attempt",
        text_hash="abc",
        language_tag="en-IN",
        access_scope="private",
        embedding_model_id="test",
        embedding_dimension=768,
        embedding=[0.0] * 768,
    )
    db.add(dirty_chunk)
    db.commit()
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 1

    async def fake_download(**kwargs):
        return b"%PDF-test"

    valid_pages = [
        {
            "page_number": 1,
            "text": "Valid extractable textbook paragraph with significant content.",
            "char_count": 60,
            "word_count": 7,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }
    ]

    async def failing_embeddings(texts):
        raise EmbeddingUnavailableError("GPU Ollama server connection refused on port 11434")

    logged_exceptions = []
    original_logger_exception = ingestion_module.logger.exception

    def spy_logger_exception(msg, *args, **kwargs):
        logged_exceptions.append(msg % args if args else msg)
        original_logger_exception(msg, *args, **kwargs)

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: valid_pages)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", failing_embeddings)
    monkeypatch.setattr(ingestion_module.logger, "exception", spy_logger_exception)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    # Verification 1: document marked failed with code embedding_unavailable
    assert doc.status == "failed"
    assert doc.error_code == "embedding_unavailable"
    assert "embedding service is unavailable" in doc.safe_error_message.lower()
    assert doc.lease_owner is None
    assert doc.lease_expires_at is None

    # Verification 2: exception was logged with document id and error
    assert any(str(doc.id) in msg for msg in logged_exceptions)
    assert any("GPU Ollama server connection refused" in msg for msg in logged_exceptions)

    # Verification 3: database is in clean state with 0 partial chunks
    remaining_chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
    assert remaining_chunks == 0


@pytest.mark.asyncio
async def test_adversarial_embedding_timeout_error_string_categorization(db, monkeypatch):
    """If provider raises generic RuntimeError containing 'embedding timeout', it must still be
    categorized as embedding_unavailable."""
    doc = _create_claimed_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-test"

    valid_pages = [
        {
            "page_number": 1,
            "text": "Valid text content for embedding categorization test.",
            "char_count": 52,
            "word_count": 7,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }
    ]

    async def timeout_embeddings(texts):
        raise RuntimeError("Embedding API timed out after 30 seconds")

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: valid_pages)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", timeout_embeddings)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "failed"
    assert doc.error_code == "embedding_unavailable"
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


@pytest.mark.asyncio
async def test_adversarial_multi_batch_embedding_failure_leaves_zero_chunks(db, monkeypatch):
    """When generating embeddings across multiple batches (e.g. batch 1 succeeds, batch 2 fails),
    verify that zero chunks are retained in the database."""
    doc = _create_claimed_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-multibatch"

    # Create 35 pages to generate at least 35 chunks (> 2 batches of 16)
    pages = [
        {
            "page_number": i,
            "text": f"Chapter {i}: Detailed concept exploration and scientific terminology for unit {i}.",
            "char_count": 80,
            "word_count": 12,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }
        for i in range(1, 36)
    ]

    call_count = 0

    async def flaky_embeddings_batch(texts):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Batch 1 succeeds
            return [[0.1] * 768 for _ in texts]
        # Batch 2 fails
        raise EmbeddingUnavailableError("Rate limit or connection dropped on batch 2")

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: pages)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", flaky_embeddings_batch)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "failed"
    assert doc.error_code == "embedding_unavailable"
    # Even though batch 1 succeeded, no chunks should be left in the database
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0



# ----------------------------------------------------------------------
# 3. Scanned document needing OCR
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adversarial_scanned_document_sets_needs_ocr_without_crashing(db, monkeypatch):
    """When a document consists of scanned pages with is_scanned_ocr_needed=True,
    verify it sets needs_ocr, records pages in DB, and indexes 0 chunks without throwing."""
    doc = _create_claimed_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-scanned"

    scanned_pages = [
        {
            "page_number": 1,
            "text": "[Image-only or empty page 1]",
            "char_count": 28,
            "word_count": 5,
            "is_scanned_ocr_needed": True,
            "extraction_quality": "low",
            "metadata": {},
        },
        {
            "page_number": 2,
            "text": "[Image-only or empty page 2]",
            "char_count": 28,
            "word_count": 5,
            "is_scanned_ocr_needed": True,
            "extraction_quality": "low",
            "metadata": {},
        }
    ]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: scanned_pages)

    # Must complete cleanly without raising any uncaught exception
    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "needs_ocr"
    assert doc.error_code == "needs_ocr"
    assert doc.page_count == 2
    assert doc.lease_owner is None
    assert doc.lease_expires_at is None

    # Pages must be recorded in DB for page-level OCR reporting
    pages_in_db = db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).all()
    assert len(pages_in_db) == 2
    assert all(p.is_scanned_ocr_needed for p in pages_in_db)

    # 0 chunks should be indexed
    assert db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count() == 0


# ----------------------------------------------------------------------
# 4. Transaction rollback hygiene & absence of PendingRollbackError
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_adversarial_no_pending_rollback_error_on_database_failure(db, monkeypatch):
    """Verify that if an operational or flush error occurs mid-transaction,
    ingestion.py's rollback guard properly clears the failed transaction
    and does NOT raise PendingRollbackError when recording the failure status."""
    doc = _create_claimed_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-test"

    valid_pages = [
        {
            "page_number": 1,
            "text": "Valid text to trigger chunk commit.",
            "char_count": 35,
            "word_count": 6,
            "is_scanned_ocr_needed": False,
            "extraction_quality": "high",
            "metadata": {},
        }
    ]

    async def fake_embeddings(texts):
        return [[0.1] * 768 for _ in texts]

    original_commit = db.commit
    fail_first_commit = True

    def flaky_commit():
        nonlocal fail_first_commit
        if fail_first_commit:
            fail_first_commit = False
            # Simulate a database failure during chunk insertion commit
            raise OperationalError("simulated commit failure", {}, None)
        return original_commit()

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", lambda **kw: valid_pages)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", fake_embeddings)
    monkeypatch.setattr(db, "commit", flaky_commit)

    # If PendingRollbackError were triggered, process_claimed_document would re-fail in the handler
    await process_claimed_document(db, doc)
    db.refresh(doc)

    # Status must be captured as database_error without crashing with PendingRollbackError
    assert doc.status == "failed"
    assert doc.error_code == "database_error"


@pytest.mark.asyncio
async def test_adversarial_progress_callback_thread_safety(db, monkeypatch):
    """Verify that multiple concurrent progress callback calls during extraction
    do not interact with the db session or cause session state corruption."""
    doc = _create_claimed_doc(db)

    async def fake_download(**kwargs):
        return b"%PDF-multipage"

    def multi_page_extract_with_callbacks(file_bytes, filename, mime_type, progress_callback=None):
        if progress_callback:
            # Rapid progress calls simulating worker thread execution
            for page in range(1, 15):
                progress_callback(page, 14, f"Processing page {page}/14")
        return [
            {
                "page_number": i,
                "text": f"Content of page {i} with sufficient text.",
                "char_count": 40,
                "word_count": 7,
                "is_scanned_ocr_needed": False,
                "extraction_quality": "high",
                "metadata": {},
            }
            for i in range(1, 15)
        ]

    async def fake_embeddings(texts):
        return [[0.2] * 768 for _ in texts]

    monkeypatch.setattr(ingestion_module.storage_service, "download_file", fake_download)
    monkeypatch.setattr(ingestion_module.extraction_service, "extract_document", multi_page_extract_with_callbacks)
    monkeypatch.setattr(ingestion_module.ai_provider, "get_embeddings_batch", fake_embeddings)

    await process_claimed_document(db, doc)
    db.refresh(doc)

    assert doc.status == "awaiting_review"
    assert doc.page_count == 14
    assert db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).count() == 14
