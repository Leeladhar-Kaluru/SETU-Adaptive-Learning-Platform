import datetime
import uuid

from app.models.learning import (
    LearningPath,
    PathLesson,
    LessonVersion,
    Question,
    QuizAttempt,
    StudyEvent,
)
from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _student(db, name="Asha"):
    user_id = uuid.uuid4()
    db.add(UserProfile(id=user_id, email=f"{name.lower()}@example.com", display_name=name, role="student"))
    db.commit()
    return user_id


def test_dashboard_and_profile_require_a_real_row(client, db):
    stranger = uuid.uuid4()
    assert client.get("/api/v1/profile/dashboard", headers=auth_headers(stranger)).status_code == 404
    assert client.get("/api/v1/profile", headers=auth_headers(stranger)).status_code == 404
    assert client.put(
        "/api/v1/profile", headers=auth_headers(stranger), json={"displayName": "Invented"}
    ).status_code == 404


def test_fresh_student_dashboard_has_no_invented_history(client, db):
    student_id = _student(db)
    response = client.get("/api/v1/profile/dashboard", headers=auth_headers(student_id))
    assert response.status_code == 200
    data = response.json()

    assert data["profile"]["grade"] is None
    assert data["profile"]["boardId"] is None
    assert data["profile"]["dailyGoalMinutes"] is None
    assert data["profile"]["academicContextComplete"] is False
    assert data["stats"] == {
        "currentStreak": 0,
        "longestStreak": 0,
        "totalMinutesStudied": 0.0,
        "totalSessions": 0,
        "averageAccuracy": 0.0,
        "totalQuestionsAttempted": 0,
    }
    assert len(data["activityHeatmap"]) == 84
    assert all(day["minutes"] == 0 and day["level"] == 0 for day in data["activityHeatmap"])
    assert data["conceptMastery"] == []
    assert data["recentAttempts"] == []
    assert data["classrooms"] == []


def test_attempt_time_is_not_added_to_study_time_twice(client, db):
    student_id = _student(db)
    db.add(StudyEvent(owner_id=student_id, event_type="reading", seconds=120))
    path = LearningPath(owner_id=student_id, grade=9, subject_id="subject-science", outline_json={"title": "Cells"})
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1)
    db.add(lesson)
    db.flush()
    version = LessonVersion(path_lesson_id=lesson.id, lesson_package_json={"title": "Cells"}, validation_status="ready")
    db.add(version)
    db.flush()
    question = Question(
        lesson_version_id=version.id, question_key="q1", type="multiple_choice",
        prompt_json={"prompt": "Which unit?"}, answer_key_json={"correct": "Cell"}, concept_ids=["concept-cell"],
    )
    db.add(question)
    db.flush()
    db.add(QuizAttempt(
        owner_id=student_id, question_id=question.id, lesson_version_id=version.id,
        response_json={"answer": "Cell"}, score=1.0, is_correct=True, elapsed_seconds=75,
    ))
    db.commit()

    data = client.get("/api/v1/profile/dashboard", headers=auth_headers(student_id)).json()
    assert data["stats"]["totalMinutesStudied"] == 2.0
    assert data["stats"]["totalSessions"] == 1
    assert data["recentAttempts"][0]["elapsedSeconds"] == 75
    today = datetime.datetime.utcnow().date().isoformat()
    today_row = next(day for day in data["activityHeatmap"] if day["date"] == today)
    assert today_row["minutes"] == 2.0


def test_duplicate_profile_study_event_route_is_removed(client, db):
    student_id = _student(db)
    response = client.post(
        "/api/v1/profile/study-event",
        headers=auth_headers(student_id),
        json={"eventType": "reading", "seconds": 60},
    )
    assert response.status_code == 404


def test_study_summary_does_not_invent_a_pace_or_goal(client, db):
    student_id = _student(db)
    summary = client.get("/api/v1/study/summary", headers=auth_headers(student_id)).json()
    assert summary["pace"] is None
    assert summary["dailyGoalMinutes"] is None
    assert "25" not in summary["focus"]
    assert summary["minutesStudied"] == 0.0
