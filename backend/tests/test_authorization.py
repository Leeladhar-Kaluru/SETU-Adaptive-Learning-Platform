import uuid
from pathlib import Path

from app.models.documents import Document
from app.models.learning import LearningPath, PathLesson, LessonVersion
from app.models.profiles import UserProfile


def _profile(db, role="student"):
    user_id = uuid.uuid4()
    db.add(UserProfile(
        id=user_id, email=f"{role}-{user_id.hex[:6]}@example.com",
        display_name=f"{role.title()} User", role=role,
    ))
    db.commit()
    return user_id


def test_student_cannot_call_teacher_endpoint(client, db):
    student_id = _profile(db, "student")
    response = client.get("/api/v1/teacher/classrooms", headers={"X-User-Id": str(student_id)})
    assert response.status_code == 403


def test_teacher_can_create_a_real_join_code(client, db):
    teacher_id = _profile(db, "teacher")
    response = client.post(
        "/api/v1/teacher/classrooms",
        headers={"X-User-Id": str(teacher_id)},
        json={"name": "Morning Science", "grade": 9, "boardId": "board-cbse", "subjectScope": "subject-science"},
    )
    assert response.status_code == 200
    code = response.json()["joinCode"]
    assert code != "SETU-JOIN"
    assert 5 <= len(code) <= 6


def test_lesson_is_not_readable_by_another_user(client, db, tmp_path):
    owner_id = _profile(db)
    other_id = _profile(db)
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Test path"}, status="active",
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="ready")
    db.add(lesson)
    db.flush()
    db.add(LessonVersion(
        path_lesson_id=lesson.id, version_number=1,
        lesson_package_json={"title": "Cells"}, validation_status="ready",
    ))
    db.commit()

    owner_response = client.get(
        f"/api/v1/learning-paths/lessons/{lesson.id}", headers={"X-User-Id": str(owner_id)}
    )
    other_response = client.get(
        f"/api/v1/learning-paths/lessons/{lesson.id}", headers={"X-User-Id": str(other_id)}
    )
    assert owner_response.status_code == 200
    assert other_response.status_code == 404


def test_diagram_requires_document_owner(client, db):
    owner_id = _profile(db)
    other_id = _profile(db)
    doc = Document(
        owner_id=owner_id, original_filename="book.pdf", storage_key="documents/book.pdf",
        mime_type="application/pdf", size_bytes=10, status="awaiting_review",
    )
    db.add(doc)
    db.commit()

    diagram_dir = Path(__file__).resolve().parents[1] / "diagrams" / str(doc.id)
    diagram_dir.mkdir(parents=True, exist_ok=True)
    diagram = diagram_dir / "page_1_d0.png"
    diagram.write_bytes(b"\x89PNG\r\n\x1a\n")

    assert client.get(
        f"/api/v1/documents/{doc.id}/diagrams/page_1_d0.png",
        headers={"X-User-Id": str(other_id)},
    ).status_code == 404
    assert client.get(
        f"/api/v1/documents/{doc.id}/diagrams/page_1_d0.png",
        headers={"X-User-Id": str(owner_id)},
    ).status_code == 200
    diagram.unlink()
    diagram_dir.rmdir()
