import os
import sys
import time
import uuid
import datetime
import asyncio
from typing import Optional

# Ensure backend directory in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text, func
from app.core.database import SessionLocal
from app.models.jobs import GenerationJob
from app.models.learning import PathLesson, LessonVersion, LearningPath
from app.models.documents import Document, DocumentChunk
from app.services.ingestion import process_claimed_document
from app.services.lesson_generator import lesson_generator_service

WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"

async def claim_next_document(db, lease_seconds: int = 600) -> Optional[Document]:
    """Claims the oldest stored document, and requeues expired extraction leases."""
    now = datetime.datetime.now(datetime.timezone.utc)
    db.execute(text("""
        UPDATE documents
        SET status = 'stored', lease_owner = NULL, lease_expires_at = NULL
        WHERE status IN ('extracting', 'indexing')
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at < :now
          AND COALESCE(attempt_count, 0) < 3
          AND deleted_at IS NULL
    """), {"now": now})
    db.commit()

    doc = (
        db.query(Document)
        .filter(Document.status == "stored", Document.deleted_at.is_(None))
        .order_by(Document.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if not doc:
        return None

    doc.attempt_count = (doc.attempt_count or 0) + 1
    if doc.attempt_count > 3:
        doc.status = "failed"
        doc.safe_error_message = "Processing failed after several attempts."
        doc.error_code = "attempt_limit"
        doc.lease_owner = None
        doc.lease_expires_at = None
        db.commit()
        return None

    doc.status = "extracting"
    doc.lease_owner = WORKER_ID
    doc.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
    db.commit()
    db.refresh(doc)
    return doc


async def claim_next_job(db, lease_seconds: int = 300) -> Optional[GenerationJob]:
    """
    Atomically claims next queued or expired-lease job using FOR UPDATE SKIP LOCKED.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    lease_expires = now + datetime.timedelta(seconds=lease_seconds)

    # Reclaim expired leases for jobs stuck in claimed, generating, or validating
    db.execute(text("""
        UPDATE generation_jobs 
        SET status = 'queued', lease_owner = NULL, lease_expires_at = NULL 
        WHERE status IN ('claimed', 'generating', 'validating') AND lease_expires_at < :now;
    """), {"now": now})
    db.commit()

    # Claim next job ordered by priority (lower number = higher priority)
    job = db.query(GenerationJob).filter(
        GenerationJob.status.in_(["queued", "retry_wait"]),
        func.coalesce(GenerationJob.not_before, GenerationJob.created_at) <= now
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

        # Fetch evidence chunks for this specific lesson based on chapter page range
        chunks = []
        if path.document_id:
            chapters = (path.outline_json or {}).get("chapters", [])
            chapter_idx = max(0, lesson.sequence - 1)
            target_chapter = chapters[chapter_idx] if chapter_idx < len(chapters) else None
            
            c_query = db.query(DocumentChunk).filter(DocumentChunk.document_id == path.document_id)
            if target_chapter and "pageStart" in target_chapter and "pageEnd" in target_chapter:
                p_start = target_chapter["pageStart"]
                p_end = target_chapter["pageEnd"]
                # Match chunks that overlap with this chapter's pages
                c_rows = (
                    c_query.filter(
                        DocumentChunk.page_start <= p_end,
                        DocumentChunk.page_end >= p_start
                    )
                    .order_by(DocumentChunk.chunk_index.asc())
                    .limit(6)
                    .all()
                )
            else:
                c_rows = c_query.order_by(DocumentChunk.chunk_index.asc()).limit(6).all()

            if not c_rows:
                c_rows = db.query(DocumentChunk).filter(DocumentChunk.document_id == path.document_id).limit(6).all()

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
        latest = (
            db.query(func.max(LessonVersion.version_number))
            .filter(LessonVersion.path_lesson_id == lesson.id)
            .scalar()
            or 0
        )
        version = LessonVersion(
            path_lesson_id=lesson.id,
            version_number=latest + 1,
            lesson_package_json=package,
            validation_status=validation_status
        )
        db.add(version)
        db.commit()

        if validation_status == "ready":
            lesson.status = "ready"
            job.status = "ready"
            job.completed_at = datetime.datetime.now(datetime.timezone.utc)

            # Insert question records into database for checkpoint tests and practice
            from app.models.learning import Question
            all_questions = package.get("practice", []) + package.get("checkpointTest", [])
            for q_idx, q_item in enumerate(all_questions):
                q_key = q_item.get("questionId") or f"q_{q_idx + 1}"
                q_prompt = q_item.get("prompt") if isinstance(q_item.get("prompt"), dict) else {"text": str(q_item.get("prompt") or "")}
                answer_payload = q_item.get("answerKey")
                answer_payload = answer_payload if isinstance(answer_payload, dict) else {"answer": str(answer_payload or "")}
                if q_item.get("feedback"):
                    answer_payload["feedback"] = q_item["feedback"]
                if q_item.get("validator"):
                    answer_payload["validator"] = q_item["validator"]
                q_concepts = q_item.get("conceptIds") or [lesson.lesson_key]
                db.add(Question(
                    lesson_version_id=version.id,
                    question_key=q_key,
                    type=q_item.get("type") or "multiple_choice",
                    prompt_json=q_prompt,
                    answer_key_json=answer_payload,
                    concept_ids=q_concepts,
                    difficulty=q_item.get("difficulty") or "standard",
                    validation_status="ready"
                ))
            db.commit()

            print(f"[{WORKER_ID}] Job {job.id} completed successfully! Lesson marked READY.")
        else:
            failed_checks = [
                check["name"] for check in package.get("validation", {}).get("checks", [])
                if not check.get("passed")
            ]
            lesson.status = "failed"
            job.status = "failed"
            job.error_code = "validation_failed"
            job.safe_error_message = "Lesson validation failed: " + ", ".join(failed_checks[:3])
        
        db.commit()
        return True

    except Exception as e:
        print(f"[{WORKER_ID}] Job error: {e}")
        db.rollback()
        job.error_code = "generation_failed"
        if job.attempt_count < job.max_attempts:
            job.status = "retry_wait"
            # Exponential backoff: 5s, 10s, 20s
            backoff_secs = 5 * (2 ** (job.attempt_count - 1))
            job.not_before = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=backoff_secs)
            job.safe_error_message = "Lesson generation failed. The worker will retry."
        else:
            job.status = "failed"
            job.safe_error_message = "Lesson generation failed after several attempts."
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
            document = await claim_next_document(db)
            if document:
                print(f"[{WORKER_ID}] Reading document {document.id} ({document.original_filename})")
                await process_claimed_document(db, document)
            else:
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

