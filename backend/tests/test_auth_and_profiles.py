import uuid

from app.models.curriculum import Resource, ResourceRight, ResourceSource
from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def test_profile_read_and_update_without_hosted_auth(client, db):
    user_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=user_id,
            email="student@example.test",
            display_name="Aarav Sharma",
            role="student",
            grade=9,
            board_id="board-cbse",
            preferred_language="en-IN",
        )
    )
    db.commit()

    profile_res = client.get("/api/v1/profile", headers=auth_headers(user_id))
    assert profile_res.status_code == 200
    p_data = profile_res.json()
    assert p_data["id"] == str(user_id)
    assert p_data["displayName"] == "Aarav Sharma"
    assert p_data["grade"] == 9
    assert p_data["boardId"] == "board-cbse"
    assert p_data["preferredLanguage"] == "en-IN"

    update_payload = {
        "displayName": "Aarav S.",
        "subjectsInterested": ["subject-science", "subject-math"],
        "learningGoals": ["CBSE Board Prep", "Concept Mastery"],
        "dailyGoalMinutes": 35,
        "accessibilityPreferences": {"font_size": "large", "reduced_motion": False},
        "onboardingCompleted": True,
        "tourCompleted": True,
    }
    put_res = client.put(
        "/api/v1/profile", json=update_payload, headers=auth_headers(user_id)
    )
    assert put_res.status_code == 200
    up_data = put_res.json()["profile"]
    assert up_data["displayName"] == "Aarav S."
    assert up_data["dailyGoalMinutes"] == 35
    assert up_data["onboardingCompleted"] is True
    assert up_data["tourCompleted"] is True


def test_classroom_creation_and_student_join(client, db):
    teacher_id = uuid.uuid4()
    student_id = uuid.uuid4()
    db.add_all(
        [
            UserProfile(
                id=teacher_id,
                email="teacher@example.test",
                display_name="Teacher One",
                role="teacher",
                grade=10,
                board_id="board-cbse",
                preferred_language="en-IN",
            ),
            UserProfile(
                id=student_id,
                email="student@example.test",
                display_name="Student One",
                role="student",
                grade=10,
                board_id="board-cbse",
                preferred_language="en-IN",
            ),
        ]
    )
    db.commit()

    create_payload = {
        "name": "Class 10 Physics - Advanced",
        "grade": 10,
        "boardId": "board-cbse",
        "subjectScope": "subject-science",
    }
    c_res = client.post(
        "/api/v1/teacher/classrooms",
        json=create_payload,
        headers=auth_headers(teacher_id),
    )
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert "joinCode" in c_data
    join_code = c_data["joinCode"]
    classroom_id = c_data["id"]

    join_res = client.post(
        "/api/v1/teacher/join",
        json={"joinCode": join_code},
        headers=auth_headers(student_id),
    )
    assert join_res.status_code == 200
    j_data = join_res.json()
    assert j_data["status"] in ("joined", "already_member")
    assert j_data["classroomId"] == classroom_id

    matrix_res = client.get(
        f"/api/v1/teacher/classrooms/{classroom_id}/evidence-matrix",
        headers=auth_headers(teacher_id),
    )
    assert matrix_res.status_code == 200
    m_data = matrix_res.json()
    assert [student["studentId"] for student in m_data["students"]] == [str(student_id)]


def test_catalogue_grade_filter_uses_test_inserted_rows(client, db):
    # The disposable database may carry migration-seeded catalogue rows from
    # earlier suites; remove them so this test proves only its own rows return.
    db.query(ResourceRight).delete()
    db.query(Resource).delete()
    db.commit()

    source = ResourceSource(
        id="test-source-catalogue",
        name="Test Source",
        source_type="open_textbook",
        source_url="https://example.test/source",
        verification_status="verified",
        allowed_actions=["link"],
    )
    db.add(source)
    db.flush()
    grade_6 = Resource(
        id="test-resource-grade-6",
        source_id=source.id,
        title="Test Grade 6 Resource",
        board_id="board-cbse",
        grade=6,
        subject_id="subject-science",
        publisher="Test Publisher",
    )
    grade_10 = Resource(
        id="test-resource-grade-10",
        source_id=source.id,
        title="Test Grade 10 Resource",
        board_id="board-cbse",
        grade=10,
        subject_id="subject-science",
        publisher="Test Publisher",
    )
    db.add_all([grade_6, grade_10])
    db.flush()
    db.add_all(
        [
            ResourceRight(
                id="test-right-grade-6",
                resource_id=grade_6.id,
                license_name="CC BY 4.0",
                can_link=True,
            ),
            ResourceRight(
                id="test-right-grade-10",
                resource_id=grade_10.id,
                license_name="CC BY 4.0",
                can_link=True,
            ),
        ]
    )
    db.commit()

    res6 = client.get("/api/v1/catalogue/resources?grade=6")
    assert res6.status_code == 200
    data6 = res6.json()
    assert {row["id"] for row in data6} == {grade_6.id}
    assert all(row["grade"] == 6 for row in data6)

    res10 = client.get("/api/v1/catalogue/resources?grade=10")
    assert res10.status_code == 200
    data10 = res10.json()
    assert {row["id"] for row in data10} == {grade_10.id}
    assert all(row["grade"] == 10 for row in data10)
