import uuid
from app.models.profiles import UserProfile


def test_new_profile_has_no_academic_defaults(db):
    profile = UserProfile(
        id=uuid.uuid4(),
        email="fresh@example.com",
        display_name="Fresh Learner",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    assert profile.grade is None
    assert profile.board_id is None
    assert profile.daily_goal_minutes is None
    assert profile.preferred_language is None


def test_catalogue_resources_are_empty_until_real_data_is_added(client):
    assert client.get("/api/v1/catalogue/resources").json() == []


def test_reference_taxonomy_is_still_available(client):
    boards = client.get("/api/v1/catalogue/boards").json()
    subjects = client.get("/api/v1/catalogue/subjects").json()
    assert any(board["id"] == "board-cbse" for board in boards)
    assert any(subject["id"] == "subject-science" for subject in subjects)
