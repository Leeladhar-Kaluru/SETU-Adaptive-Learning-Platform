import uuid

from app.models.learning import (
    ConceptEvidence, ConceptMasterySnapshot, LearningPath, LessonVersion,
    PathLesson, Question, QuizAttempt, StudyEvent,
)


def _seed_question(db, owner_id, *, question_type="multiple_choice", answer="A", concept_ids=None):
    path = LearningPath(owner_id=owner_id, grade=9, subject_id="subject-science", outline_json={"title": "Cells"})
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready")
    db.add(lesson)
    db.flush()
    version = LessonVersion(path_lesson_id=lesson.id, version_number=1, lesson_package_json={"title": "Cells"}, validation_status="ready")
    db.add(version)
    db.flush()
    question = Question(
        lesson_version_id=version.id, question_key="q1", type=question_type,
        prompt_json={"text": "Choose A"}, answer_key_json={"answer": answer, "feedback": "A is correct."},
        concept_ids=concept_ids or ["concept-1"], difficulty="standard", validation_status="ready",
    )
    db.add(question)
    db.commit()
    return version, question


def _payload(version, key="attempt-1", response="A", **overrides):
    body = {
        "lessonVersionId": str(version.id), "questionKey": "q1", "response": response,
        "hintLevel": 0, "hintsUsed": [], "elapsedSeconds": 42,
        "attemptKind": "practice", "syncIdempotencyKey": key,
    }
    body.update(overrides)
    return body


def test_wrong_answer_cannot_be_forced_correct(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id, answer="A")
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)},
        json=_payload(version, response="B", **{"isCorrect": True, "score": 1.0}),
    )
    assert response.status_code == 200
    assert response.json()["isCorrect"] is False
    assert response.json()["score"] == 0.0
    feedback = response.json()["feedback"]
    assert "correct!" not in feedback.casefold()
    assert "A" in feedback


def test_correct_answer_records_evidence_and_exact_time(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id, answer="A", concept_ids=["concept-1", "concept-2"])
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)}, json=_payload(version)
    )
    assert response.status_code == 200
    attempt = db.query(QuizAttempt).filter(QuizAttempt.owner_id == owner_id).one()
    assert attempt.is_correct is True
    assert attempt.elapsed_seconds == 42
    assert db.query(ConceptEvidence).filter(ConceptEvidence.source_attempt_id == attempt.id).count() == 2
    event = db.query(StudyEvent).filter(StudyEvent.owner_id == owner_id).one()
    assert event.seconds == 42
    assert db.query(ConceptMasterySnapshot).filter(ConceptMasterySnapshot.owner_id == owner_id).count() == 2


def test_duplicate_idempotency_key_is_applied_once(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    first = client.post("/api/v1/attempts", headers=headers, json=_payload(version))
    second = client.post("/api/v1/attempts", headers=headers, json=_payload(version))
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["alreadyRecorded"] is True
    assert db.query(QuizAttempt).filter(QuizAttempt.owner_id == owner_id).count() == 1
    assert db.query(ConceptEvidence).filter(ConceptEvidence.owner_id == owner_id).count() == 1


def test_other_users_question_is_not_found(client, db):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id)
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(other_id)}, json=_payload(version)
    )
    assert response.status_code == 404
    assert db.query(QuizAttempt).count() == 0


def test_unsupported_question_type_is_rejected(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id, question_type="essay")
    response = client.post(
        "/api/v1/attempts", headers={"X-User-Id": str(owner_id)}, json=_payload(version)
    )
    assert response.status_code == 422
    assert db.query(QuizAttempt).count() == 0


def test_three_correct_checkpoint_attempts_reach_demonstrated(client, db):
    owner_id = uuid.uuid4()
    version, _ = _seed_question(db, owner_id)
    headers = {"X-User-Id": str(owner_id)}
    third = None
    for index in range(3):
        third = client.post(
            "/api/v1/attempts", headers=headers,
            json=_payload(version, key=f"attempt-{index}", attemptKind="checkpoint"),
        )
        assert third.status_code == 200
    assert third.json()["mastery"]["band"] == "demonstrated"
