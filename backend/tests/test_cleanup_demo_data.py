import json
import uuid

import pytest

from app.models.classroom import Classroom, ClassroomMembership, TeacherAction
from app.models.curriculum import Resource, ResourceRight, ResourceSource
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.doubts import Doubt, SyncEvent
from app.models.jobs import GenerationJob
from app.models.learning import (
    ConceptEvidence,
    ConceptMasterySnapshot,
    LearningPath,
    LessonVersion,
    PathLesson,
    Question,
    QuizAttempt,
    StudyEvent,
)
from app.models.profiles import UserProfile
from scripts.cleanup_demo_data import (
    SEEDED_RESOURCE_IDS,
    cleanup,
    inventory,
    mask_email,
)


def _profile(db, email: str, **kwargs) -> UserProfile:
    profile = UserProfile(
        id=uuid.uuid4(),
        email=email,
        display_name=email.split("@")[0],
        **kwargs,
    )
    db.add(profile)
    db.flush()
    return profile


def _document(db, owner_id, name: str, **kwargs) -> Document:
    document = Document(
        owner_id=owner_id,
        original_filename=name,
        storage_key=f"documents/{owner_id}/{name}",
        mime_type="application/pdf",
        size_bytes=10,
        status="ready",
        **kwargs,
    )
    db.add(document)
    db.flush()
    return document


def test_cleanup_deletes_only_explicitly_named_users(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    real_document = _document(db, real.id, "real.pdf")
    demo_document = _document(db, demo.id, "demo.pdf")
    real_document_id = real_document.id
    demo_document_id = demo_document.id
    db.add_all(
        [
            DocumentPage(
                document_id=real_document.id,
                page_number=1,
                extracted_text="real page",
            ),
            DocumentPage(
                document_id=demo_document.id,
                page_number=1,
                extracted_text="demo page",
            ),
            DocumentChunk(
                document_id=demo_document.id,
                page_start=1,
                page_end=1,
                chunk_index=0,
                text="demo chunk",
                text_hash="a" * 64,
            ),
        ]
    )
    db.commit()

    before = inventory(db)
    assert before["profiles"] == 2

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
        delete_storage_object=lambda bucket, path: True,
    )

    assert report["deleted_users"] == 1
    assert report["preserved_users"] == 1
    assert report["storage_deleted"] == 1
    assert report["storage_failed"] == 0
    assert report["documents"] == 1
    assert report["document_pages"] == 1
    assert report["document_chunks"] == 1
    assert db.get(UserProfile, demo.id) is None
    assert db.get(UserProfile, real.id) is not None
    assert db.query(Document).filter(Document.owner_id == real.id).count() == 1
    assert db.query(Document).filter(Document.owner_id == demo.id).count() == 0
    assert db.query(DocumentPage).filter(DocumentPage.document_id == real_document_id).count() == 1
    assert db.query(DocumentPage).filter(DocumentPage.document_id == demo_document_id).count() == 0


def test_cleanup_refuses_to_delete_a_preserved_user(db):
    real = _profile(db, "real@gmail.com")
    db.commit()
    try:
        cleanup(
            db,
            delete_user_ids={real.id},
            preserve_user_ids={real.id},
            apply=True,
        )
    except ValueError as exc:
        assert "preserved" in str(exc).lower()
    else:
        raise AssertionError("cleanup must refuse to delete a preserved user")


def test_cleanup_refuses_apply_with_an_empty_delete_set(db):
    real = _profile(db, "real@gmail.com")
    db.commit()
    with pytest.raises(ValueError, match="at least one"):
        cleanup(
            db,
            delete_user_ids=set(),
            preserve_user_ids={real.id},
            apply=True,
        )
    assert db.get(UserProfile, real.id) is not None


def test_dry_run_counts_without_deleting(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    _document(db, demo.id, "demo.pdf")
    db.commit()

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=False,
    )

    assert report["applied"] is False
    assert report["deleted_users"] == 0
    assert report["documents"] == 1
    assert db.get(UserProfile, demo.id) is not None
    assert db.query(Document).count() == 1


