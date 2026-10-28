import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.learning import QuizAttempt, ConceptEvidence, ConceptMasterySnapshot, LessonVersion
from app.services.adaptive_engine import adaptive_engine

router = APIRouter()

class AttemptRequest(BaseModel):
    lesson_version_id: uuid.UUID
    question_id: uuid.UUID
    concept_id: str
    response: Any
    is_correct: bool
    hint_level: int = 0
    hints_used: Optional[List[str]] = None
    elapsed_seconds: int = 0
    sync_idempotency_key: Optional[str] = None

@router.post("")
def submit_attempt(
    req: AttemptRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Submits question attempt, records atomic learning evidence,
    and returns explainable adaptive next action.
    """
    if req.sync_idempotency_key:
        existing = db.query(QuizAttempt).filter(
            QuizAttempt.owner_id == owner_id,
            QuizAttempt.sync_idempotency_key == req.sync_idempotency_key
        ).first()
        if existing:
            return {
                "id": str(existing.id),
                "isCorrect": existing.is_correct,
                "score": existing.score,
                "alreadyRecorded": True
            }

    score = 1.0 if req.is_correct else 0.0
    attempt = QuizAttempt(
        owner_id=owner_id,
        question_id=req.question_id,
        lesson_version_id=req.lesson_version_id,
        response_json=req.response,
        score=score,
        is_correct=req.is_correct,
        hint_level=req.hint_level,
        hints_used=req.hints_used,
        elapsed_seconds=req.elapsed_seconds,
        sync_idempotency_key=req.sync_idempotency_key
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    # Record concept evidence event
    outcome = "correct" if req.is_correct else "incorrect"
    evidence = ConceptEvidence(
        owner_id=owner_id,
        concept_id=req.concept_id,
        source_attempt_id=attempt.id,
        evidence_type="practice_attempt",
        outcome=outcome,
        weight=1.0,
        rationale=f"Attempt with {req.hint_level} hints used"
    )
    db.add(evidence)
    db.commit()

    # Re-calculate mastery for this concept
    all_evidence = db.query(ConceptEvidence).filter(
        ConceptEvidence.owner_id == owner_id,
        ConceptEvidence.concept_id == req.concept_id
    ).all()
    e_records = [{"outcome": e.outcome, "hints_used": req.hint_level} for e in all_evidence]
    mastery = adaptive_engine.calculate_mastery(e_records)

    # Persist or update snapshot
    snapshot = db.query(ConceptMasterySnapshot).filter(
        ConceptMasterySnapshot.owner_id == owner_id,
        ConceptMasterySnapshot.concept_id == req.concept_id
    ).first()

    if not snapshot:
        snapshot = ConceptMasterySnapshot(
            owner_id=owner_id,
            concept_id=req.concept_id,
            estimate_band=mastery["band"],
            numeric_estimate=mastery["score"],
            evidence_count=mastery["evidenceCount"],
            explanation_json=mastery
        )
        db.add(snapshot)
    else:
        snapshot.estimate_band = mastery["band"]
        snapshot.numeric_estimate = mastery["score"]
        snapshot.evidence_count = mastery["evidenceCount"]
        snapshot.explanation_json = mastery

    db.commit()

    # Determine adaptive next action
    next_action = adaptive_engine.determine_next_action(mastery)

    return {
        "attemptId": str(attempt.id),
        "isCorrect": attempt.is_correct,
        "score": attempt.score,
        "mastery": mastery,
        "nextAction": next_action
    }
