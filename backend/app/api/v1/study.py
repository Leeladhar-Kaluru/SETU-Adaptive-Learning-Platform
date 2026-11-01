import datetime
import uuid
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.classroom import TeacherAction
from app.models.learning import LearningPath, LessonVersion, PathLesson, StudyEvent
from app.models.profiles import UserProfile
from app.services.coach_service import build_lesson_coaching
from app.services.learner_insights import build_learner_insights
from app.services.smart_check import build_smart_check, next_smart_question
from app.services.study_plan import build_study_plan

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
        .filter(
            TeacherAction.student_id == owner_id,
            TeacherAction.status.in_(("proposed", "accepted", "edited")),
        )
        .order_by(TeacherAction.created_at.desc())
        .limit(10)
        .all()
    )

    suggestion_rows = []
    for action in suggestions:
        reason = action.reason_json or {}
        # A suggestion leaves the student's desk once the student responds to it.
        if reason.get("studentResponse"):
            continue
        if len(suggestion_rows) >= 5:
            break
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

    reading_title = None
    if readings:
        latest_reading = readings[-1]
        lesson = (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(
                PathLesson.id == latest_reading.lesson_id,
                LearningPath.status.in_(["active", "generating"]),
            )
            .first()
            if latest_reading.lesson_id
            else None
        )
        if lesson:
            reading_title = lesson.title

    return {
        "minutesStudied": round(total_seconds / 60, 1),
        "readingTitle": reading_title,
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


@router.get("/insights")
def learner_insights(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Evidence-derived understanding of routine, pace, hints, accuracy and mastery."""
    return build_learner_insights(db, owner_id)


@router.get("/plan")
def adaptive_study_plan(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """One cross-book plan that reorders itself from recorded performance."""
    return build_study_plan(db, owner_id)


def _owned_lesson(
    db: Session, owner_id: uuid.UUID, lesson_id: str
) -> tuple[PathLesson, LessonVersion]:
    lesson = None
    try:
        lesson_uuid = uuid.UUID(lesson_id)
        lesson = (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(PathLesson.id == lesson_uuid, LearningPath.owner_id == owner_id)
            .first()
        )
    except (ValueError, TypeError):
        lesson = (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(PathLesson.lesson_key == lesson_id, LearningPath.owner_id == owner_id)
            .first()
        )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    version = (
        db.query(LessonVersion)
        .filter(LessonVersion.path_lesson_id == lesson.id)
        .order_by(LessonVersion.version_number.desc())
        .first()
    )
    if not version or not version.lesson_package_json:
        raise HTTPException(status_code=404, detail="Lesson package content not ready")
    return lesson, version


@router.get("/coach/{lesson_id}")
def lesson_coaching(
    lesson_id: str,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Grounded key points, source spotlights, fun facts and study tips."""
    lesson, version = _owned_lesson(db, owner_id, lesson_id)
    return build_lesson_coaching(
        db, owner_id=owner_id, lesson=lesson, lesson_version=version
    )


@router.get("/smart-check")
def smart_check(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """A short diagnostic built from the learner's least certain concepts."""
    return build_smart_check(db, owner_id)


class SmartCheckNextRequest(BaseModel):
    answeredQuestionKeys: list[str] = Field(default_factory=list, max_length=20)


@router.post("/smart-check/next")
def smart_check_next(
    req: SmartCheckNextRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return next_smart_question(
        db,
        owner_id,
        answered_question_keys=req.answeredQuestionKeys,
        max_questions=5,
    )


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
    ).first()
    reason = dict(action.reason_json or {}) if action else {}
    if (
        not action
        or action.status not in ("proposed", "accepted", "edited")
        or reason.get("studentResponse")
    ):
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
