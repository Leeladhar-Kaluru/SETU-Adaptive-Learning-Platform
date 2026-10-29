import uuid

from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _student(db):
    user_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=user_id,
            email=f"student-{user_id.hex[:6]}@example.com",
            display_name="Asha",
            role="student",
        )
    )
    db.commit()
    return user_id


def test_profile_rejects_an_unknown_board(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(student_id),
        json={"boardId": "board-not-real"},
    )
    assert response.status_code == 422
    assert "board" in response.json()["detail"].lower()


def test_profile_rejects_an_unknown_language(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(student_id),
        json={"preferredLanguage": "xx-XX"},
    )
    assert response.status_code == 422
    assert "language" in response.json()["detail"].lower()


def test_profile_rejects_an_unknown_subject(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(student_id),
        json={"subjectsInterested": ["subject-astrology"]},
    )
    assert response.status_code == 422
    assert "subject" in response.json()["detail"].lower()


def test_profile_rejects_a_grade_outside_classes_6_to_10(client, db):
    student_id = _student(db)
    assert (
        client.put(
            "/api/v1/profile", headers=auth_headers(student_id), json={"grade": 11}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/profile",
            headers=auth_headers(student_id),
            json={"dailyGoalMinutes": 5},
        ).status_code
        == 422
    )


def test_profile_cannot_escalate_its_own_role(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(student_id),
        json={"role": "teacher"},
    )
    assert response.status_code == 200
    assert response.json()["profile"]["role"] == "student"
    assert db.get(UserProfile, student_id).role == "student"


def test_onboarding_cannot_finish_without_academic_context(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(student_id),
        json={"onboardingCompleted": True},
    )
    assert response.status_code == 422
    assert "class" in response.json()["detail"].lower()


def test_valid_academic_context_is_persisted(client, db):
    student_id = _student(db)
    response = client.put(
        "/api/v1/profile",
        headers=auth_headers(student_id),
        json={
            "grade": 9,
            "boardId": "board-cbse",
            "preferredLanguage": "en-IN",
            "subjectsInterested": ["subject-science"],
            "dailyGoalMinutes": 30,
            "onboardingCompleted": True,
        },
    )
    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["grade"] == 9
    assert profile["boardId"] == "board-cbse"
    assert profile["preferredLanguage"] == "en-IN"
    assert profile["onboardingCompleted"] is True


def test_signup_validates_before_calling_supabase(client, monkeypatch):
    called = {"value": False}

    class _ForbiddenClient:
        def __init__(self, *args, **kwargs):
            called["value"] = True
            raise AssertionError("Supabase must not be called for invalid taxonomy")

    monkeypatch.setattr("app.api.v1.auth.httpx.AsyncClient", _ForbiddenClient)
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new@example.com",
            "password": "secret123",
            "displayName": "New Learner",
            "role": "student",
            "grade": 9,
            "boardId": "board-not-real",
        },
    )
    assert response.status_code == 422
    assert called["value"] is False


def test_classroom_requires_available_board_and_subject(client, db):
    teacher_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=teacher_id,
            email=f"teacher-{teacher_id.hex[:6]}@example.com",
            display_name="Teacher Rao",
            role="teacher",
        )
    )
    db.commit()

    base = {"name": "Morning Science", "grade": 9}
    ignored = client.post(
        "/api/v1/teacher/classrooms",
        headers=auth_headers(teacher_id),
        json={**base, "boardId": "board-not-real", "subjectScope": "subject-science"},
    )
    assert ignored.status_code == 422
    assert "board" in ignored.json()["detail"].lower()

    ignored = client.post(
        "/api/v1/teacher/classrooms",
        headers=auth_headers(teacher_id),
        json={**base, "boardId": "board-cbse", "subjectScope": "Mathematics"},
    )
    assert ignored.status_code == 422
    assert "subject" in ignored.json()["detail"].lower()

    created = client.post(
        "/api/v1/teacher/classrooms",
        headers=auth_headers(teacher_id),
        json={**base, "boardId": "board-cbse", "subjectScope": "subject-science"},
    )
    assert created.status_code == 200
    assert created.json()["subjectScope"] == "subject-science"
