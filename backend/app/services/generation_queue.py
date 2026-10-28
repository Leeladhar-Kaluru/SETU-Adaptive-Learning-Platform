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
