import datetime
import uuid

from app.models.classroom import ClassroomMembership
from app.models.learning import ConceptMasterySnapshot
from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _profile(db, role="student", name=None):
    user_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=user_id,
            email=f"{role}-{user_id.hex[:6]}@example.com",
            display_name=name or f"{role.title()} {user_id.hex[:4]}",
            role=role,
        )
    )
    db.commit()
    return user_id


def _classroom(client, teacher_id):
    response = client.post(
        "/api/v1/teacher/classrooms",
        headers=auth_headers(teacher_id),
        json={
            "name": "Class 9-B Science",
            "grade": 9,
            "boardId": "board-cbse",
            "subjectScope": "subject-science",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot(db, student_id, concept="concept-cell"):
    db.add(
        ConceptMasterySnapshot(
            owner_id=student_id,
            concept_id=concept,
            estimate_band="approaching",
            numeric_estimate=0.6,
            evidence_count=2,
            calculated_at=datetime.datetime.utcnow(),
        )
    )
    db.commit()


def test_roster_join_code_rotation_and_removal(client, db):
    teacher_id = _profile(db, "teacher", "Mrs. Sharma")
    outsider_teacher = _profile(db, "teacher", "Mr. Rao")
    student_id = _profile(db, name="Asha")
    second_student = _profile(db, name="Bilal")
    room = _classroom(client, teacher_id)
    original_code = room["joinCode"]

    assert client.get(
        f"/api/v1/teacher/classrooms/{room['id']}/roster",
        headers=auth_headers(outsider_teacher),
    ).status_code == 404

    joined = client.post(
        "/api/v1/teacher/join",
        headers=auth_headers(student_id),
        json={"joinCode": original_code},
    )
    assert joined.status_code == 200
    assert joined.json()["status"] == "joined"

    roster = client.get(
        f"/api/v1/teacher/classrooms/{room['id']}/roster",
        headers=auth_headers(teacher_id),
    )
    assert roster.status_code == 200
    members = roster.json()["members"]
    assert [(m["studentId"], m["status"]) for m in members] == [(str(student_id), "active")]
    assert members[0]["studentName"] == "Asha"

    rotated = client.post(
        f"/api/v1/teacher/classrooms/{room['id']}/rotate-join-code",
        headers=auth_headers(teacher_id),
    )
    assert rotated.status_code == 200
    new_code = rotated.json()["joinCode"]
    assert new_code != original_code

    stale = client.post(
        "/api/v1/teacher/join",
        headers=auth_headers(second_student),
        json={"joinCode": original_code},
    )
    assert stale.status_code == 404

    fresh = client.post(
        "/api/v1/teacher/join",
        headers=auth_headers(second_student),
        json={"joinCode": new_code},
    )
    assert fresh.status_code == 200
    assert fresh.json()["status"] == "joined"

    removed = client.patch(
        f"/api/v1/teacher/classrooms/{room['id']}/members/{student_id}",
        headers=auth_headers(teacher_id),
        json={"status": "removed"},
    )
    assert removed.status_code == 200
    assert removed.json()["status"] == "removed"

    matrix = client.get(
        f"/api/v1/teacher/classrooms/{room['id']}/evidence-matrix",
        headers=auth_headers(teacher_id),
    ).json()
    assert [row["studentId"] for row in matrix["matrix"]] == [str(second_student)]

    blocked = client.post(
        "/api/v1/teacher/join",
        headers=auth_headers(student_id),
        json={"joinCode": new_code},
    )
    assert blocked.status_code == 403
    assert "removed" in blocked.json()["detail"]

    restored = client.patch(
        f"/api/v1/teacher/classrooms/{room['id']}/members/{student_id}",
        headers=auth_headers(teacher_id),
        json={"status": "active"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    roster = client.get(
        f"/api/v1/teacher/classrooms/{room['id']}/roster",
        headers=auth_headers(teacher_id),
    ).json()
    assert {m["studentId"]: m["status"] for m in roster["members"]} == {
        str(student_id): "active",
        str(second_student): "active",
    }

    unknown = client.patch(
        f"/api/v1/teacher/classrooms/{room['id']}/members/{uuid.uuid4()}",
        headers=auth_headers(teacher_id),
        json={"status": "removed"},
    )
    assert unknown.status_code == 404

    stale_membership = (
        db.query(ClassroomMembership)
        .filter(
            ClassroomMembership.classroom_id == uuid.UUID(room["id"]),
            ClassroomMembership.student_id == student_id,
        )
        .one()
    )
    assert stale_membership.status == "active"


def test_teacher_action_decisions_are_owned_and_explained(client, db):
    teacher_id = _profile(db, "teacher", "Mrs. Sharma")
    other_teacher = _profile(db, "teacher", "Mr. Rao")
    student_id = _profile(db, name="Asha")
    room = _classroom(client, teacher_id)
    _snapshot(db, student_id)
    client.post(
        "/api/v1/teacher/join",
        headers=auth_headers(student_id),
        json={"joinCode": room["joinCode"]},
    )

    body = {
        "classroomId": room["id"],
        "studentId": str(student_id),
        "conceptId": "concept-cell",
        "actionType": "targeted_review",
        "notes": "Review the worked example before the next check.",
    }

    first = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json=body,
    )
    assert first.status_code == 200
    first_id = first.json()["id"]

    assert client.patch(
        f"/api/v1/teacher/actions/{first_id}",
        headers=auth_headers(other_teacher),
        json={"decision": "accept"},
    ).status_code == 404

    accepted = client.patch(
        f"/api/v1/teacher/actions/{first_id}",
        headers=auth_headers(teacher_id),
        json={"decision": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    second = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json=body,
    ).json()
    missing_reason = client.patch(
        f"/api/v1/teacher/actions/{second['id']}",
        headers=auth_headers(teacher_id),
        json={"decision": "override", "notes": " "},
    )
    assert missing_reason.status_code == 422

    overridden = client.patch(
        f"/api/v1/teacher/actions/{second['id']}",
        headers=auth_headers(teacher_id),
        json={
            "decision": "override",
            "notes": "Keep the current unit; the class check moved to Friday.",
        },
    )
    assert overridden.status_code == 200
    assert overridden.json()["status"] == "edited"

    third = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json=body,
    ).json()
    dismissed = client.post(
        f"/api/v1/study/recommendations/{third['id']}/respond",
        headers=auth_headers(student_id),
        json={"decision": "dismiss"},
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"

    override_after_dismiss = client.patch(
        f"/api/v1/teacher/actions/{third['id']}",
        headers=auth_headers(teacher_id),
        json={
            "decision": "override",
            "notes": "This review is required before the practical.",
        },
    )
    assert override_after_dismiss.status_code == 200
    assert override_after_dismiss.json()["status"] == "edited"

    fourth = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json=body,
    ).json()
    fifth = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json=body,
    ).json()
    assert fifth["status"] == "proposed"

    superseded = client.patch(
        f"/api/v1/teacher/actions/{fourth['id']}",
        headers=auth_headers(teacher_id),
        json={"decision": "accept"},
    )
    assert superseded.status_code == 409
