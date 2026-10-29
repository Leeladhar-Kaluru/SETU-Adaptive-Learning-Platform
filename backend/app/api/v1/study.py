import datetime
import uuid
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.classroom import TeacherAction
from app.models.learning import StudyEvent
from app.models.profiles import UserProfile

router = APIRouter()


class StudyEventCreate(BaseModel):
    eventType: str = Field(pattern="^(reading|checkpoint)$")
    pathId: Optional[str] = None
    lessonId: Optional[str] = None
    lessonTitle: Optional[str] = None
    seconds: int = 0
    score: Optional[float] = None


def _as_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def summarize_student(db: Session, owner_id: uuid.UUID) -> dict:
    events = (
        db.query(StudyEvent)
        .filter(StudyEvent.owner_id == owner_id)
        .order_by(StudyEvent.occurred_at.asc())
        .all()
    )
    total_seconds = sum(event.seconds or 0 for event in events)
    checkpoints = [event for event in events if event.event_type == "checkpoint" and event.score is not None]
    readings = [event for event in events if event.event_type == "reading" and event.lesson_title]

    improvement = "not_enough"
    accuracy = None
    if checkpoints:
        scores = [event.score for event in checkpoints]
        accuracy = sum(scores) / len(scores)
        if len(scores) >= 2:
            midpoint = max(1, len(scores) // 2)
            earlier = sum(scores[:midpoint]) / midpoint
            later = sum(scores[midpoint:]) / max(1, len(scores) - midpoint)
            if later >= earlier + 0.1:
                improvement = "improving"
            elif later <= earlier - 0.1:
                improvement = "needs_support"
            else:
                improvement = "steady"

    today = datetime.datetime.utcnow().date()
    heatmap = []
    for offset in range(6, -1, -1):
        day = today - datetime.timedelta(days=offset)
        seconds = 0
        for event in events:
            occurred = event.occurred_at or datetime.datetime.utcnow()
            if occurred.date() == day:
                seconds += event.seconds or 0
        heatmap.append({"date": day.isoformat(), "seconds": seconds})

    profile = db.query(UserProfile).filter(UserProfile.id == owner_id).first()
    pace_minutes = profile.daily_goal_minutes if profile and profile.daily_goal_minutes else None
    pace = None
    if profile and isinstance(profile.accessibility_preferences, dict):
        pace = profile.accessibility_preferences.get("pace")

    if improvement == "needs_support":
        focus = "Stay with the current unit and retry the check before opening the next one."
    elif improvement == "improving":
        focus = "Recent checks are stronger than earlier ones. Continue into the next ready unit."
    elif pace and pace_minutes:
        focus = f"Your pace is {pace_minutes} minutes a day. Work through the ready units in order."
    elif pace_minutes:
        focus = f"Your daily goal is {pace_minutes} minutes. Work through the ready units in order."
    elif pace:
        focus = f"Your pace is {pace}. Work through the ready units in order."
    else:
        focus = "Set a daily goal and pace to get a schedule suggestion."

    suggestions = (
        db.query(TeacherAction)
        .filter(TeacherAction.student_id == owner_id, TeacherAction.status == "proposed")
        .order_by(TeacherAction.created_at.desc())
        .limit(5)
        .all()
    )

    suggestion_rows = []
    for action in suggestions:
        reason = action.reason_json or {}
        evidence = reason.get("evidence") or {}
        band = evidence.get("band")
        count = evidence.get("evidenceCount")
        concept = reason.get("conceptId")
        if band and concept:
            explanation = (
                f"Your teacher noticed {band.replace('_', ' ')} evidence for "
                f"{str(concept).replace('-', ' ')} ({count} checks)."
            )
        else:
            explanation = "Your teacher sent a note for your next study session."
        teacher = db.query(UserProfile).filter(UserProfile.id == action.teacher_id).first()
        suggestion_rows.append(
            {
                "id": str(action.id),
                "note": reason.get("notes") or "",
                "actionType": action.action_type,
                "conceptId": concept,
                "status": action.status,
                "explanation": explanation,
                "teacherName": teacher.display_name if teacher else "Your teacher",
                "createdAt": action.created_at.isoformat() if action.created_at else None,
            }
        )

    return {
        "minutesStudied": round(total_seconds / 60, 1),
        "readingTitle": readings[-1].lesson_title if readings else None,
        "checkpointCount": len(checkpoints),
        "accuracyRate": round(accuracy, 2) if accuracy is not None else None,
        "improvement": improvement,
        "pace": pace,
        "dailyGoalMinutes": pace_minutes,
        "focus": focus,
        "heatmap": heatmap,
        "suggestions": suggestion_rows,
    }


@router.post("/events")
def record_study_event(
    req: StudyEventCreate,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    event = StudyEvent(
        owner_id=owner_id,
        path_id=_as_uuid(req.pathId),
        lesson_id=(req.lessonId or "")[:80] or None,
        lesson_title=(req.lessonTitle or "")[:200] or None,
        event_type=req.eventType,
        seconds=max(0, min(req.seconds, 60 * 180)),
        score=None if req.score is None else max(0.0, min(float(req.score), 1.0)),
    )
    db.add(event)
    db.commit()
    return {"id": str(event.id), "status": "recorded"}


@router.get("/summary")
def study_summary(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return summarize_student(db, owner_id)


class RecommendationDecision(BaseModel):
    decision: Literal["accept", "dismiss"]
    note: Optional[str] = Field(default=None, max_length=500)


@router.post("/recommendations/{action_id}/respond")
def respond_to_recommendation(
    action_id: uuid.UUID,
    req: RecommendationDecision,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    action = db.query(TeacherAction).filter(
        TeacherAction.id == action_id,
        TeacherAction.student_id == owner_id,
        TeacherAction.status == "proposed",
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    action.status = "accepted" if req.decision == "accept" else "dismissed"
    action.resolved_at = datetime.datetime.utcnow()
    reason = dict(action.reason_json or {})
    reason["studentResponse"] = {
        "decision": req.decision,
        "note": (req.note or "").strip()[:500],
        "respondedAt": action.resolved_at.isoformat(),
    }
    action.reason_json = reason
    db.commit()
    return {"id": str(action.id), "status": action.status}
