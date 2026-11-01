"""SETU Embedded Background Generation Pipeline.

Runs durable background work (document extraction, chunking, embedding,
lesson package generation, validation gates, and coach notes) directly within
the FastAPI process or as a standalone CLI worker.

Adheres strictly to Rule 7: Durable PostgreSQL queue with atomic leases
(FOR UPDATE SKIP LOCKED), bounded exponential backoff, and crash recovery.
"""

import asyncio
import datetime
import logging
import os
import sys
import uuid
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.documents import Document, DocumentChunk
from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, LessonVersion, PathLesson, Question
from app.services.coach_notes import claim_next_coach_note, process_coach_note
from app.services.ingestion import process_claimed_document
from app.services.lesson_generator import lesson_generator_service

logger = logging.getLogger(__name__)

WORKER_ID = f"pipeline-{uuid.uuid4().hex[:8]}"

# Event used to immediately wake the pipeline loop upon upload/job creation
_pipeline_event: Optional[asyncio.Event] = None


def get_pipeline_event() -> asyncio.Event:
    global _pipeline_event
    if _pipeline_event is None:
        _pipeline_event = asyncio.Event()
    return _pipeline_event


def notify_pipeline() -> None:
    """Signals the pipeline runner to immediately claim any newly queued job."""
    evt = get_pipeline_event()
    evt.set()


