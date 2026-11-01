import uuid

from app.core.storage import storage_service
from app.models.documents import Document, DocumentChunk


def _headers(owner_id: uuid.UUID) -> dict[str, str]:
    return {"X-User-Id": str(owner_id)}


def test_list_reports_real_chunk_counts(client, db):
    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id,
        original_filename="cells.pdf",
        storage_key="documents/cells.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        status="awaiting_review",
        page_count=2,
    )
    db.add(doc)
    db.flush()
    for index in range(2):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                page_start=1,
                page_end=1,
                chunk_index=index,
                text=f"Chunk {index}",
                text_hash=f"hash-{index}",
            )
        )
    db.commit()

    response = client.get("/api/v1/documents", headers=_headers(owner_id))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["chunkCount"] == 2


def test_progress_text_is_not_reported_as_an_error(client, db):
    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id,
        original_filename="cells.pdf",
        storage_key="documents/cells.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        status="extracting",
        safe_error_message="Processing page 3/10...",
    )
    db.add(doc)
    db.commit()

    body = client.get(f"/api/v1/documents/{doc.id}/status", headers=_headers(owner_id)).json()
    assert body["errorMessage"] is None
    assert body["progressMessage"] == "Processing page 3/10..."

    doc.status = "failed"
    doc.safe_error_message = "The document could not be processed."
    db.commit()

    body = client.get(f"/api/v1/documents/{doc.id}/status", headers=_headers(owner_id)).json()
    assert body["errorMessage"] == "The document could not be processed."
    assert body["progressMessage"] is None


def test_reuploading_a_failed_file_retries_it(client, db, monkeypatch):
    async def fake_upload(**kwargs):
        return True

    monkeypatch.setattr(storage_service, "upload_file", fake_upload)
    owner_id = uuid.uuid4()
    content = b"Chapter 1 Water\nWater is a compound of hydrogen and oxygen.\n"
    file = ("water-notes.txt", content, "text/plain")

    first = client.post("/api/v1/documents/upload", files={"file": file}, headers=_headers(owner_id))
    assert first.status_code == 200, first.text
    document_id = first.json()["documentId"]

    stored = db.query(Document).filter(Document.id == uuid.UUID(document_id)).one()
    stored.status = "failed"
    stored.error_code = "processing_failed"
    stored.safe_error_message = "The document could not be processed."
    stored.attempt_count = 2
    db.commit()

    again = client.post("/api/v1/documents/upload", files={"file": file}, headers=_headers(owner_id))
    assert again.status_code == 200, again.text
    body = again.json()
    assert body["documentId"] == document_id
    assert body["status"] == "stored"
    assert body["errorMessage"] is None
    assert body["deduplicated"] is False

    db.refresh(stored)
    assert stored.attempt_count == 0
    assert stored.error_code is None
    assert stored.safe_error_message is None

def test_status_says_when_no_outline_can_be_built(client, db):
    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id,
        original_filename="notes.pdf",
        storage_key="documents/notes.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        status="awaiting_review",
        page_count=0,
    )
    db.add(doc)
    db.commit()

    body = client.get(f"/api/v1/documents/{doc.id}/status", headers=_headers(owner_id)).json()
    assert body["canBuildPath"] is False
    assert "could not detect chapter headings" in body["outlineMessage"]

def test_upload_strips_directory_parts_from_the_filename(client, db, monkeypatch):
    captured = {}

    async def fake_upload(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(storage_service, "upload_file", fake_upload)
    owner_id = uuid.uuid4()

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("..\\..\\secret.txt", b"Water is a compound.\n", "text/plain")},
        headers=_headers(owner_id),
    )
    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "secret.txt"
    assert captured["path"].endswith("/secret.txt")
    assert ".." not in captured["path"]