def test_inventory_masks_emails_and_reports_domains(db):
    _profile(db, "real@gmail.com")
    _profile(db, "demo@example.com")
    _profile(db, "teacher@example.org")
    db.commit()

    result = inventory(db)

    assert result["profiles"] == 3
    assert result["profiles_by_domain"] == {
        "example.com": 1,
        "example.org": 1,
        "gmail.com": 1,
    }
    assert result["storage_objects"] is None
    assert len(result["users"]) == 3
    assert all("***@" in user["email"] for user in result["users"])
    assert any(user["is_test_domain"] is True for user in result["users"])
    assert any(user["is_test_domain"] is False for user in result["users"])
    serialized = json.dumps(result)
    assert "real@gmail.com" not in serialized
    assert "demo@example.com" not in serialized
    assert "teacher@example.org" not in serialized
    assert mask_email("real@gmail.com") == "r***@gmail.com"
    assert mask_email(None) == "***"


def test_inventory_storage_probe_is_optional_and_failure_safe(db):
    _profile(db, "demo@example.com")
    db.commit()

    assert inventory(db, list_storage_objects=lambda: ["one", "two"])["storage_objects"] == 2
    assert inventory(db, list_storage_objects=lambda: 7)["storage_objects"] == 7

    def broken_probe():
        raise RuntimeError("storage unavailable")

    assert inventory(db, list_storage_objects=broken_probe)["storage_objects"] is None


def test_cleanup_records_storage_failure_but_still_deletes_rows(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    demo_document = _document(db, demo.id, "demo.pdf")
    demo_document_id = demo_document.id
    db.commit()

    def broken_storage_delete(bucket, path):
        raise RuntimeError("storage down")

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
        delete_storage_object=broken_storage_delete,
    )

    assert report["storage_deleted"] == 0
    assert report["storage_failed"] == 1
    assert db.get(Document, demo_document_id) is None
    assert db.get(UserProfile, real.id) is not None


def test_cleanup_scopes_classrooms_memberships_and_activity(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    real_classroom = Classroom(
        owner_teacher_id=real.id,
        name="Real classroom",
        grade=9,
        subject_scope="subject-science",
    )
    demo_classroom = Classroom(
        owner_teacher_id=demo.id,
        name="Demo classroom",
        grade=9,
        subject_scope="subject-science",
    )
    db.add_all([real_classroom, demo_classroom])
    db.flush()
    real_classroom_id = real_classroom.id
    demo_classroom_id = demo_classroom.id
    db.add_all(
        [
            ClassroomMembership(classroom_id=real_classroom.id, student_id=demo.id),
            ClassroomMembership(classroom_id=demo_classroom.id, student_id=real.id),
            TeacherAction(
                teacher_id=demo.id,
                classroom_id=real_classroom.id,
                student_id=real.id,
                action_type="custom_note",
                reason_json={"note": "demo"},
            ),
            Doubt(owner_id=demo.id, client_doubt_id="demo-doubt", question_text="demo?"),
            Doubt(owner_id=real.id, client_doubt_id="real-doubt", question_text="real?"),
            StudyEvent(owner_id=demo.id, event_type="lesson_opened"),
            StudyEvent(owner_id=real.id, event_type="lesson_opened"),
            SyncEvent(
                owner_id=demo.id,
                client_event_id="demo-event",
                event_type="attempt_sync",
                payload_json={},
            ),
        ]
    )
    db.commit()

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
    )

    assert report["classrooms"] == 1
    assert report["classroom_memberships"] == 2
    assert report["teacher_actions"] == 1
    assert report["doubts"] == 1
    assert report["study_events"] == 1
    assert report["sync_events"] == 1
    assert db.get(Classroom, real_classroom_id) is not None
    assert db.get(Classroom, demo_classroom_id) is None
    assert db.query(ClassroomMembership).count() == 0
    assert db.query(TeacherAction).count() == 0
    assert db.query(Doubt).filter(Doubt.owner_id == real.id).count() == 1
    assert db.query(Doubt).filter(Doubt.owner_id == demo.id).count() == 0
    assert db.query(StudyEvent).filter(StudyEvent.owner_id == real.id).count() == 1
    assert db.query(SyncEvent).filter(SyncEvent.owner_id == demo.id).count() == 0


def test_cleanup_scopes_concept_evidence_and_mastery(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    db.add_all(
        [
            ConceptEvidence(
                owner_id=demo.id,
                concept_id="concept-demo",
                outcome="correct",
            ),
            ConceptEvidence(
                owner_id=real.id,
                concept_id="concept-real",
                outcome="correct",
            ),
            ConceptMasterySnapshot(
                owner_id=demo.id,
                concept_id="concept-demo",
            ),
            ConceptMasterySnapshot(
                owner_id=real.id,
                concept_id="concept-real",
            ),
        ]
    )
    db.commit()

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
    )

    assert report["concept_evidence"] == 1
    assert report["concept_mastery_snapshots"] == 1
    assert db.query(ConceptEvidence).filter(ConceptEvidence.owner_id == demo.id).count() == 0
    assert db.query(ConceptEvidence).filter(ConceptEvidence.owner_id == real.id).count() == 1
    assert (
        db.query(ConceptMasterySnapshot)
        .filter(ConceptMasterySnapshot.owner_id == demo.id)
        .count()
        == 0
    )
    assert (
        db.query(ConceptMasterySnapshot)
        .filter(ConceptMasterySnapshot.owner_id == real.id)
        .count()
        == 1
    )


