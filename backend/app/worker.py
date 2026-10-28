import os
import sys
import time
import uuid
import datetime
import asyncio
from typing import Optional

# Ensure backend directory in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.jobs import GenerationJob
from app.models.learning import PathLesson, LessonVersion, LearningPath
from app.models.documents import DocumentChunk
from app.services.lesson_generator import lesson_generator_service

WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"

async def claim_next_job(db, lease_seconds: int = 300) -> Optional[GenerationJob]:
    """
    Atomically claims next queued or expired-lease job using FOR UPDATE SKIP LOCKED.
    """
    now = datetime.datetime.utcnow()
    lease_expires = now + datetime.timedelta(seconds=lease_seconds)

    # Reclaim expired leases
    db.execute(text("""
        UPDATE generation_jobs 
        SET status = 'queued', lease_owner = NULL, lease_expires_at = NULL 
        WHERE status = 'claimed' AND lease_expires_at < :now;
    """), {"now": now})
    db.commit()

    # Claim next job ordered by priority (lower number = higher priority)
    job = db.query(GenerationJob).filter(
        GenerationJob.status == "queued",
        GenerationJob.not_before <= now
    ).order_by(GenerationJob.priority.asc(), GenerationJob.created_at.asc()).with_for_update(skip_locked=True).first()

    if job:
        job.status = "claimed"
        job.lease_owner = WORKER_ID
        job.lease_expires_at = lease_expires
        job.attempt_count += 1
        job.started_at = now
        db.commit()
        db.refresh(job)

    return job

async def process_job(db, job: GenerationJob) -> bool:
    """Executes lesson generation and validation for claimed job."""
    print(f"[{WORKER_ID}] Processing job {job.id} for lesson {job.lesson_id} (Attempt {job.attempt_count})")
    lesson = db.query(PathLesson).filter(PathLesson.id == job.lesson_id).first()
    path = db.query(LearningPath).filter(LearningPath.id == job.path_id).first()

    if not lesson or not path:
        job.status = "failed"
        job.safe_error_message = "Lesson or Path record not found"
        db.commit()
        return False

    try:
        job.status = "generating"
        db.commit()

        # Fetch evidence chunks for this document
        chunks = []
        if path.document_id:
            c_rows = db.query(DocumentChunk).filter(DocumentChunk.document_id == path.document_id).limit(5).all()
            chunks = [
                {
                    "citationId": f"cite_{str(c.id)[:8]}",
                    "chunkId": str(c.id),
                    "documentVersionId": str(c.document_id),
                    "pageStart": c.page_start,
                    "pageEnd": c.page_end,
                    "headingPath": c.heading_path or [],
                    "text": c.text
                }
                for c in c_rows
            ]

        # Generate lesson package
        package = await lesson_generator_service.generate_lesson_package(
            lesson_id=lesson.lesson_key,
            lesson_title=lesson.title,
            path_id=str(path.id),
            grade=path.grade,
            subject=path.subject_id,
            evidence_chunks=chunks
        )

        job.status = "validating"
        db.commit()

        validation_status = package.get("validation", {}).get("status", "draft")
        
        # Save version
        version = LessonVersion(
            path_lesson_id=lesson.id,
            version_number=1,
            lesson_package_json=package,
            validation_status=validation_status
        )
        db.add(version)
        db.commit()

        if validation_status == "ready":
            lesson.status = "ready"
            job.status = "ready"
            job.completed_at = datetime.datetime.utcnow()
            print(f"[{WORKER_ID}] Job {job.id} completed successfully! Lesson marked READY.")
        else:
            lesson.status = "failed"
            job.status = "failed"
            job.safe_error_message = "Lesson validation checks failed"
        
        db.commit()
        return True

    except Exception as e:
        print(f"[{WORKER_ID}] Job error: {e}")
        db.rollback()
        if job.attempt_count < job.max_attempts:
            job.status = "retry_wait"
            # Exponential backoff: 5s, 10s, 20s
            backoff_secs = 5 * (2 ** (job.attempt_count - 1))
            job.not_before = datetime.datetime.utcnow() + datetime.timedelta(seconds=backoff_secs)
            job.safe_error_message = str(e)[:400]
        else:
            job.status = "failed"
            job.safe_error_message = f"Max attempts ({job.max_attempts}) exceeded. Error: {str(e)[:300]}"
            if lesson:
                lesson.status = "failed"
        db.commit()
        return False

async def run_worker_loop(poll_interval: float = 2.0, max_cycles: Optional[int] = None):
    print(f"Starting SETU Background Worker [{WORKER_ID}]...")
    cycles = 0
    while True:
        db = SessionLocal()
        try:
            job = await claim_next_job(db)
            if job:
                await process_job(db, job)
            else:
                await asyncio.sleep(poll_interval)
        except Exception as e:
            print(f"Worker loop error: {e}")
            await asyncio.sleep(poll_interval)
        finally:
            db.close()

        cycles += 1
        if max_cycles and cycles >= max_cycles:
            break

if __name__ == "__main__":
    asyncio.run(run_worker_loop())
