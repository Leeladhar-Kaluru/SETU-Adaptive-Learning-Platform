import datetime
import uuid

from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.learning import ConceptEvidence, ConceptMasterySnapshot, StudyEvent
from app.models.profiles import UserProfile
from tests.conftest import auth_headers


def _profile(db, role="student", name=None):
    user_id = uuid.uuid4()
    db.add(UserProfile(
        id=user_id, email=f"{role}-{user_id.hex[:6]}@example.com",
        display_name=name or f"{role.title()} {user_id.hex[:4]}", role=role,
    ))
    db.commit()
    return user_id


def _classroom(db, teacher_id, name="Morning Science"):
    room = Classroom(
        owner_teacher_id=teacher_id, name=name, grade=9,
        board_id="board-cbse", subject_scope="subject-science",
        join_code=f"T{uuid.uuid4().hex[:5].upper()}",
    )
    db.add(room)
    db.commit()
    return room


def _member(db, room, student_id):
    db.add(ClassroomMembership(classroom_id=room.id, student_id=student_id, status="active"))
    db.commit()


def _snapshot(db, student_id, concept="concept-cell", band="demonstrated", count=3):
    db.add(ConceptMasterySnapshot(
        owner_id=student_id, concept_id=concept, estimate_band=band,
        numeric_estimate=0.9, evidence_count=count,
        calculated_at=datetime.datetime.utcnow(),
    ))
    db.commit()


def _evidence(db, student_id, concept="concept-cell", outcome="correct"):
    db.add(ConceptEvidence(owner_id=student_id, concept_id=concept, outcome=outcome))
    db.commit()


def test_teacher_sees_only_own_classroom_evidence(client, db):
    teacher_a, teacher_b = _profile(db, "teacher"), _profile(db, "teacher")
    room_a, room_b = _classroom(db, teacher_a), _classroom(db, teacher_b)
    student_a, student_b = _profile(db, name="Asha"), _profile(db, name="Bilal")
    _member(db, room_a, student_a)
    _member(db, room_b, student_b)
    _snapshot(db, student_a)
    _snapshot(db, student_b, concept="concept-secret", band="developing", count=2)
    _evidence(db, student_a, outcome="correct")
    _evidence(db, student_a, outcome="incorrect")
    _evidence(db, student_b, concept="concept-secret", outcome="incorrect")
    db.add(StudyEvent(owner_id=student_a, event_type="reading", seconds=300, lesson_title="Cells"))
    db.commit()

    response = client.get(
        f"/api/v1/teacher/classrooms/{room_a.id}/evidence-matrix",
        headers=auth_headers(teacher_a),
    )
    assert response.status_code == 200
    matrix = response.json()["matrix"]
    assert [row["studentId"] for row in matrix] == [str(student_a)]
    assert matrix[0]["studentName"] == "Asha"
    assert matrix[0]["evidenceBand"] == "demonstrated"
    assert matrix[0]["concepts"][0]["conceptId"] == "concept-cell"
    assert matrix[0]["minutesStudied"] == 5.0

    scoped = client.get(
        f"/api/v1/teacher/evidence?classroomId={room_a.id}",
        headers=auth_headers(teacher_a),
    )
    assert scoped.status_code == 200
    assert {row["conceptId"] for row in scoped.json()} == {"concept-cell"}
    assert scoped.json()[0]["totalAttempts"] == 2

    assert client.get(
        f"/api/v1/teacher/classrooms/{room_b.id}/evidence-matrix",
        headers=auth_headers(teacher_a),
    ).status_code == 404
    assert client.get(
        f"/api/v1/teacher/evidence?classroomId={room_b.id}",
        headers=auth_headers(teacher_a),
    ).status_code == 404


def test_recommendation_requires_evidence_and_is_respondable(client, db):
    teacher_id = _profile(db, "teacher")
    room = _classroom(db, teacher_id)
    student_id = _profile(db, name="Asha")
    outsider_id = _profile(db, name="Bilal")
    _member(db, room, student_id)
    _snapshot(db, student_id, band="approaching", count=2)
    student_headers = auth_headers(student_id)

    no_evidence = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json={
            "classroomId": str(room.id), "studentId": str(student_id),
            "conceptId": "concept-not-assessed", "actionType": "targeted_review",
            "notes": "Review the worked example.",
        },
    )
    assert no_evidence.status_code == 422

    created = client.post(
        "/api/v1/teacher/recommendations",
        headers=auth_headers(teacher_id),
        json={
            "classroomId": str(room.id), "studentId": str(student_id),
            "conceptId": "concept-cell", "actionType": "targeted_review",
            "notes": "Review the worked example before the next check.",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["status"] == "proposed"
    assert payload["reason"]["evidence"]["band"] == "approaching"
    assert payload["reason"]["evidence"]["evidenceCount"] == 2

    summary = client.get("/api/v1/study/summary", headers=student_headers).json()
    assert summary["suggestions"][0]["status"] == "proposed"
    assert "approaching" in summary["suggestions"][0]["explanation"]
    assert summary["suggestions"][0]["conceptId"] == "concept-cell"

    assert client.post(
        f"/api/v1/study/recommendations/{payload['id']}/respond",
        headers=auth_headers(outsider_id),
        json={"decision": "accept"},
    ).status_code == 404
    assert client.post(
        f"/api/v1/study/recommendations/{payload['id']}/respond",
        headers=student_headers,
        json={"decision": "accept"},
    ).json()["status"] == "accepted"
    assert client.get("/api/v1/study/summary", headers=student_headers).json()["suggestions"] == []


def test_new_recommendation_supersedes_the_previous_one(client, db):
    teacher_id = _profile(db, "teacher")
    room = _classroom(db, teacher_id)
    student_id = _profile(db, name="Asha")
    _member(db, room, student_id)
    _snapshot(db, student_id)

    body = {
        "classroomId": str(room.id), "studentId": str(student_id),
        "conceptId": "concept-cell", "actionType": "reinforce_foundations",
        "notes": "Stay with this unit for one more check.",
    }
    first = client.post("/api/v1/teacher/recommendations", headers=auth_headers(teacher_id), json=body).json()
    second = client.post("/api/v1/teacher/recommendations", headers=auth_headers(teacher_id), json=body).json()

    actions = client.get(
        f"/api/v1/teacher/classrooms/{room.id}/evidence-matrix",
        headers=auth_headers(teacher_id),
    ).json()["actions"]
    statuses = {action["id"]: action["status"] for action in actions}
    assert statuses[first["id"]] == "superseded"
    assert statuses[second["id"]] == "proposed"
