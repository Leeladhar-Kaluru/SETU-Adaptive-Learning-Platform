import uuid

from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson


def _ready_document(db, owner_id):
    doc = Document(
        owner_id=owner_id, original_filename="Class_9_Science.pdf",
        storage_key=f"documents/{owner_id}/book.pdf", mime_type="application/pdf",
        size_bytes=100, status="awaiting_review", page_count=2,
    )
    db.add(doc)
    db.flush()
    db.add_all([
        DocumentPage(document_id=doc.id, page_number=1, extracted_text="Chapter 1: The Cell\nCells are the unit of life.", char_count=50, word_count=10),
        DocumentPage(document_id=doc.id, page_number=2, extracted_text="Chapter 2: Tissues\nTissues are groups of cells.", char_count=50, word_count=10),
    ])
    db.add(DocumentChunk(
        document_id=doc.id, page_start=1, page_end=2, chunk_index=0,
        heading_path=["Chapter 1"], text="Cells are the unit of life. Tissues are groups of cells.",
        text_hash="hash", embedding=[0.1] * 768,
        embedding_model_id="text-embedding-nomic-embed-text-v1.5", embedding_dimension=768,
    ))
    db.commit()
    return doc


def test_path_requires_explicit_grade_and_subject(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id)},
    )
    assert response.status_code == 422


def test_path_requires_a_real_subject(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id), "grade": 9, "subjectId": "subject-not-real"},
    )
    assert response.status_code == 422


def test_path_queues_one_job_per_lesson(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id), "grade": 9, "subjectId": "subject-science"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totalLessons"] >= 1
    lessons = db.query(PathLesson).filter(PathLesson.path_id == uuid.UUID(body["pathId"])).all()
    jobs = db.query(GenerationJob).filter(GenerationJob.path_id == uuid.UUID(body["pathId"])).all()
    assert len(lessons) == body["totalLessons"]
    assert len(jobs) == len(lessons)


def test_duplicate_path_is_rejected(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    payload = {"documentId": str(doc.id), "grade": 9, "subjectId": "subject-science"}
    headers = {"X-User-Id": str(owner_id)}
    assert client.post("/api/v1/learning-paths", headers=headers, json=payload).status_code == 200
    assert client.post("/api/v1/learning-paths", headers=headers, json=payload).status_code == 409


def test_document_without_indexed_chunks_is_rejected(client, db):
    owner_id = uuid.uuid4()
    doc = _ready_document(db, owner_id)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
    db.commit()
    response = client.post(
        "/api/v1/learning-paths",
        headers={"X-User-Id": str(owner_id)},
        json={"documentId": str(doc.id), "grade": 9, "subjectId": "subject-science"},
    )
    assert response.status_code == 409
