import uuid
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.attempt_service import (
    AttemptNotFoundError,
    InvalidAnswerKeyError,
    UnsupportedQuestionTypeError,
    grade_and_record_attempt,
)

router = APIRouter()


class AttemptRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lesson_version_id: uuid.UUID = Field(alias="lessonVersionId")
    question_key: str = Field(alias="questionKey")
    response: Any
    hint_level: int = Field(default=0, ge=0, le=10, alias="hintLevel")
    hints_used: Optional[List[str]] = Field(default=None, alias="hintsUsed")
    elapsed_seconds: int = Field(default=0, ge=0, le=1800, alias="elapsedSeconds")
    attempt_kind: Literal["practice", "checkpoint"] = Field(default="practice", alias="attemptKind")
    sync_idempotency_key: Optional[str] = Field(default=None, alias="syncIdempotencyKey")


@router.post("")
def submit_attempt(
    req: AttemptRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Grades a question attempt on the server, records atomic learning evidence,
    adapts the learning path, and returns an explainable next action.
    """
    try:
        outcome = grade_and_record_attempt(
            db,
            owner_id=owner_id,
            lesson_version_id=req.lesson_version_id,
            question_key=req.question_key,
            response=req.response,
            hint_level=req.hint_level,
            hints_used=req.hints_used,
            elapsed_seconds=req.elapsed_seconds,
            attempt_kind=req.attempt_kind,
            idempotency_key=req.sync_idempotency_key,
        )
    except AttemptNotFoundError:
        raise HTTPException(status_code=404, detail="Question not found for this lesson.")
    except (UnsupportedQuestionTypeError, InvalidAnswerKeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    personal_coach: Optional[str] = None
    if outcome.concept_ids and not outcome.already_recorded:
        from app.services.coach_notes import enqueue_coach_note
        from app.services.pipeline_runner import notify_pipeline

        try:
            enqueue_coach_note(
                db,
                owner_id=owner_id,
                concept_id=str(outcome.concept_ids[0]),
                lesson_version_id=req.lesson_version_id,
                question_key=req.question_key,
                response=req.response,
                is_correct=outcome.is_correct,
                hints_used=len(req.hints_used or []) or req.hint_level,
                elapsed_seconds=req.elapsed_seconds,
            )
            personal_coach = "queued"
            notify_pipeline()
        except Exception:
            personal_coach = None

    return {
        "attemptId": str(outcome.attempt_id),
        "isCorrect": outcome.is_correct,
        "score": outcome.score,
        "correctAnswer": outcome.correct_answer,
        "feedback": outcome.feedback,
        "mastery": outcome.mastery,
        "nextAction": outcome.next_action,
        "coaching": outcome.coaching,
        "alreadyRecorded": outcome.already_recorded,
        "personalCoach": personal_coach,
        "conceptId": str(outcome.concept_ids[0]) if outcome.concept_ids else None,
    }
