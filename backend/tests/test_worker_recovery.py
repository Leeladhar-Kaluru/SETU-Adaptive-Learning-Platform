import pytest
import uuid
import datetime
from app.core.database import SessionLocal
from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, PathLesson
from app.worker import claim_next_job, WORKER_ID

@pytest.mark.asyncio
async def test_worker_job_claiming_and_lease_expiry():
    db = SessionLocal()
    owner_uuid = uuid.UUID("a0000000-0000-0000-0000-000000000001")
    path_uuid = uuid.uuid4()
    lesson_uuid = uuid.uuid4()

    try:
        # Create dummy path and lesson
        path = LearningPath(
            id=path_uuid,
            owner_id=owner_uuid,
            grade=9,
            subject_id="SCIENCE",
            status="generating",
            outline_json={"title": "Class 9 Science - Worker Test", "chapters": []}
        )
        db.add(path)

        lesson = PathLesson(
            id=lesson_uuid,
            path_id=path_uuid,
            lesson_key=f"les-{uuid.uuid4().hex[:6]}",
            sequence=1,
            title="Cell Organelles",
            status="queued"
        )
        db.add(lesson)
        db.commit()

        # 1. Enqueue job
        job = GenerationJob(
            id=uuid.uuid4(),
            owner_id=owner_uuid,
            path_id=path_uuid,
            lesson_id=lesson_uuid,
            job_type="lesson_package",
            status="queued",
            priority=1,
            attempt_count=0,
            max_attempts=3,
            idempotency_key=f"idem-{uuid.uuid4().hex}"
        )
        db.add(job)
        db.commit()

        # 2. Claim job
        claimed = await claim_next_job(db, lease_seconds=60)
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.status == "claimed"
        assert claimed.lease_owner == WORKER_ID
        assert claimed.lease_expires_at is not None
        assert claimed.attempt_count == 1

        # 3. Simulate Worker Crash: Job stuck in 'generating' with expired lease
        claimed.status = "generating"
        claimed.lease_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)
        db.commit()

        # 4. New/Restarted Worker claims next job
        # Must reclaim the expired lease and claim it again
        reclaimed = await claim_next_job(db, lease_seconds=120)
        assert reclaimed is not None
        assert reclaimed.id == job.id
        assert reclaimed.status == "claimed"
        assert reclaimed.attempt_count == 2
        # Reclaimed job has new extended lease
        lease_naive = reclaimed.lease_expires_at.replace(tzinfo=None) if reclaimed.lease_expires_at.tzinfo else reclaimed.lease_expires_at
        assert lease_naive > datetime.datetime.utcnow()

    finally:
        # Cleanup
        db.query(GenerationJob).filter(GenerationJob.path_id == path_uuid).delete()
        db.query(PathLesson).filter(PathLesson.path_id == path_uuid).delete()
        db.query(LearningPath).filter(LearningPath.id == path_uuid).delete()
        db.commit()
        db.close()
