import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.profiles import UserProfile
from app.models.learning import (
    StudyEvent,
    QuizAttempt,
    ConceptMasterySnapshot,
    LessonVersion,
    PathLesson
)
from app.models.classroom import Classroom, ClassroomMembership

router = APIRouter()

class ProfileUpdateRequest(BaseModel):
    displayName: Optional[str] = None
    grade: Optional[int] = None
    boardId: Optional[str] = None
    preferredLanguage: Optional[str] = None
    subjectsInterested: Optional[List[str]] = None
    learningGoals: Optional[List[str]] = None
    dailyGoalMinutes: Optional[int] = None
    accessibilityPreferences: Optional[Dict[str, Any]] = None
    onboardingCompleted: Optional[bool] = None
    tourCompleted: Optional[bool] = None

@router.get("/dashboard")
async def get_student_dashboard(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Returns complete student learning dashboard data:
    - User profile details
    - 12-week (84-day) activity heatmap
    - Streak calculations (current streak & longest streak)
    - Total study duration & average accuracy
    - Concept mastery matrix by band
    - Recent quiz attempts
    - Joined classrooms
    """
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete signup or onboarding.")

    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    # 1. Fetch all study events for this student
    events = db.query(StudyEvent).filter(
        StudyEvent.owner_id == user_id
    ).order_by(StudyEvent.occurred_at.asc()).all()

    # 2. Build 84-day activity heatmap (12 weeks) from study events only.
    # Quiz attempts already write a StudyEvent, so adding attempt time here
    # would count the same minutes twice.
    start_date = today - datetime.timedelta(days=83)
    daily_stats: Dict[str, Dict[str, Any]] = {}
    
    # Initialize all 84 days
    for i in range(84):
        d = start_date + datetime.timedelta(days=i)
        d_str = d.isoformat()
        daily_stats[d_str] = {
            "date": d_str,
            "seconds": 0,
            "minutes": 0,
            "count": 0,
            "level": 0
        }

    active_days_set = set()
    total_study_seconds = 0

    for ev in events:
        total_study_seconds += (ev.seconds or 0)
        ev_date = ev.occurred_at.date() if ev.occurred_at else today
        active_days_set.add(ev_date)
        d_str = ev_date.isoformat()
        if d_str in daily_stats:
            daily_stats[d_str]["seconds"] += (ev.seconds or 0)
            daily_stats[d_str]["count"] += 1

    attempts = db.query(QuizAttempt).filter(
        QuizAttempt.owner_id == user_id
    ).order_by(QuizAttempt.occurred_at.desc()).all()

    # Assign heatmap intensity levels (0 = 0m, 1 = 1-15m, 2 = 16-30m, 3 = 31-45m, 4 = 45m+)
    heatmap_list = []
    for d_str in sorted(daily_stats.keys()):
        item = daily_stats[d_str]
        mins = round(item["seconds"] / 60, 1)
        item["minutes"] = mins
        if mins <= 0:
            item["level"] = 0
        elif mins <= 15:
            item["level"] = 1
        elif mins <= 30:
            item["level"] = 2
        elif mins <= 45:
            item["level"] = 3
        else:
            item["level"] = 4
        heatmap_list.append(item)

    # 3. Calculate Streaks
    # Current streak: count backwards from today (or yesterday if no event yet today)
    current_streak = 0
    check_date = today
    if check_date not in active_days_set:
        check_date = today - datetime.timedelta(days=1)
    
    while check_date in active_days_set:
        current_streak += 1
        check_date -= datetime.timedelta(days=1)

    # Longest streak across all dates
    longest_streak = 0
    if active_days_set:
        sorted_active_days = sorted(list(active_days_set))
        temp_streak = 1
        longest_streak = 1
        for i in range(1, len(sorted_active_days)):
            diff = (sorted_active_days[i] - sorted_active_days[i - 1]).days
            if diff == 1:
                temp_streak += 1
                if temp_streak > longest_streak:
                    longest_streak = temp_streak
            elif diff > 1:
                temp_streak = 1

    # 4. Accuracy & Quiz stats
    total_attempts = len(attempts)
    correct_attempts = sum(1 for a in attempts if a.is_correct)
    avg_score = round((correct_attempts / total_attempts * 100), 1) if total_attempts > 0 else 0.0

    # 5. Mastery matrix
    snapshots = db.query(ConceptMasterySnapshot).filter(
        ConceptMasterySnapshot.owner_id == user_id
    ).order_by(ConceptMasterySnapshot.calculated_at.desc()).all()

    mastery_list = []
    for s in snapshots:
        mastery_list.append({
            "conceptId": s.concept_id,
            "band": s.estimate_band,
            "score": round((s.numeric_estimate or 0.0) * 100, 1),
            "evidenceCount": s.evidence_count,
            "calculatedAt": s.calculated_at.isoformat() if s.calculated_at else None,
            "needsRemediation": s.estimate_band == "developing"
        })

    # 6. Recent Attempts with lesson titles
    recent_attempts_list = []
    for att in attempts[:10]:
        # Resolve lesson title
        lesson_title = "Practice Checkpoint"
        lesson_ver = db.query(LessonVersion).filter(LessonVersion.id == att.lesson_version_id).first()
        if lesson_ver:
            p_lesson = db.query(PathLesson).filter(PathLesson.id == lesson_ver.path_lesson_id).first()
            if p_lesson:
                lesson_title = p_lesson.title

        recent_attempts_list.append({
            "id": str(att.id),
            "lessonTitle": lesson_title,
            "score": att.score,
            "isCorrect": att.is_correct,
            "hintsUsed": len(att.hints_used or []),
            "elapsedSeconds": att.elapsed_seconds if att.elapsed_seconds is not None else 0,
            "occurredAt": att.occurred_at.isoformat() if att.occurred_at else None
        })

    # 7. Joined classrooms
    memberships = db.query(ClassroomMembership).filter(
        ClassroomMembership.student_id == user_id,
        ClassroomMembership.status == "active"
    ).all()
    classrooms_list = []
    for m in memberships:
        c = db.query(Classroom).filter(Classroom.id == m.classroom_id).first()
        if c:
            classrooms_list.append({
                "id": str(c.id),
                "name": c.name,
                "grade": c.grade,
                "subjectScope": c.subject_scope,
                "joinCode": c.join_code,
                "joinedAt": m.created_at.isoformat() if m.created_at else None
            })

    return {
        "profile": {
            "id": str(profile.id),
            "email": profile.email,
            "role": profile.role,
            "displayName": profile.display_name,
            "grade": profile.grade,
            "boardId": profile.board_id,
            "preferredLanguage": profile.preferred_language,
            "subjectsInterested": profile.subjects_interested or [],
            "learningGoals": profile.learning_goals or [],
            "dailyGoalMinutes": profile.daily_goal_minutes,
            "academicContextComplete": bool(
                profile.grade and profile.board_id and profile.preferred_language
            ),
            "onboardingCompleted": profile.onboarding_completed
        },
        "stats": {
            "currentStreak": current_streak,
            "longestStreak": longest_streak,
            "totalMinutesStudied": round(total_study_seconds / 60, 1),
            "totalSessions": len(events),
            "averageAccuracy": avg_score,
            "totalQuestionsAttempted": total_attempts
        },
        "activityHeatmap": heatmap_list,
        "conceptMastery": mastery_list,
        "recentAttempts": recent_attempts_list,
        "classrooms": classrooms_list
    }

@router.get("")
async def get_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete signup or onboarding.")

    return {
        "id": str(profile.id),
        "email": profile.email,
        "role": profile.role,
        "displayName": profile.display_name,
        "grade": profile.grade,
        "boardId": profile.board_id,
        "preferredLanguage": profile.preferred_language,
        "subjectsInterested": profile.subjects_interested or [],
        "learningGoals": profile.learning_goals or [],
        "dailyGoalMinutes": profile.daily_goal_minutes,
        "accessibilityPreferences": profile.accessibility_preferences or {
            "font_size": "medium",
            "reduced_motion": False,
            "high_contrast": False
        },
        "onboardingCompleted": profile.onboarding_completed,
        "tourCompleted": profile.tour_completed,
        "createdAt": profile.created_at.isoformat()
    }

@router.put("")
async def update_profile(
    req: ProfileUpdateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Complete signup or onboarding.")

    if req.displayName is not None:
        profile.display_name = req.displayName.strip()
    if req.grade is not None:
        profile.grade = req.grade
    if req.boardId is not None:
        profile.board_id = req.boardId
    if req.preferredLanguage is not None:
        profile.preferred_language = req.preferredLanguage
    if req.subjectsInterested is not None:
        profile.subjects_interested = req.subjectsInterested
    if req.learningGoals is not None:
        profile.learning_goals = req.learningGoals
    if req.dailyGoalMinutes is not None:
        profile.daily_goal_minutes = req.dailyGoalMinutes
    if req.accessibilityPreferences is not None:
        profile.accessibility_preferences = req.accessibilityPreferences
    if req.onboardingCompleted is not None:
        profile.onboarding_completed = req.onboardingCompleted
    if req.tourCompleted is not None:
        profile.tour_completed = req.tourCompleted

    db.commit()
    db.refresh(profile)

    return {
        "status": "updated",
        "profile": {
            "id": str(profile.id),
            "email": profile.email,
            "role": profile.role,
            "displayName": profile.display_name,
            "grade": profile.grade,
            "boardId": profile.board_id,
            "preferredLanguage": profile.preferred_language,
            "subjectsInterested": profile.subjects_interested or [],
            "learningGoals": profile.learning_goals or [],
            "dailyGoalMinutes": profile.daily_goal_minutes,
            "accessibilityPreferences": profile.accessibility_preferences or {},
            "onboardingCompleted": profile.onboarding_completed,
            "tourCompleted": profile.tour_completed
        }
    }

