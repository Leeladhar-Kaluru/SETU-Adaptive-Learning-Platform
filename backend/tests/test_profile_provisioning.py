import uuid

from app.models.profiles import UserProfile
from app.services.profiles import ensure_profile_from_auth


def test_profile_from_auth_has_no_invented_academic_context(db):
    user_id = uuid.uuid4()
    profile = ensure_profile_from_auth(
        db, user_id, email="new@example.com", display_name="New Learner"
    )
    db.commit()
    db.refresh(profile)
    assert profile.display_name == "New Learner"
    assert profile.grade is None
    assert profile.board_id is None
    assert profile.daily_goal_minutes is None


def test_profile_role_cannot_be_self_escalated(client, db):
    user_id = uuid.uuid4()
    ensure_profile_from_auth(db, user_id, email="student@example.com", display_name="Student")
    response = client.put(
        "/api/v1/profile",
        headers={"X-User-Id": str(user_id)},
        json={"role": "teacher"},
    )
    assert response.status_code == 200
    assert response.json()["profile"]["role"] == "student"
    assert db.get(UserProfile, user_id).role == "student"


def test_synthetic_test_token_is_rejected(client):
    response = client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer test-token-00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


def test_x_user_id_can_be_disabled(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SETU_TEST_AUTH", False)
    response = client.get(
        "/api/v1/profile",
        headers={"X-User-Id": str(uuid.uuid4())},
    )
    assert response.status_code == 401
