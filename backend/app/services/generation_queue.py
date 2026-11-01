import datetime
import uuid
from typing import Callable, List

from sqlalchemy.orm import Session

from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson


def enqueue_lesson_generation(
    db: Session,
    *,
    owner_id: uuid.UUID,
    path: LearningPath,
    lessons: List[PathLesson],
    priority_for: Callable[[PathLesson], int] | None = None,
) -> List[GenerationJob]:
    jobs: List[GenerationJob] = []
    for lesson in lessons:
        key = f"gen_{path.id}_{lesson.id}_v{path.path_version}"
        existing = db.query(GenerationJob).filter(GenerationJob.idempotency_key == key).first()
        if existing:
            jobs.append(existing)
            continue
        priority = priority_for(lesson) if priority_for else (1 if lesson.sequence <= 2 else 20 + lesson.sequence)
        job = GenerationJob(
            job_type="generate_lesson", owner_id=owner_id, path_id=path.id,
            path_version=path.path_version, lesson_id=lesson.id, priority=priority,
            status="queued", idempotency_key=key,
        )
        db.add(job)
        jobs.append(job)
    db.commit()
    return jobs


def requeue_failed_lessons(db: Session, *, owner_id: uuid.UUID, path: LearningPath) -> int:
    """Reset the path's failed generation jobs so the worker claims them again.

    Reuses the existing job rows (idempotency keys are preserved), so a
    follow-up ``enqueue_lesson_generation`` can never create duplicates.
    """
    jobs = (
        db.query(GenerationJob)
        .filter(
            GenerationJob.path_id == path.id,
            GenerationJob.owner_id == owner_id,
            GenerationJob.status == "failed",
        )
        .all()
    )
    for job in jobs:
        job.status = "queued"
        job.attempt_count = 0
        job.not_before = datetime.datetime.utcnow()
        job.lease_owner = None
        job.lease_expires_at = None
        job.error_code = None
        job.safe_error_message = None

    lesson_ids = [job.lesson_id for job in jobs]
    if lesson_ids:
        db.query(PathLesson).filter(
            PathLesson.id.in_(lesson_ids),
            PathLesson.status == "failed",
        ).update({"status": "queued"}, synchronize_session=False)
    if path.status == "failed":
        path.status = "generating"
    db.commit()
    return len(jobs)
