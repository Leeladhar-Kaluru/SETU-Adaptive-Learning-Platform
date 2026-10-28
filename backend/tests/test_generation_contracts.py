import copy
import uuid

import pytest

from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson, LessonVersion, Question
from app.services.generation_queue import enqueue_lesson_generation
from app.services.lesson_generator import lesson_generator_service
from app.worker import process_job
from tests.fixtures import evidence_chunks, valid_lesson_package


def _path_and_lesson(db):
    owner_id = uuid.uuid4()
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Cells"}, status="generating",
    )
    db.add(path)
    db.flush()
    lesson = PathLesson(path_id=path.id, lesson_key="lesson_1", title="Cells", sequence=1, status="queued")
    db.add(lesson)
    db.commit()
    return owner_id, path, lesson


def test_validation_rejects_missing_answer_key():
    package = valid_lesson_package()
    package["practice"][0]["answerKey"] = ""
    result = lesson_generator_service.validate_package(package, evidence_chunks())
    assert result["status"] == "rejected"
    assert any(check["name"] == "answer_keys_nonempty" and not check["passed"] for check in result["checks"])


def test_validation_rejects_missing_source_refs():
    package = valid_lesson_package()
    package["sourceRefs"] = []
    result = lesson_generator_service.validate_package(package, evidence_chunks())
    assert result["status"] == "rejected"
    assert any(check["name"] == "source_refs_present" and not check["passed"] for check in result["checks"])


def test_validation_accepts_a_complete_package():
    result = lesson_generator_service.validate_package(valid_lesson_package(), evidence_chunks())
    assert result["status"] == "ready"


def test_enqueue_is_idempotent(db):
    owner_id, path, lesson = _path_and_lesson(db)
    first = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])
    second = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id
    assert db.query(GenerationJob).count() == 1


@pytest.mark.asyncio
async def test_provider_failure_does_not_publish_a_lesson(db, monkeypatch):
    owner_id, path, lesson = _path_and_lesson(db)
    job = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])[0]

    async def failing_generation(**kwargs):
        raise RuntimeError("chat provider unavailable")

    monkeypatch.setattr(lesson_generator_service, "generate_lesson_package", failing_generation)
    await process_job(db, job)
    db.refresh(job)

    assert job.status in ("retry_wait", "failed")
    assert db.query(LessonVersion).filter(LessonVersion.path_lesson_id == lesson.id).count() == 0


@pytest.mark.asyncio
async def test_rejected_package_creates_no_questions(db, monkeypatch):
    owner_id, path, lesson = _path_and_lesson(db)
    job = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])[0]
    package = valid_lesson_package()
    package["practice"][0]["answerKey"] = ""

    async def invalid_generation(**kwargs):
        result = copy.deepcopy(package)
        result["validation"] = lesson_generator_service.validate_package(result, evidence_chunks())
        return result

    monkeypatch.setattr(lesson_generator_service, "generate_lesson_package", invalid_generation)
    await process_job(db, job)
    db.refresh(job)
    db.refresh(lesson)

    versions = db.query(LessonVersion).filter(LessonVersion.path_lesson_id == lesson.id).all()
    assert lesson.status == "failed"
    assert versions and versions[0].validation_status == "rejected"
    assert db.query(Question).count() == 0
