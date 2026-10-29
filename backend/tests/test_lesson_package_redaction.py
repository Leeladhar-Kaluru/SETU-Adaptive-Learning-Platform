import uuid

from app.models.learning import LearningPath, LessonVersion, PathLesson, Question


def _ready_lesson(db, owner_id):
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Cells"}, status="active",
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready")
    db.add(lesson)
    db.flush()
    version = LessonVersion(
        path_lesson_id=lesson.id, version_number=1, validation_status="ready",
        lesson_package_json={
            "title": "Cells", "grade": 9, "subjectId": "subject-science",
            "practice": [{
                "questionId": "q1", "type": "multiple_choice", "prompt": "Choose one",
                "options": ["Cell", "Tissue"], "conceptIds": ["concept-cell"],
                "answerKey": "Cell", "feedback": "The cell is the unit.",
            }],
            "checkpointTest": [{
                "questionId": "t1", "type": "multiple_choice", "prompt": "Choose one",
                "options": ["A", "B"], "conceptIds": ["concept-cell"],
                "answerKey": "B", "feedback": "B is correct.",
            }],
        },
    )
    db.add(version)
    db.flush()
    db.add(Question(
        lesson_version_id=version.id, question_key="q1", type="multiple_choice",
        prompt_json={"text": "Choose one"}, answer_key_json={"answer": "Cell", "feedback": "The cell is the unit."},
        concept_ids=["concept-cell"], validation_status="ready",
    ))
    db.commit()
    return lesson, version


def test_lesson_package_never_exposes_answer_keys(client, db):
    owner_id = uuid.uuid4()
    lesson, version = _ready_lesson(db, owner_id)
    response = client.get(
        f"/api/v1/learning-paths/lessons/{lesson.id}",
        headers={"X-User-Id": str(owner_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["lessonVersionId"] == str(version.id)
    assert "answerKey" not in body["practice"][0]
    assert "answerKey" not in body["checkpointTest"][0]


def test_correct_answer_is_returned_only_after_grading(client, db):
    owner_id = uuid.uuid4()
    _, version = _ready_lesson(db, owner_id)
    response = client.post(
        "/api/v1/attempts",
        headers={"X-User-Id": str(owner_id)},
        json={
            "lessonVersionId": str(version.id), "questionKey": "q1", "response": "Tissue",
            "hintLevel": 0, "hintsUsed": [], "elapsedSeconds": 12,
            "attemptKind": "practice", "syncIdempotencyKey": "redaction-attempt-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["isCorrect"] is False
    assert body["correctAnswer"] == "Cell"
