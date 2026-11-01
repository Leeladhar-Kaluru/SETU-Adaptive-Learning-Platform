import datetime
import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.ai_provider import ai_provider
from app.models.learning import CoachNote, Question
from app.services.text_sanitize import sanitize_prose

MAX_ATTEMPTS = 3


def enqueue_coach_note(
    db: Session,
    *,
    owner_id: uuid.UUID,
    concept_id: str,
    lesson_version_id: uuid.UUID,
    question_key: str,
    response: Any,
    is_correct: bool,
    hints_used: int,
    elapsed_seconds: int,
) -> CoachNote:
    question = (
        db.query(Question)
        .filter(
            Question.lesson_version_id == lesson_version_id,
            Question.question_key == question_key,
        )
        .first()
    )
    prompt_text = ""
    if question is not None:
        prompt = question.prompt_json or {}
        prompt_text = str(prompt.get("text") or prompt.get("prompt") or "")[:300]
    attempt_snapshot = {
        "attemptId": str(uuid.uuid4()),
        "question": prompt_text,
        "response": str(response)[:300],
        "correctAnswer": str((question.answer_key_json or {}).get("answer") or "")[:200] if question else "",
        "isCorrect": bool(is_correct),
        "hintsUsed": int(hints_used or 0),
        "elapsedSeconds": int(elapsed_seconds or 0),
        "occurredAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    existing = (
        db.query(CoachNote)
        .filter(
            CoachNote.owner_id == owner_id,
            CoachNote.concept_id == concept_id,
            CoachNote.status.in_(["queued", "claimed"]),
        )
        .first()
    )
    if existing is not None:
        request_json = dict(existing.request_json or {})
        attempts = list(request_json.get("attempts") or [])
        attempts.append(attempt_snapshot)
        request_json["attempts"] = attempts[-12:]
        existing.request_json = request_json
        existing.safe_error_message = None
        db.commit()
        return existing

    note = CoachNote(
        owner_id=owner_id,
        concept_id=concept_id,
        status="queued",
        request_json={"attempts": [attempt_snapshot]},
    )
    db.add(note)
    db.commit()
    return note


def claim_next_coach_note(db: Session, worker_id: str, lease_seconds: int = 120) -> Optional[CoachNote]:
    now = datetime.datetime.now(datetime.timezone.utc)
    db.query(CoachNote).filter(
        CoachNote.status == "claimed",
        CoachNote.lease_expires_at < now,
    ).update(
        {"status": "queued", "lease_owner": None, "lease_expires_at": None},
        synchronize_session=False,
    )
    db.commit()

    note = (
        db.query(CoachNote)
        .filter(CoachNote.status == "queued")
        .order_by(CoachNote.created_at.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if note is None:
        return None
    note.status = "claimed"
    note.lease_owner = worker_id
    note.lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
    note.attempt_count = (note.attempt_count or 0) + 1
    db.commit()
    db.refresh(note)
    return note


async def process_coach_note(db: Session, note: CoachNote) -> bool:
    attempts = list((note.request_json or {}).get("attempts") or [])
    if not attempts:
        note.status = "failed"
        note.safe_error_message = "No attempt evidence was attached."
        db.commit()
        return False

    try:
        system = (
            "You are the SETU learning coach. Analyze the student's real recent attempts for ONE "
            "concept and write short, specific, encouraging advice. Reference what the student "
            "actually answered (quote their wrong answer if present), name the likely "
            "misunderstanding, and give one concrete study step. Never invent attempts that are "
            "not listed. Never use LaTeX or markdown. Reply ONLY with JSON: "
            '{"headline": "...", "body": "...", "studyTipTitle": "...", "studyTipBody": "..."}.'
        )
        user = "Recent attempts for this concept:\n" + json.dumps(attempts, ensure_ascii=False, indent=2)
        raw = await ai_provider.generate_chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=600,
            require_complete=True,
        )
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Coach model did not return JSON.")
        parsed = json.loads(raw[start : end + 1])
        content = {
            "headline": sanitize_prose(str(parsed.get("headline") or ""))[:140],
            "body": sanitize_prose(str(parsed.get("body") or ""))[:600],
            "studyTipTitle": sanitize_prose(str(parsed.get("studyTipTitle") or "How to practice this"))[:80],
            "studyTipBody": sanitize_prose(str(parsed.get("studyTipBody") or ""))[:300],
            "analyzedAttempts": len(attempts),
        }
        if len(content["headline"]) < 5 or len(content["body"]) < 10:
            raise ValueError("Coach model returned an empty note.")
        note.content_json = content
        note.status = "ready"
        note.completed_at = datetime.datetime.now(datetime.timezone.utc)
        note.safe_error_message = None
        db.commit()
        return True
    except Exception:
        db.rollback()
        note = db.query(CoachNote).filter(CoachNote.id == note.id).first()
        if note is None:
            return False
        if (note.attempt_count or 0) >= MAX_ATTEMPTS:
            note.status = "failed"
            note.safe_error_message = "The coach could not finish analyzing these attempts."
            note.lease_owner = None
            note.lease_expires_at = None
        else:
            note.status = "queued"
            note.lease_owner = None
            note.lease_expires_at = None
        db.commit()
        return False


def latest_ready_note(db: Session, *, owner_id: uuid.UUID, concept_id: str) -> Optional[Dict[str, Any]]:
    note = (
        db.query(CoachNote)
        .filter(
            CoachNote.owner_id == owner_id,
            CoachNote.concept_id == concept_id,
            CoachNote.status == "ready",
        )
        .order_by(CoachNote.completed_at.desc())
        .first()
    )
    if note is None:
        return None
    return {
        "id": str(note.id),
        "conceptId": note.concept_id,
        "content": note.content_json,
        "completedAt": note.completed_at.isoformat() if note.completed_at else None,
    }
