import uuid

from app.models.classroom import ClassroomMembership
from app.models.learning import (
    ConceptMasterySnapshot,
    LearningPath,
    LessonVersion,
    PathLesson,
    Question,
)
from app.models.profiles import UserProfile
from tests.conftest import auth_headers

CONCEPT = "concept-chemical-reactions"


def _profile(db, role="student", name="Student"):
    user_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=user_id,
            email=f"{role}-{user_id.hex[:6]}@example.com",
            display_name=name,
            role=role,
            grade=10,
            board_id="board-cbse",
            preferred_language="en-IN",
        )
    )
    db.commit()
    return user_id


def _seed_question(db, owner_id, title="Chemical Reactions"):
    path = LearningPath(
        owner_id=owner_id,
        grade=10,
        subject_id="subject-science",
        outline_json={"title": title, "chapters": []},
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(
        path_id=path.id,
        lesson_key=f"chem_{uuid.uuid4().hex[:6]}",
        title=title,
        sequence=1,
        status="ready",
    )
    db.add(lesson)
    db.flush()
    version = LessonVersion(
        path_lesson_id=lesson.id,
        version_number=1,
        lesson_package_json={"title": title},
        validation_status="ready",
    )
    db.add(version)
    db.flush()
    db.add(
        Question(
            lesson_version_id=version.id,
            question_key="q1",
            type="multiple_choice",
            prompt_json={"text": "What happens when magnesium ribbon burns in air?"},
            answer_key_json={"answer": "c", "feedback": "Magnesium burns with a white flame."},
            concept_ids=[CONCEPT],
            validation_status="ready",
        )
    )
    db.commit()
    return path, lesson, version


def _attempt(client, student_id, version, *, response, key, kind="checkpoint"):
    result = client.post(
        "/api/v1/attempts",
        headers=auth_headers(student_id),
        json={
            "lessonVersionId": str(version.id),
            "questionKey": "q1",
            "response": response,
            "hintLevel": 0,
            "hintsUsed": [],
            "elapsedSeconds": 45,
            "attemptKind": kind,
            "syncIdempotencyKey": key,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_multi_user_evidence_matrix_tracks_real_server_graded_attempts(client, db):
    teacher_id = _profile(db, "teacher", "Mrs. Sharma")
    aarav_id = _profile(db, name="Aarav Patel")
    diya_id = _profile(db, name="Diya Rao")
    rohan_id = _profile(db, name="Rohan Gupta")

    classroom = client.post(
        "/api/v1/teacher/classrooms",
        headers=auth_headers(teacher_id),
        json={
            "name": "Class 10-A Science",
            "grade": 10,
            "boardId": "board-cbse",
            "subjectScope": "subject-science",
        },
    )
    assert classroom.status_code == 200, classroom.text
    room = classroom.json()
    assert room["subjectScope"] == "subject-science"
    assert room["joinCode"]

    for student_id, name in [(aarav_id, "Aarav"), (diya_id, "Diya"), (rohan_id, "Rohan")]:
        joined = client.post(
            "/api/v1/teacher/join",
            headers=auth_headers(student_id),
            json={"joinCode": room["joinCode"]},
        )
        assert joined.status_code == 200, f"{name} join failed: {joined.text}"
        assert joined.json()["status"] == "joined"

    assert (
        db.query(ClassroomMembership)
        .filter(ClassroomMembership.classroom_id == uuid.UUID(room["id"]))
        .count()
        == 3
    )

    aarav_path, _, aarav_version = _seed_question(db, aarav_id)
    diya_path, diya_lesson, diya_version = _seed_question(db, diya_id)
    rohan_path, _, rohan_version = _seed_question(db, rohan_id)

    for index in range(3):
        result = _attempt(
            client, aarav_id, aarav_version,
            response="c", key=f"aarav-{index}",
        )
        assert result["isCorrect"] is True
    assert result["mastery"]["band"] == "demonstrated"

    first_wrong = _attempt(
        client, diya_id, diya_version,
        response="a", key="diya-0",
    )
    assert first_wrong["isCorrect"] is False
    second_wrong = _attempt(
        client, diya_id, diya_version,
        response="b", key="diya-1",
    )
    assert second_wrong["isCorrect"] is False
    assert second_wrong["mastery"]["band"] == "developing"
    assert second_wrong["nextAction"]["remediationInjected"] is True

    remediation = (
        db.query(PathLesson)
        .filter(
            PathLesson.path_id == diya_path.id,
            PathLesson.lesson_key.like("rem_%"),
        )
        .first()
    )
    assert remediation is not None
    assert remediation.sequence == diya_lesson.sequence + 1
    assert "Foundations & Guided Refresher" in remediation.title
    assert remediation.status == "queued"

    for index, response in enumerate(["b", "c", "c"]):
        result = _attempt(
            client, rohan_id, rohan_version,
            response=response, key=f"rohan-{index}",
        )
    assert result["mastery"]["band"] == "approaching"

    matrix_response = client.get(
        f"/api/v1/teacher/classrooms/{room['id']}/evidence-matrix",
        headers=auth_headers(teacher_id),
    )
    assert matrix_response.status_code == 200, matrix_response.text
    matrix = matrix_response.json()
    assert matrix["totalStudents"] == 3
    rows = {row["studentId"]: row for row in matrix["matrix"]}

    assert rows[str(aarav_id)]["studentName"] == "Aarav Patel"
    assert rows[str(aarav_id)]["evidenceBand"] == "demonstrated"
    assert rows[str(diya_id)]["evidenceBand"] == "developing"
    assert rows[str(rohan_id)]["evidenceBand"] == "approaching"
    assert rows[str(diya_id)]["concepts"] == [
        {
            "conceptId": CONCEPT,
            "band": "developing",
            "score": 0.0,
            "evidenceCount": 2,
            "calculatedAt": rows[str(diya_id)]["concepts"][0]["calculatedAt"],
        }
    ]

    scoped_evidence = client.get(
        f"/api/v1/teacher/evidence?classroomId={room['id']}",
        headers=auth_headers(teacher_id),
    )
    assert scoped_evidence.status_code == 200
    concept_row = scoped_evidence.json()[0]
    assert concept_row["conceptId"] == CONCEPT
    assert concept_row["totalAttempts"] == 8
    assert concept_row["correctAttempts"] == 5
    assert concept_row["incorrectAttempts"] == 3

    recommendation = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json={
            "classroomId": room["id"],
            "studentId": str(diya_id),
            "conceptId": CONCEPT,
            "actionType": "targeted_review",
            "notes": "Review foundational chemical equations before the next check.",
        },
    )
    assert recommendation.status_code == 200, recommendation.text
    recommendation_body = recommendation.json()
    assert recommendation_body["status"] == "proposed"
    assert recommendation_body["reason"]["evidence"]["band"] == "developing"
    assert recommendation_body["reason"]["evidence"]["evidenceCount"] == 2

    summary = client.get("/api/v1/study/summary", headers=auth_headers(diya_id)).json()
    suggestion = summary["suggestions"][0]
    assert suggestion["id"] == recommendation_body["id"]
    assert suggestion["status"] == "proposed"
    assert suggestion["conceptId"] == CONCEPT
    assert suggestion["teacherName"] == "Mrs. Sharma"
    assert "developing" in suggestion["explanation"]

    dashboard_response = client.get(
        "/api/v1/profile/dashboard", headers=auth_headers(diya_id)
    )
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["profile"]["displayName"] == "Diya Rao"
    assert dashboard["stats"]["currentStreak"] >= 1
    assert dashboard["stats"]["totalQuestionsAttempted"] == 2
    assert [room_row["name"] for room_row in dashboard["classrooms"]] == ["Class 10-A Science"]
    assert dashboard["profile"]["dailyGoalMinutes"] is None

    mastery = next(
        item for item in dashboard["conceptMastery"] if item["conceptId"] == CONCEPT
    )
    assert mastery["band"] == "developing"
    assert mastery["needsRemediation"] is True
    assert any(day["count"] > 0 for day in dashboard["activityHeatmap"])

    responded = client.post(
        f"/api/v1/study/recommendations/{recommendation_body['id']}/respond",
        headers=auth_headers(diya_id),
        json={"decision": "accept"},
    )
    assert responded.status_code == 200
    assert responded.json()["status"] == "accepted"
    assert client.get("/api/v1/study/summary", headers=auth_headers(diya_id)).json()[
        "suggestions"
    ] == []

    assert (
        db.query(ConceptMasterySnapshot)
        .filter(ConceptMasterySnapshot.owner_id == aarav_id)
        .count()
        == 1
    )
    assert aarav_path.owner_id == aarav_id
    assert rohan_path.owner_id == rohan_id
