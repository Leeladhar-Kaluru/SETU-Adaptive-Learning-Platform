import json
import uuid

import pytest

from app.models.learning import (
    CoachNote, LearningPath, LessonVersion, PathLesson, Question,
)
from app.services import coach_notes as coach_module


def _seed_question(db, owner_id, *, answer="A", concept_ids=None):
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Cells"},
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
        prompt_json={"text": "Which gas do plants absorb for photosynthesis?"},
        answer_key_json={"answer": answer, "feedback": "A is correct."},
        concept_ids=concept_ids or ["concept-1"], difficulty="standard",
        validation_status="ready",
    )
    db.add(question)
    db.commit()
    return version


def _attempt(version, key, response, **overrides):
    body = {
        "lessonVersionId": str(version.id), "questionKey": "q1", "response": response,
        "hintLevel": 0, "hintsUsed": [], "elapsedSeconds": 25,
        "attemptKind": "practice", "syncIdempotencyKey": key,
    }
    body.update(overrides)
    return body


def test_wrong_answer_enqueues_coach_note_with_real_attempt_snapshot(client, db):
    owner_id = uuid.uuid4()
    version = _seed_question(db, owner_id, answer="A")
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)},
        json=_attempt(version, "attempt-1", "B"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["personalCoach"] == "queued"
    assert body["conceptId"] == "concept-1"

    note = db.query(CoachNote).filter(CoachNote.owner_id == owner_id).one()
    assert note.status == "queued"
    attempts = note.request_json["attempts"]
    assert len(attempts) == 1
    snapshot = attempts[0]
    assert snapshot["response"] == "B"
    assert snapshot["isCorrect"] is False
    assert snapshot["correctAnswer"] == "A"
    assert "Which gas do plants absorb" in snapshot["question"]
    assert snapshot["elapsedSeconds"] == 25


def test_idempotent_retry_does_not_double_enqueue(client, db):
    owner_id = uuid.uuid4()
    version = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    payload = _attempt(version, "attempt-1", "B")
    first = client.post("/api/v1/attempts", headers=headers, json=payload)
    second = client.post("/api/v1/attempts", headers=headers, json=payload)
    assert first.json()["personalCoach"] == "queued"
    assert second.json()["personalCoach"] is None
    assert db.query(CoachNote).filter(CoachNote.owner_id == owner_id).count() == 1


def test_repeated_attempts_append_to_the_same_note(client, db):
    owner_id = uuid.uuid4()
    version = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    for index, answer in enumerate(["B", "A", "B"]):
        response = client.post(
            "/api/v1/attempts", headers=headers,
            json=_attempt(version, f"attempt-{index}", answer),
        )
        assert response.status_code == 200
    note = db.query(CoachNote).filter(CoachNote.owner_id == owner_id).one()
    attempts = note.request_json["attempts"]
    assert len(attempts) == 3
    assert [a["response"] for a in attempts] == ["B", "A", "B"]
    assert [a["isCorrect"] for a in attempts] == [False, True, False]


@pytest.mark.asyncio
async def test_worker_turns_real_attempts_into_a_personalized_note(client, db, monkeypatch):
    owner_id = uuid.uuid4()
    version = _seed_question(db, owner_id, answer="A")
    headers = {"X-User-Id": str(owner_id)}
    for index in range(2):
        client.post(
            "/api/v1/attempts", headers=headers,
            json=_attempt(version, f"attempt-{index}", "B"),
        )

    captured = {"user": None}

    async def fake_chat(messages=None, **kwargs):
        captured["user"] = messages[-1]["content"]
        return json.dumps({
            "headline": "Mixing up the plant gases",
            "body": "You chose B both times. Photosynthesis takes in carbon dioxide, not oxygen.",
            "studyTipTitle": "Trace the gas exchange",
            "studyTipBody": "Draw the leaf and label what enters and leaves through the stomata.",
        })

    monkeypatch.setattr(coach_module.ai_provider, "generate_chat", fake_chat)

    claimed = coach_module.claim_next_coach_note(db, "test-worker")
    assert claimed is not None
    assert claimed.status == "claimed"
    ok = await coach_module.process_coach_note(db, claimed)
    assert ok is True
    assert '"response": "B"' in captured["user"]
    assert "Which gas do plants absorb" in captured["user"]

    response = client.get("/api/v1/study/coach-note/concept-1", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    content = body["note"]["content"]
    assert content["headline"] == "Mixing up the plant gases"
    assert content["analyzedAttempts"] == 2
    assert "carbon dioxide" in content["body"]
    assert content["studyTipBody"].startswith("Draw the leaf")


@pytest.mark.asyncio
async def test_coach_provider_failure_is_requeued_then_fails_safely(client, db, monkeypatch):
    owner_id = uuid.uuid4()
    version = _seed_question(db, owner_id)
    client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)},
        json=_attempt(version, "attempt-1", "B"),
    )

    async def broken_chat(**kwargs):
        raise RuntimeError("model offline")

    monkeypatch.setattr(coach_module.ai_provider, "generate_chat", broken_chat)

    for _ in range(coach_module.MAX_ATTEMPTS):
        claimed = coach_module.claim_next_coach_note(db, "test-worker")
        assert claimed is not None
        ok = await coach_module.process_coach_note(db, claimed)
        assert ok is False

    note = db.query(CoachNote).filter(CoachNote.owner_id == owner_id).one()
    assert note.status == "failed"
    assert note.safe_error_message
    assert note.lease_owner is None

    response = client.get(
        "/api/v1/study/coach-note/concept-1", headers={"X-User-Id": str(owner_id)}
    )
    assert response.json()["status"] == "none"


def test_coach_note_endpoint_reports_pending_and_none_states(client, db):
    owner_id = uuid.uuid4()
    version = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    client.post(
        "/api/v1/attempts", headers=headers,
        json=_attempt(version, "attempt-1", "B"),
    )

    pending = client.get("/api/v1/study/coach-note/concept-1", headers=headers).json()
    assert pending["status"] == "pending"

    missing = client.get("/api/v1/study/coach-note/concept-9", headers=headers).json()
    assert missing["status"] == "none"

    other_user = client.get(
        "/api/v1/study/coach-note/concept-1",
        headers={"X-User-Id": str(uuid.uuid4())},
    ).json()
    assert other_user["status"] == "none"
