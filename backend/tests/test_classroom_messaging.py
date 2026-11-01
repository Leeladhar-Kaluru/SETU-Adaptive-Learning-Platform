import uuid

from app.models.classroom import Classroom, ClassroomMembership
from app.models.profiles import UserProfile


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


def _profile(db, user_id, name):
    db.add(UserProfile(id=user_id, display_name=name))
    db.commit()


def _classroom(db, teacher_id, *, name="Grade 9 Science", grade=9, subject_scope="subject-science"):
    classroom = Classroom(
        owner_teacher_id=teacher_id, name=name, grade=grade,
        subject_scope=subject_scope, join_code=f"SETU-{uuid.uuid4().hex[:6].upper()}",
    )
    db.add(classroom)
    db.commit()
    return classroom


def _join(db, classroom, student_id):
    db.add(ClassroomMembership(
        classroom_id=classroom.id, student_id=student_id, role="student", status="active",
    ))
    db.commit()


def test_student_lists_only_joined_classrooms_without_join_code(client, db):
    teacher_id, student_id, other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    _profile(db, teacher_id, "Ms. Rao")
    _profile(db, student_id, "Aarav")
    joined = _classroom(db, teacher_id)
    _classroom(db, teacher_id, name="Grade 8 Maths", grade=8, subject_scope="subject-math")
    _join(db, joined, student_id)

    body = client.get("/api/v1/classroom/me", headers=_headers(student_id)).json()
    assert len(body["classrooms"]) == 1
    entry = body["classrooms"][0]
    assert entry["id"] == str(joined.id)
    assert entry["role"] == "student"
    assert entry["joinCode"] is None
    assert entry["teacherId"] == str(teacher_id)
    assert entry["teacherName"] == "Ms. Rao"

    other = client.get("/api/v1/classroom/me", headers=_headers(other_id)).json()
    assert other["classrooms"] == []


def test_teacher_sees_owned_classrooms_with_join_code(client, db):
    teacher_id = uuid.uuid4()
    _profile(db, teacher_id, "Ms. Rao")
    classroom = _classroom(db, teacher_id)

    body = client.get("/api/v1/classroom/me", headers=_headers(teacher_id)).json()
    assert len(body["classrooms"]) == 1
    entry = body["classrooms"][0]
    assert entry["role"] == "teacher"
    assert entry["joinCode"] == classroom.join_code
    assert entry["teacherName"] == "Ms. Rao"


def test_group_messages_flow_between_members_and_teacher(client, db):
    teacher_id, student_a, student_b, stranger = (uuid.uuid4() for _ in range(4))
    for uid, name in [(teacher_id, "Ms. Rao"), (student_a, "Aarav"), (student_b, "Bina")]:
        _profile(db, uid, name)
    classroom = _classroom(db, teacher_id)
    _join(db, classroom, student_a)
    _join(db, classroom, student_b)

    sent = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a),
        json={"body": "Is the test on Friday?", "kind": "group"},
    )
    assert sent.status_code == 200, sent.text
    message = sent.json()["message"]
    assert message["senderName"] == "Aarav"
    assert message["kind"] == "group"
    assert message["recipientId"] is None

    for viewer in (student_a, student_b, teacher_id):
        body = client.get(
            f"/api/v1/classroom/{classroom.id}/messages", headers=_headers(viewer)
        ).json()
        assert [m["id"] for m in body["messages"]] == [message["id"]]

    stranger_view = client.get(
        f"/api/v1/classroom/{classroom.id}/messages", headers=_headers(stranger)
    )
    assert stranger_view.status_code == 404


def test_direct_messages_are_private_to_sender_and_recipient(client, db):
    teacher_id, student_a, student_b = (uuid.uuid4() for _ in range(3))
    for uid, name in [(teacher_id, "Ms. Rao"), (student_a, "Aarav"), (student_b, "Bina")]:
        _profile(db, uid, name)
    classroom = _classroom(db, teacher_id)
    _join(db, classroom, student_a)
    _join(db, classroom, student_b)

    sent = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a),
        json={"body": "I did not understand the second step.", "kind": "direct", "recipientId": str(teacher_id)},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["message"]["recipientId"] == str(teacher_id)

    teacher_view = client.get(
        f"/api/v1/classroom/{classroom.id}/messages", headers=_headers(teacher_id)
    ).json()
    assert [m["kind"] for m in teacher_view["messages"]] == ["direct"]

    other_student_view = client.get(
        f"/api/v1/classroom/{classroom.id}/messages", headers=_headers(student_b)
    ).json()
    assert other_student_view["messages"] == []


def test_teacher_can_reply_directly_and_student_sees_it(client, db):
    teacher_id, student_a = uuid.uuid4(), uuid.uuid4()
    _profile(db, teacher_id, "Ms. Rao")
    _profile(db, student_a, "Aarav")
    classroom = _classroom(db, teacher_id)
    _join(db, classroom, student_a)

    sent = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(teacher_id),
        json={"body": "Let me explain step two in class tomorrow.", "kind": "direct", "recipientId": str(student_a)},
    )
    assert sent.status_code == 200, sent.text

    view = client.get(
        f"/api/v1/classroom/{classroom.id}/messages", headers=_headers(student_a)
    ).json()
    assert [m["body"] for m in view["messages"]] == ["Let me explain step two in class tomorrow."]


def test_message_guards(client, db):
    teacher_id, student_a, outsider = (uuid.uuid4() for _ in range(3))
    _profile(db, teacher_id, "Ms. Rao")
    _profile(db, student_a, "Aarav")
    classroom = _classroom(db, teacher_id)
    _join(db, classroom, student_a)

    self_message = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a),
        json={"body": "hi", "kind": "direct", "recipientId": str(student_a)},
    )
    assert self_message.status_code == 422

    non_member_recipient = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a),
        json={"body": "hi", "kind": "direct", "recipientId": str(outsider)},
    )
    assert non_member_recipient.status_code == 404

    empty_body = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a),
        json={"body": "   ", "kind": "group"},
    )
    assert empty_body.status_code == 422

    non_member_post = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(outsider),
        json={"body": "hello?", "kind": "group"},
    )
    assert non_member_post.status_code == 404


def test_cursor_returns_only_newer_messages_and_classes_do_not_leak(client, db):
    teacher_id, student_a = uuid.uuid4(), uuid.uuid4()
    _profile(db, teacher_id, "Ms. Rao")
    _profile(db, student_a, "Aarav")
    classroom = _classroom(db, teacher_id)
    other = _classroom(db, teacher_id, name="Grade 8 Maths", grade=8, subject_scope="subject-math")
    _join(db, classroom, student_a)
    _join(db, other, student_a)

    first = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a), json={"body": "first", "kind": "group"},
    )
    assert first.status_code == 200
    client.post(
        f"/api/v1/classroom/{other.id}/messages",
        headers=_headers(student_a), json={"body": "leak?", "kind": "group"},
    )

    body = client.get(
        f"/api/v1/classroom/{classroom.id}/messages", headers=_headers(student_a)
    ).json()
    assert [m["body"] for m in body["messages"]] == ["first"]

    second = client.post(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a), json={"body": "second", "kind": "group"},
    )
    after = second.json()["message"]["createdAt"]
    newer = client.get(
        f"/api/v1/classroom/{classroom.id}/messages",
        headers=_headers(student_a),
        params={"after": after},
    ).json()
    assert newer["messages"] == []
