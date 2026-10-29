import uuid

from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def test_a_fresh_student_and_teacher_start_empty(client, db):
    student_id = uuid.uuid4()
    teacher_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=student_id,
            email="fresh-student@example.com",
            display_name="Fresh Student",
            role="student",
        )
    )
    db.add(
        UserProfile(
            id=teacher_id,
            email="fresh-teacher@example.com",
            display_name="Fresh Teacher",
            role="teacher",
        )
    )
    db.commit()

    student_headers = auth_headers(student_id)
    teacher_headers = auth_headers(teacher_id)

    assert client.get("/api/v1/documents", headers=student_headers).json() == []
    assert client.get("/api/v1/learning-paths", headers=student_headers).json() == []
    assert client.get("/api/v1/doubts", headers=student_headers).json() == []
    assert client.get("/api/v1/teacher/classrooms", headers=teacher_headers).json() == []
    assert client.get("/api/v1/catalogue/resources").json() == []

    dashboard = client.get("/api/v1/profile/dashboard", headers=student_headers).json()
    assert dashboard["stats"]["totalSessions"] == 0
    assert dashboard["stats"]["totalQuestionsAttempted"] == 0
    assert dashboard["conceptMastery"] == []
    assert dashboard["recentAttempts"] == []
    assert dashboard["classrooms"] == []

    summary = client.get("/api/v1/study/summary", headers=student_headers).json()
    assert summary["minutesStudied"] == 0.0
    assert summary["checkpointCount"] == 0
    assert summary["suggestions"] == []
