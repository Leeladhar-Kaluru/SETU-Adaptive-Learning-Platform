import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1.documents import validate_file_signature
from app.api.v1.learning_paths import CreatePathRequest
from app.core.storage import storage_service
from app.main import app
from app.models.documents import Document
from app.services.extraction import extraction_service
from app.services.lesson_generator import lesson_generator_service
from app.core.database import SessionLocal

client = TestClient(app)
FRONTEND_READER = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "LessonReaderPage.tsx"


def test_outline_uses_document_headings():
    outline = lesson_generator_service.build_outline_from_pages(
        document_title="notes.txt",
        extracted_pages=[
            {"page_number": 1, "text": "Chapter 1 Photosynthesis\nPlants capture light."},
            {"page_number": 2, "text": "The leaf is the usual site of this process."},
            {"page_number": 4, "text": "Chapter 2 Respiration\nCells release energy."},
        ],
        grade=7,
        subject="subject-science",
    )
    titles = [chapter["chapterTitle"] for chapter in outline["chapters"]]
    assert titles[0].startswith("Chapter 1")
    assert titles[-1].startswith("Chapter 2")
    assert outline["chapters"][0]["pageStart"] == 1
    assert outline["chapters"][-1]["pageEnd"] == 4
    blob = " ".join(titles)
    assert "Core Foundational" not in blob
    assert "Fundamentals of" not in blob


def test_outline_refuses_empty_extraction():
    with pytest.raises(ValueError):
        lesson_generator_service.build_outline_from_pages(
            document_title="scan.pdf",
            extracted_pages=[{"page_number": 1, "text": "[Image-only or empty page; OCR indexing required]"}],
            grade=8,
            subject="subject-math",
        )


def test_create_path_accepts_document_id_alias():
    document_id = uuid.uuid4()
    req = CreatePathRequest.model_validate({"documentId": str(document_id), "grade": 8})
    assert req.document_id == document_id


def test_signature_rejects_fake_pdf():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        validate_file_signature("pdf", b"this is not a pdf")


def test_lesson_reader_has_no_demo_package():
    source = FRONTEND_READER.read_text(encoding="utf-8")
    assert "getDefaultDemoPackage" not in source
    assert "Plasma Membrane & Diffusion Mechanics" not in source


def test_production_generator_has_no_test_fixture():
    source = Path(__file__).resolve().parents[1] / "app" / "services" / "lesson_generator.py"
    text = source.read_text(encoding="utf-8")
    assert "_test_fixture" not in text
    assert "_build_deterministic" not in text


def test_upload_returns_before_extraction(monkeypatch):
    async def fake_upload(**kwargs):
        return True

    def explode(*args, **kwargs):
        raise AssertionError("extraction must not run during upload")

    monkeypatch.setattr(storage_service, "upload_file", fake_upload)
    monkeypatch.setattr(extraction_service, "extract_document", explode)

    content = b"Chapter 1 Water\nWater is a compound of hydrogen and oxygen.\n"
    test_headers = {"X-User-Id": "a0000000-0000-0000-0000-000000000001"}
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("water-notes.txt", content, "text/plain")},
        headers=test_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "stored"
    assert body["documentId"]

    again = client.post(
        "/api/v1/documents/upload",
        files={"file": ("water-notes.txt", content, "text/plain")},
        headers=test_headers,
    )
    assert again.status_code == 200
    assert again.json()["documentId"] == body["documentId"]

    db = SessionLocal()
    try:
        db.query(Document).filter(Document.id == uuid.UUID(body["documentId"])).delete()
        db.commit()
    finally:
        db.close()