def _utc_now_naive() -> datetime.datetime:
    """PostgreSQL timestamp without time zone columns require naive UTC."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


async def claim_next_document(db: Session, lease_seconds: int = 600) -> Optional[Document]:
    """Atomically claims the oldest stored document and requeues expired extraction leases."""
    now = _utc_now_naive()
    lease_expires = now + datetime.timedelta(seconds=lease_seconds)

    db.execute(
        text("""
        UPDATE documents
        SET status = 'stored', lease_owner = NULL, lease_expires_at = NULL
        WHERE status IN ('extracting', 'indexing')
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at < :now
          AND COALESCE(attempt_count, 0) < 3
          AND deleted_at IS NULL
    """),
        {"now": now},
    )
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
    doc.lease_expires_at = lease_expires
    db.commit()
    db.refresh(doc)
    return doc


async def claim_next_job(db: Session, lease_seconds: int = 300) -> Optional[GenerationJob]:
    """Atomically claims next queued or expired-lease generation job."""
    now = _utc_now_naive()
    lease_expires = now + datetime.timedelta(seconds=lease_seconds)

    # Reclaim expired leases for jobs stuck in claimed, generating, or validating
    db.execute(
        text("""
        UPDATE generation_jobs 
        SET status = 'queued', lease_owner = NULL, lease_expires_at = NULL 
        WHERE status IN ('claimed', 'generating', 'validating') AND lease_expires_at < :now;
    """),
        {"now": now},
    )
    db.commit()

    job = (
        db.query(GenerationJob)
        .filter(
            GenerationJob.status.in_(["queued", "retry_wait"]),
            func.coalesce(GenerationJob.not_before, GenerationJob.created_at) <= now,
        )
        .order_by(GenerationJob.priority.asc(), GenerationJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )

    if job:
        job.status = "claimed"
        job.lease_owner = WORKER_ID
        job.lease_expires_at = lease_expires
        job.attempt_count += 1
        job.started_at = now
        db.commit()
        db.refresh(job)

    return job


def refresh_path_status(db: Session, path: LearningPath) -> None:
    """Keep the parent path status truthful as lessons reach terminal states."""
    db.flush()
    statuses = [
        row[0]
        for row in db.query(PathLesson.status)
        .filter(PathLesson.path_id == path.id)
        .all()
    ]
    if any(status in ("queued", "generating") for status in statuses):
        path.status = "generating"
    elif any(status == "ready" for status in statuses):
        path.status = "active"
    else:
        path.status = "failed"


async def process_job(db: Session, job: GenerationJob) -> bool:
    """Executes lesson package generation and validation for a claimed job."""
    job_id = job.id
    lesson_id = job.lesson_id
    path_id = job.path_id
    attempt_count = job.attempt_count
    max_attempts = job.max_attempts
    print(f"[{WORKER_ID}] Processing job {job_id} for lesson {lesson_id} (Attempt {attempt_count})")

    lesson = db.query(PathLesson).filter(PathLesson.id == lesson_id).first()
    path = db.query(LearningPath).filter(LearningPath.id == path_id).first()

    if not lesson or not path:
        job.status = "failed"
        job.safe_error_message = "Lesson or Path record not found"
        db.commit()
        return False

    job.status = "generating"
    db.commit()

    # Extract all data needed for generation
    lesson_key = lesson.lesson_key
    lesson_title = lesson.title
    path_id_str = str(path.id)
    path_grade = path.grade
    path_subject = path.subject_id
    document_id = path.document_id
    sequence = lesson.sequence

    chunks = []
    language_tag = "en-IN"
    if document_id:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document and document.language_tag:
            language_tag = document.language_tag
        doc_filename = document.original_filename if document else None

        chapters = (path.outline_json or {}).get("chapters", [])
        chapter_idx = max(0, sequence - 1)
        target_chapter = chapters[chapter_idx] if chapter_idx < len(chapters) else None

        c_query = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)
        if target_chapter and "pageStart" in target_chapter and "pageEnd" in target_chapter:
            p_start = target_chapter["pageStart"]
            p_end = target_chapter["pageEnd"]
            c_rows = (
                c_query.filter(
                    DocumentChunk.page_start <= p_end,
                    DocumentChunk.page_end >= p_start,
                )
                .order_by(DocumentChunk.chunk_index.asc())
                .limit(6)
                .all()
            )
        else:
            c_rows = c_query.order_by(DocumentChunk.chunk_index.asc()).limit(6).all()

        if not c_rows:
            c_rows = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .limit(6)
                .all()
            )

        chunks = [
            {
                "citationId": f"cite_{str(c.id)[:8]}",
                "chunkId": str(c.id),
                "documentVersionId": str(c.document_id),
                "pageStart": c.page_start,
                "pageEnd": c.page_end,
                "headingPath": c.heading_path or [],
                "sourceTitle": doc_filename,
                "text": c.text,
            }
            for c in c_rows
        ]

    # Release DB connection back to the pool while the LLM network request runs
    db.close()

    try:
        package = await lesson_generator_service.generate_lesson_package(
            lesson_id=lesson_key,
            lesson_title=lesson_title,
            path_id=path_id_str,
            grade=path_grade,
            subject=path_subject,
            evidence_chunks=chunks,
            language_tag=language_tag,
        )

        with SessionLocal() as save_db:
            job_rec = save_db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            lesson_rec = save_db.query(PathLesson).filter(PathLesson.id == lesson_id).first()
            path_rec = save_db.query(LearningPath).filter(LearningPath.id == path_id).first()
            if not job_rec or not lesson_rec or not path_rec:
                return False

            job_rec.status = "validating"
            save_db.commit()

            validation_status = package.get("validation", {}).get("status", "draft")

            latest = (
                save_db.query(func.max(LessonVersion.version_number))
                .filter(LessonVersion.path_lesson_id == lesson_rec.id)
                .scalar()
                or 0
            )
            version = LessonVersion(
                path_lesson_id=lesson_rec.id,
                version_number=latest + 1,
                lesson_package_json=package,
                validation_status=validation_status,
            )
            save_db.add(version)
            save_db.commit()

            if validation_status == "ready":
                lesson_rec.status = "ready"
                job_rec.status = "ready"
                job_rec.completed_at = _utc_now_naive()
                refresh_path_status(save_db, path_rec)

                # Insert atomic question records for checks and practice
                all_questions = package.get("practice", []) + package.get("checkpointTest", [])
                for q_idx, q_item in enumerate(all_questions):
                    q_key = q_item.get("questionId") or f"q_{q_idx + 1}"
                    q_prompt = (
                        q_item.get("prompt")
                        if isinstance(q_item.get("prompt"), dict)
                        else {"text": str(q_item.get("prompt") or "")}
                    )
                    q_options = q_item.get("options")
                    if isinstance(q_options, list) and q_options:
                        q_prompt = {**q_prompt, "options": q_options}
                    answer_payload = q_item.get("answerKey")
                    answer_payload = (
                        answer_payload
                        if isinstance(answer_payload, dict)
                        else {"answer": str(answer_payload or "")}
                    )
                    if q_item.get("feedback"):
                        answer_payload["feedback"] = q_item["feedback"]
                    if q_item.get("validator"):
                        answer_payload["validator"] = q_item["validator"]
                    q_concepts = q_item.get("conceptIds") or [lesson_rec.lesson_key]
                    save_db.add(
                        Question(
                            lesson_version_id=version.id,
                            question_key=q_key,
                            type=q_item.get("type") or "multiple_choice",
                            prompt_json=q_prompt,
                            answer_key_json=answer_payload,
                            concept_ids=q_concepts,
                            difficulty=q_item.get("difficulty") or "standard",
                            validation_status="ready",
                        )
                    )
                save_db.commit()
                print(f"[{WORKER_ID}] Job {job_id} completed successfully! Lesson marked READY.")
            else:
                failed_checks = [
                    check["name"]
                    for check in package.get("validation", {}).get("checks", [])
                    if not check.get("passed")
                ]
                lesson_rec.status = "failed"
                job_rec.status = "failed"
                job_rec.error_code = "validation_failed"
                job_rec.safe_error_message = "Lesson validation failed: " + ", ".join(failed_checks[:3])
                refresh_path_status(save_db, path_rec)
                save_db.commit()

        return True

    except Exception as e:
        print(f"[{WORKER_ID}] Job error: {e}")
        with SessionLocal() as err_db:
            job_rec = err_db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            lesson_rec = err_db.query(PathLesson).filter(PathLesson.id == lesson_id).first()
            if job_rec:
                job_rec.error_code = "generation_failed"
                if job_rec.attempt_count < max_attempts:
                    job_rec.status = "retry_wait"
                    backoff_secs = 5 * (2 ** (job_rec.attempt_count - 1))
                    job_rec.not_before = _utc_now_naive() + datetime.timedelta(seconds=backoff_secs)
                    job_rec.safe_error_message = "Lesson generation failed. The worker will retry."
                else:
                    job_rec.status = "failed"
                    job_rec.safe_error_message = "Lesson generation failed after several attempts."
                    if lesson_rec:
                        lesson_rec.status = "failed"
                err_db.commit()
        return False


async def run_pipeline_loop(
    stop_event: Optional[asyncio.Event] = None,
    poll_interval: float = 2.0,
    max_cycles: Optional[int] = None,
) -> None:
    """Core durable execution loop.

    Runs continuous atomic claims against documents, lesson jobs, and coach notes.
    Wakes up immediately when `notify_pipeline()` is invoked.
    """
    print(f"Starting SETU Background Pipeline [{WORKER_ID}]...")
    evt = get_pipeline_event()
    cycles = 0

    while True:
        if stop_event and stop_event.is_set():
            print(f"[{WORKER_ID}] Stopping pipeline gracefully...")
            break

        had_work = False
        db = SessionLocal()
        try:
            # 1. Claim next document
            document = await claim_next_document(db)
            if document:
                had_work = True
                print(f"[{WORKER_ID}] Processing document {document.id} ({document.original_filename})")
                await process_claimed_document(db, document)
            else:
                # 2. Claim next generation job
                job = await claim_next_job(db)
                if job:
                    had_work = True
                    await process_job(db, job)
                else:
                    # 3. Claim next coach note
                    coach_note = claim_next_coach_note(db, WORKER_ID)
                    if coach_note:
                        had_work = True
                        print(f"[{WORKER_ID}] Analyzing attempts for coach note {coach_note.id}")
                        await process_coach_note(db, coach_note)
        except Exception as e:
            print(f"[{WORKER_ID}] Pipeline loop error: {e}")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass

        cycles += 1
        if max_cycles and cycles >= max_cycles:
            break

        if had_work:
            # When work was found, immediately check for next job without sleeping
            await asyncio.sleep(0.05)
        else:
            # When idle, wait on event notification or poll_interval
            try:
                await asyncio.wait_for(evt.wait(), timeout=poll_interval)
                evt.clear()
            except (asyncio.TimeoutError, TimeoutError):
                pass