def test_cleanup_cascades_learning_path_content_and_jobs(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    path = LearningPath(
        owner_id=demo.id,
        grade=9,
        subject_id="subject-science",
        outline_json={"title": "Demo path"},
        status="active",
    )
    db.add(path)
    db.flush()
    path_id = path.id
    lesson = PathLesson(
        path_id=path.id,
        lesson_key="lesson_1",
        title="Demo lesson",
        sequence=1,
        status="ready",
    )
    db.add(lesson)
    db.flush()
    lesson_id = lesson.id
    version = LessonVersion(
        path_lesson_id=lesson.id,
        version_number=1,
        lesson_package_json={"title": "Demo lesson"},
        validation_status="ready",
    )
    db.add(version)
    db.flush()
    version_id = version.id
    question = Question(
        lesson_version_id=version.id,
        question_key="q1",
        type="short_text",
        prompt_json={"prompt": "Demo?"},
        answer_key_json={"answer": "Demo"},
        concept_ids=["concept-demo"],
    )
    db.add(question)
    db.flush()
    question_id = question.id
    db.add_all(
        [
            GenerationJob(
                owner_id=demo.id,
                path_id=path.id,
                lesson_id=lesson.id,
                idempotency_key="demo-job-1",
            ),
            QuizAttempt(
                owner_id=real.id,
                question_id=question.id,
                lesson_version_id=version.id,
                response_json={"answer": "Demo"},
            ),
        ]
    )
    db.commit()

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
    )

    assert report["learning_paths"] == 1
    assert report["path_lessons"] == 1
    assert report["lesson_versions"] == 1
    assert report["questions"] == 1
    assert report["generation_jobs"] == 1
    assert report["quiz_attempts"] == 1
    assert db.get(LearningPath, path_id) is None
    assert db.get(PathLesson, lesson_id) is None
    assert db.get(LessonVersion, version_id) is None
    assert db.get(Question, question_id) is None
    assert db.query(GenerationJob).count() == 0
    assert db.query(QuizAttempt).count() == 0
    assert db.get(UserProfile, real.id) is not None


def test_cleanup_clears_seeded_resource_references_and_removes_catalogue(db):
    real = _profile(db, "real@gmail.com")
    demo = _profile(db, "demo@example.com")
    db.add(
        ResourceSource(
            id="ncert-portal",
            name="NCERT",
            source_type="portal",
            source_url="https://example.org/ncert",
        )
    )
    db.flush()
    db.add(
        Resource(
            id="res-ncert-sci-9",
            source_id="ncert-portal",
            title="Seeded science resource",
            resource_kind="textbook",
        )
    )
    db.flush()
    db.add(
        ResourceRight(
            id="right-res-ncert-sci-9",
            resource_id="res-ncert-sci-9",
            license_name="Demo licence",
        )
    )
    real_document = _document(
        db, real.id, "real.pdf", resource_id="res-ncert-sci-9"
    )
    demo_document = _document(
        db, demo.id, "demo.pdf", resource_id="res-ncert-sci-9"
    )
    real_document_id = real_document.id
    demo_document_id = demo_document.id
    db.commit()

    report = cleanup(
        db,
        delete_user_ids={demo.id},
        preserve_user_ids={real.id},
        apply=True,
    )

    db.expire_all()
    assert report["resources"] == 1
    assert report["resource_rights"] == 1
    assert report["cleared_document_resource_references"] == 1
    assert db.get(Resource, "res-ncert-sci-9") is None
    assert db.query(ResourceRight).filter_by(resource_id="res-ncert-sci-9").count() == 0
    assert db.get(Document, demo_document_id) is None
    preserved_document = db.get(Document, real_document_id)
    assert preserved_document is not None
    assert preserved_document.resource_id is None


def test_seeded_resource_safety_net_matches_migration_006():
    assert len(SEEDED_RESOURCE_IDS) == 26
    assert len(set(SEEDED_RESOURCE_IDS)) == 26
