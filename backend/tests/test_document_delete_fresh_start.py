import uuid

from app.core.storage import storage_service
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.doubts import Doubt
from app.models.jobs import GenerationJob
from app.models.learning import (
    ConceptEvidence, LearningPath, LessonVersion, PathLesson, Question,
    QuizAttempt, StudyEvent,
)


def _headers(owner_id: uuid.UUID) -> dict[str, str]:
    return {"X-User-Id": str(owner_id)}


def _seed_tree(db, owner_id, *, status="ready"):
    doc = Document(
        owner_id=owner_id, original_filename="science.pdf",
        storage_key="documents/science.pdf", storage_bucket="documents",
        mime_type="application/pdf", size_bytes=100, status=status, page_count=2,
    )
    db.add(doc)
    db.flush()
    db.add(DocumentPage(
        document_id=doc.id, page_number=1, extracted_text="Page one text.",
        char_count=14, word_count=3,
    ))
    db.add(DocumentChunk(
        document_id=doc.id, page_start=1, page_end=1, chunk_index=0,
        text="Page one text.", text_hash="hash-0",
    ))
    db.flush()
    path = LearningPath(
        owner_id=owner_id, document_id=doc.id, grade=9,
        subject_id="subject-science", outline_json={"title": "Cells"},
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(
        path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready",
    )
    db.add(lesson)
    db.flush()
    version = LessonVersion(
        path_lesson_id=lesson.id, version_number=1,
        lesson_package_json={"title": "Cells"}, validation_status="ready",
    )
    db.add(version)
    db.flush()
    question = Question(
        lesson_version_id=version.id, question_key="q1", type="multiple_choice",
        prompt_json={"text": "Choose A"},
        answer_key_json={"answer": "A", "feedback": "A is correct."},
        concept_ids=["concept-1"], difficulty="standard", validation_status="ready",
    )
    db.add(question)
    db.flush()
    db.add(GenerationJob(
        owner_id=owner_id, path_id=path.id, lesson_id=lesson.id,
        idempotency_key=f"job-{doc.id}", status="failed", attempt_count=3,
    ))
    db.add(Doubt(
        owner_id=owner_id, client_doubt_id="doubt-1", path_id=path.id,
        question_text="What is a cell?", status="answered",
    ))
    db.commit()
    return doc, version


def test_deleting_a_document_removes_everything_built_from_it(client, db, monkeypatch):
    owner_id = uuid.uuid4()
    doc, version = _seed_tree(db, owner_id)

    attempt = client.post(
        "/api/v1/attempts", headers=_headers(owner_id),
        json={
            "lessonVersionId": str(version.id), "questionKey": "q1", "response": "A",
            "hintLevel": 0, "hintsUsed": [], "elapsedSeconds": 30,
            "attemptKind": "checkpoint", "syncIdempotencyKey": "attempt-1",
        },
    )
    assert attempt.status_code == 200, attempt.text
    assert db.query(QuizAttempt).count() == 1
    assert db.query(ConceptEvidence).count() == 1
    assert db.query(StudyEvent).count() == 1

    deleted = {"calls": 0}

    async def fake_delete_file(**kwargs):
        deleted["calls"] += 1

    monkeypatch.setattr(storage_service, "delete_file", fake_delete_file)

    response = client.delete(f"/api/v1/documents/{doc.id}", headers=_headers(owner_id))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "deleted"
    assert body["deletedPaths"] == 1
    assert deleted["calls"] == 1

    from app.models.learning import CoachNote

    for model in (
        Document, DocumentPage, DocumentChunk, LearningPath, PathLesson,
        LessonVersion, Question, QuizAttempt, ConceptEvidence, StudyEvent,
        Doubt, GenerationJob,
    ):
        assert db.query(model).count() == 0, model.__tablename__
    # Coach notes are owner/concept scoped and hold no document link, so the
    # fresh start does not need them — but the enqueued analysis must not crash.
    assert db.query(CoachNote).count() == 1


def test_delete_survives_storage_failure_and_still_clears_rows(client, db, monkeypatch):
    owner_id = uuid.uuid4()
    doc, _ = _seed_tree(db, owner_id)

    async def broken_delete(**kwargs):
        raise RuntimeError("storage offline")

    monkeypatch.setattr(storage_service, "delete_file", broken_delete)

    response = client.delete(f"/api/v1/documents/{doc.id}", headers=_headers(owner_id))
    assert response.status_code == 200, response.text
    assert response.json()["deletedPaths"] == 1
    assert db.query(Document).count() == 0
    assert db.query(DocumentChunk).count() == 0
    assert db.query(LearningPath).count() == 0


def test_other_users_document_is_not_found_and_stays_intact(client, db):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    doc, _ = _seed_tree(db, owner_id)

    response = client.delete(f"/api/v1/documents/{doc.id}", headers=_headers(other_id))
    assert response.status_code == 404
    assert db.query(Document).count() == 1
    assert db.query(DocumentChunk).count() == 1
    assert db.query(LearningPath).count() == 1
