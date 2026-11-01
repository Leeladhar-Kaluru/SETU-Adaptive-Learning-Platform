import copy
import datetime
import uuid

import pytest

from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson, LessonVersion, Question
from app.services.generation_queue import enqueue_lesson_generation, requeue_failed_lessons
from app.services.lesson_generator import lesson_generator_service
from app.worker import process_job, refresh_path_status
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
async def test_path_becomes_active_only_when_every_lesson_is_terminal(db, monkeypatch):
    owner_id, path, lesson = _path_and_lesson(db)
    second = PathLesson(path_id=path.id, lesson_key="lesson_2", title="Tissues", sequence=2, status="queued")
    db.add(second)
    db.commit()
    job = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])[0]

    async def valid_generation(**kwargs):
        result = valid_lesson_package()
        result["validation"] = lesson_generator_service.validate_package(result, evidence_chunks())
        return result

    monkeypatch.setattr(lesson_generator_service, "generate_lesson_package", valid_generation)
    await process_job(db, job)
    db.refresh(path)

    assert lesson.status == "ready"
    assert path.status == "generating"

    second.status = "ready"
    refresh_path_status(db, path)
    assert path.status == "active"


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


def _failed_job_for(db, path, lesson):
    key = f"gen_{path.id}_{lesson.id}_v{path.path_version}"
    job = GenerationJob(
        job_type="generate_lesson", owner_id=path.owner_id, path_id=path.id,
        path_version=path.path_version, lesson_id=lesson.id, priority=1,
        status="failed", idempotency_key=key, attempt_count=3,
        not_before=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        safe_error_message="Lesson generation failed after several attempts.",
    )
    db.add(job)
    db.commit()
    return job


def test_requeue_resets_failed_jobs_and_lessons(db):
    owner_id, path, lesson = _path_and_lesson(db)
    job = _failed_job_for(db, path, lesson)
    lesson.status = "failed"
    path.status = "active"
    db.commit()

    count = requeue_failed_lessons(db, owner_id=owner_id, path=path)
    db.refresh(job)
    db.refresh(lesson)
    db.refresh(path)

    assert count == 1
    assert job.status == "queued"
    assert job.attempt_count == 0
    assert job.not_before <= datetime.datetime.utcnow()
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.error_code is None
    assert job.safe_error_message is None
    assert lesson.status == "queued"
    assert path.status == "active"


def test_requeue_preserves_idempotency_and_ignores_ready_jobs(db):
    owner_id, path, lesson = _path_and_lesson(db)
    failed_job = _failed_job_for(db, path, lesson)
    ready_lesson = PathLesson(path_id=path.id, lesson_key="lesson_2", title="Tissues", sequence=2, status="ready")
    db.add(ready_lesson)
    db.commit()
    ready_job = GenerationJob(
        job_type="generate_lesson", owner_id=owner_id, path_id=path.id,
        path_version=path.path_version, lesson_id=ready_lesson.id, priority=1,
        status="ready", idempotency_key=f"gen_{path.id}_{ready_lesson.id}_v{path.path_version}",
    )
    db.add(ready_job)
    db.commit()

    count = requeue_failed_lessons(db, owner_id=owner_id, path=path)
    assert count == 1
    db.refresh(ready_job)
    assert ready_job.status == "ready"

    enqueued = enqueue_lesson_generation(db, owner_id=owner_id, path=path, lessons=[lesson])
    assert enqueued[0].id == failed_job.id
    assert db.query(GenerationJob).count() == 2


def test_requeue_endpoint_is_owner_scoped(client, db):
    owner_id = uuid.uuid4()
    other_owner = uuid.uuid4()
    path = LearningPath(
        owner_id=owner_id, grade=9, subject_id="subject-science",
        outline_json={"title": "Cells"}, status="active",
    )
    db.add(path)
    db.commit()
    path_id = str(path.id)

    response = client.post(
        f"/api/v1/learning-paths/{path_id}/requeue-failed",
        headers={"X-User-Id": str(owner_id)},
    )
    assert response.status_code == 200
    assert response.json()["requeuedJobs"] == 0

    response = client.post(
        f"/api/v1/learning-paths/{path_id}/requeue-failed",
        headers={"X-User-Id": str(other_owner)},
    )
    assert response.status_code == 404
