"""Learner understanding derived exclusively from recorded SETU activity.

Every number in this module comes from a stored study event, quiz attempt,
concept evidence row, mastery snapshot or learning path. Nothing here guesses
a student's routine, pace or strength: when the evidence is missing, the
service says so and lowers its confidence instead of inventing a profile.
"""

import datetime
import statistics
import uuid
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.learning import (
    ConceptEvidence,
    ConceptMasterySnapshot,
    LearningPath,
    PathLesson,
    QuizAttempt,
    StudyEvent,
)
from app.models.profiles import UserProfile

UTC = datetime.timezone.utc

WINDOWS = (
    (5, 8, "dawn", "Early morning"),
    (8, 12, "morning", "Morning"),
    (12, 17, "afternoon", "Afternoon"),
    (17, 21, "evening", "Evening"),
    (21, 29, "night", "Late night"),
)

BAND_RANK = {
    "not_enough_evidence": 0,
    "developing": 1,
    "approaching": 2,
    "demonstrated": 3,
}


def _utc_naive(value: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _median(values: Iterable[float]) -> Optional[float]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return round(statistics.median(clean), 1)


def _percent(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value * 100))


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def concept_label(concept_id: str) -> str:
    """Turn a stored concept identifier into a readable label.

    Identifiers are data, not copy. This only changes presentation; it never
    adds a concept that is not present in the database.
    """
    words = str(concept_id or "").replace("concept-", "").replace("concept_", "")
    words = words.replace("-", " ").replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else "Unlabelled concept"


def _window_for(value: datetime.datetime) -> Dict[str, str]:
    hour = value.hour
    for start, end, key, label in WINDOWS:
        if start <= end:
            if start <= hour < end:
                return {"id": key, "label": label}
        elif hour >= start or hour < end:
            return {"id": key, "label": label}
    return {"id": "night", "label": "Late night"}


def _hint_count(attempt: QuizAttempt) -> int:
    hints = attempt.hints_used
    if isinstance(hints, list):
        return len(hints)
    if isinstance(hints, str):
        return 1 if hints.strip() else 0
    return int(attempt.hint_level or 0)


def _latest_snapshots(db: Session, owner_id: uuid.UUID) -> Dict[str, ConceptMasterySnapshot]:
    rows = (
        db.query(ConceptMasterySnapshot)
        .filter(ConceptMasterySnapshot.owner_id == owner_id)
        .order_by(ConceptMasterySnapshot.calculated_at.desc())
        .all()
    )
    latest: Dict[str, ConceptMasterySnapshot] = {}
    for row in rows:
        if row.concept_id not in latest:
            latest[row.concept_id] = row
    return latest


def _streak(active_days: List[datetime.date], today: datetime.date) -> Dict[str, int]:
    if not active_days:
        return {"current": 0, "longest": 0}
    active = set(active_days)
    check = today if today in active else today - datetime.timedelta(days=1)
    current = 0
    while check in active:
        current += 1
        check -= datetime.timedelta(days=1)

    longest = 1
    running = 1
    ordered = sorted(active)
    for index in range(1, len(ordered)):
        if (ordered[index] - ordered[index - 1]).days == 1:
            running += 1
            longest = max(longest, running)
        else:
            running = 1
    return {"current": current, "longest": max(longest, current)}


def _accuracy_block(attempts: List[QuizAttempt]) -> Dict[str, Any]:
    if not attempts:
        return {
            "state": "no_evidence",
            "overall": None,
            "lastSevenDays": None,
            "previousSevenDays": None,
            "trend": "no_evidence",
            "detail": "No graded answer has been recorded yet.",
        }

    now = datetime.datetime.now(UTC).replace(tzinfo=None)
    last_seven_start = now - datetime.timedelta(days=7)
    previous_start = now - datetime.timedelta(days=14)

    def rate(rows: List[QuizAttempt]) -> Optional[float]:
        return _ratio(sum(1 for row in rows if row.is_correct), len(rows))

    last_seven = [
        row for row in attempts
        if _utc_naive(row.occurred_at) and _utc_naive(row.occurred_at) >= last_seven_start
    ]
    previous = [
        row for row in attempts
        if _utc_naive(row.occurred_at)
        and previous_start <= _utc_naive(row.occurred_at) < last_seven_start
    ]
    last_rate = rate(last_seven)
    previous_rate = rate(previous)
    overall = rate(attempts)

    trend = "starting"
    if last_rate is not None and previous_rate is not None:
        if last_rate >= previous_rate + 0.08:
            trend = "improving"
        elif last_rate <= previous_rate - 0.08:
            trend = "needs_support"
        else:
            trend = "steady"

    practice = [row for row in attempts if (row.attempt_kind or "practice") == "practice"]
    checkpoint = [row for row in attempts if row.attempt_kind == "checkpoint"]
    if last_rate is None:
        detail = (
            f"{len(attempts)} graded answer(s) are recorded, but none in the last seven days. "
            "The overall rate is from earlier work."
        )
    elif trend == "starting":
        detail = (
            f"{sum(1 for row in last_seven if row.is_correct)} of {len(last_seven)} answers "
            "in the last seven days were correct. There is not yet a full prior week to compare."
        )
    elif trend == "improving":
        detail = (
            f"Last seven days: {_percent(last_rate)}% correct, up from "
            f"{_percent(previous_rate)}% in the seven days before."
        )
    elif trend == "needs_support":
        detail = (
            f"Last seven days: {_percent(last_rate)}% correct, down from "
            f"{_percent(previous_rate)}% in the seven days before."
        )
    else:
        detail = (
            f"Last seven days: {_percent(last_rate)}% correct, within a few points of "
            f"{_percent(previous_rate)}% in the prior week."
        )

    return {
        "state": "measured",
        "overall": _percent(overall),
        "lastSevenDays": _percent(last_rate),
        "previousSevenDays": _percent(previous_rate),
        "trend": trend,
        "practiceAccuracy": _percent(rate(practice)),
        "checkpointAccuracy": _percent(rate(checkpoint)),
        "detail": detail,
    }


def _pace_block(
    attempts: List[QuizAttempt],
    events: List[StudyEvent],
    profile: Optional[UserProfile],
) -> Dict[str, Any]:
    timed_attempts = [row for row in attempts if (row.elapsed_seconds or 0) > 0]
    reading_events = [
        row for row in events
        if row.event_type == "reading" and (row.seconds or 0) > 0
    ]
    answer_seconds = _median(row.elapsed_seconds for row in timed_attempts)
    session_minutes = _median((row.seconds or 0) / 60 for row in reading_events)
    goal = profile.daily_goal_minutes if profile else None

    if answer_seconds is None and session_minutes is None:
        return {
            "state": "no_evidence",
            "medianAnswerSeconds": None,
            "medianSessionMinutes": None,
            "dailyGoalMinutes": goal,
            "goalProgress": None,
            "label": "No timed work yet",
            "detail": "No answer timing or reading session length has been recorded yet.",
        }

    label = "No timed answers yet"
    if answer_seconds is not None:
        if answer_seconds <= 45:
            label = "Quick, confident checks"
        elif answer_seconds <= 150:
            label = "Steady working pace"
        else:
            label = "Deep-work pace"

    goal_progress = None
    today = datetime.datetime.now(UTC).date()
    if goal:
        today_minutes = sum(
            (row.seconds or 0) / 60
            for row in events
            if _utc_naive(row.occurred_at) and _utc_naive(row.occurred_at).date() == today
        )
        goal_progress = _percent(min(1.0, today_minutes / goal)) if goal else None
        goal_detail = (
            f"{round(today_minutes, 1)} of {goal} goal minutes recorded today."
            if goal_progress is not None
            else ""
        )
    else:
        goal_detail = "No daily minutes goal is set."

    pieces = []
    if answer_seconds is not None:
        pieces.append(f"Median answer time is {answer_seconds:.0f}s across {len(timed_attempts)} timed answers.")
    if session_minutes is not None:
        rounded = round(session_minutes)
        unit = "minute" if rounded == 1 else "minutes"
        pieces.append(f"Median reading session is {rounded} {unit}.")
    if goal_detail:
        pieces.append(goal_detail)

    return {
        "state": "measured",
        "medianAnswerSeconds": answer_seconds,
        "medianSessionMinutes": session_minutes,
        "dailyGoalMinutes": goal,
        "goalProgress": goal_progress,
        "label": label,
        "detail": " ".join(pieces),
    }


def _hint_block(attempts: List[QuizAttempt]) -> Dict[str, Any]:
    if not attempts:
        return {
            "state": "no_evidence",
            "hintedAttempts": 0,
            "totalAttempts": 0,
            "hintRate": None,
            "averageHints": None,
            "accuracyWithHints": None,
            "accuracyWithoutHints": None,
            "label": "No hint history yet",
            "detail": "No attempt has recorded hint use yet.",
        }

    hinted = [row for row in attempts if _hint_count(row) > 0]
    independent = [row for row in attempts if _hint_count(row) == 0]
    hint_rate = _ratio(len(hinted), len(attempts))
    accuracy_hinted = _ratio(sum(1 for row in hinted if row.is_correct), len(hinted))
    accuracy_independent = _ratio(sum(1 for row in independent if row.is_correct), len(independent))
    average_hints = round(sum(_hint_count(row) for row in attempts) / len(attempts), 1)

    if hint_rate is None:
        label = "No hint history yet"
        detail = "No attempt has recorded hint use yet."
    elif hint_rate >= 0.6:
        label = "High hint reliance"
        detail = (
            f"{len(hinted)} of {len(attempts)} attempts used at least one hint. "
            "Try one independent first attempt before opening a hint."
        )
    elif hint_rate >= 0.3:
        label = "Hints are part of your process"
        detail = (
            f"{len(hinted)} of {len(attempts)} attempts used a hint. "
            "That is a normal support level, but check whether the hint is doing the thinking."
        )
    else:
        label = "Mostly independent"
        detail = (
            f"{len(hinted)} of {len(attempts)} attempts used a hint. "
            "You usually try the question first."
        )

    if accuracy_hinted is not None and accuracy_independent is not None:
        detail += (
            f" Accuracy with hints is {_percent(accuracy_hinted)}%; without hints it is "
            f"{_percent(accuracy_independent)}%."
        )

    return {
        "state": "measured",
        "hintedAttempts": len(hinted),
        "totalAttempts": len(attempts),
        "hintRate": _percent(hint_rate),
        "averageHints": average_hints,
        "accuracyWithHints": _percent(accuracy_hinted),
        "accuracyWithoutHints": _percent(accuracy_independent),
        "label": label,
        "detail": detail,
    }


def _routine_block(
    attempts: List[QuizAttempt], events: List[StudyEvent]
) -> Dict[str, Any]:
    if not events:
        return {
            "state": "no_evidence",
            "windows": [],
            "bestWindow": None,
            "currentStreak": 0,
            "longestStreak": 0,
            "activeDays": 0,
            "consistencyScore": 0,
            "consistencyLabel": "No routine yet",
            "weekdayMinutes": 0,
            "weekendMinutes": 0,
            "detail": "No study session has been recorded yet.",
        }

    event_windows: Dict[str, Dict[str, Any]] = {
        key: {"id": key, "label": label, "minutes": 0.0, "sessions": 0, "attempts": 0, "correct": 0}
        for _, _, key, label in WINDOWS
    }
    active_days = set()
    weekday_minutes = 0.0
    weekend_minutes = 0.0
    last_14_days = set()
    now = datetime.datetime.now(UTC).replace(tzinfo=None)
    for event in events:
        when = _utc_naive(event.occurred_at)
        if when is None:
            continue
        window = _window_for(when)
        bucket = event_windows[window["id"]]
        bucket["minutes"] += (event.seconds or 0) / 60
        bucket["sessions"] += 1
        active_days.add(when.date())
        if when.date() >= (now - datetime.timedelta(days=13)).date():
            last_14_days.add(when.date())
        if when.weekday() >= 5:
            weekend_minutes += (event.seconds or 0) / 60
        else:
            weekday_minutes += (event.seconds or 0) / 60

    for attempt in attempts:
        when = _utc_naive(attempt.occurred_at)
        if when is None:
            continue
        bucket = event_windows[_window_for(when)["id"]]
        bucket["attempts"] += 1
        if attempt.is_correct:
            bucket["correct"] += 1

    for bucket in event_windows.values():
        bucket["minutes"] = round(bucket["minutes"], 1)
        accuracy = _ratio(bucket["correct"], bucket["attempts"])
        bucket["accuracy"] = _percent(accuracy)

    windows = list(event_windows.values())
    studied = [window for window in windows if window["sessions"] > 0]
    with_accuracy = [window for window in studied if (window["attempts"] or 0) >= 2]
    if with_accuracy:
        best = max(with_accuracy, key=lambda item: (item["accuracy"] or 0, item["minutes"]))
        basis = f"{best['accuracy']}% accuracy across {best['attempts']} graded answers"
    elif studied:
        best = max(studied, key=lambda item: item["minutes"])
        basis = f"{best['minutes']} recorded minutes across {best['sessions']} sessions"
    else:
        best = None
        basis = "No study window recorded"

    today = now.date()
    streak = _streak(sorted(active_days), today)
    consistency = round(len(last_14_days) / 14 * 100)
    if consistency >= 70:
        consistency_label = "Very consistent"
    elif consistency >= 40:
        consistency_label = "Building a rhythm"
    elif consistency > 0:
        consistency_label = "Occasional sessions"
    else:
        consistency_label = "No routine yet"

    if best:
        detail = (
            f"Your strongest recorded window is {best['label'].lower()} "
            f"({basis}). {streak['current']} day current streak; "
            f"{consistency}% of the last 14 days have activity."
        )
    else:
        detail = "Study events are recorded, but none has a readable timestamp window yet."

    return {
        "state": "measured",
        "windows": windows,
        "bestWindow": best,
        "currentStreak": streak["current"],
        "longestStreak": streak["longest"],
        "activeDays": len(active_days),
        "consistencyScore": consistency,
        "consistencyLabel": consistency_label,
        "weekdayMinutes": round(weekday_minutes, 1),
        "weekendMinutes": round(weekend_minutes, 1),
        "timezoneNote": "Windows use the timestamps stored by SETU (UTC).",
        "detail": detail,
    }


def _mastery_block(db: Session, owner_id: uuid.UUID) -> Dict[str, Any]:
    snapshots = _latest_snapshots(db, owner_id)
    concepts: List[Dict[str, Any]] = []
    for concept_id, snapshot in snapshots.items():
        concepts.append(
            {
                "conceptId": concept_id,
                "label": concept_label(concept_id),
                "band": snapshot.estimate_band,
                "score": _percent(snapshot.numeric_estimate),
                "evidenceCount": snapshot.evidence_count or 0,
                "calculatedAt": (
                    _utc_naive(snapshot.calculated_at).isoformat()
                    if snapshot.calculated_at
                    else None
                ),
            }
        )

    demonstrated = [item for item in concepts if item["band"] == "demonstrated"]
    approaching = [item for item in concepts if item["band"] == "approaching"]
    developing = [item for item in concepts if item["band"] == "developing"]
    sparse = [item for item in concepts if item["band"] == "not_enough_evidence"]

    strengths = sorted(
        demonstrated + approaching,
        key=lambda item: (BAND_RANK.get(item["band"], 0), item["score"] or 0),
        reverse=True,
    )[:3]
    focus = sorted(
        developing,
        key=lambda item: (item["score"] if item["score"] is not None else 0, -item["evidenceCount"]),
    )[:3]
    if not focus:
        focus = sorted(
            [item for item in approaching if (item["score"] or 0) < 75],
            key=lambda item: item["score"] or 0,
        )[:3]
    if not focus:
        focus = sorted(sparse, key=lambda item: -item["evidenceCount"])[:2]

    if not concepts:
        detail = "No concept mastery snapshot exists yet. Answer a practice or checkpoint question to create evidence."
    else:
        detail = (
            f"{len(concepts)} concept(s) have a mastery snapshot: "
            f"{len(demonstrated)} demonstrated, {len(approaching)} approaching, "
            f"{len(developing)} developing, {len(sparse)} with too little evidence."
        )

    return {
        "state": "measured" if concepts else "no_evidence",
        "concepts": concepts,
        "strengths": strengths,
        "focusAreas": focus,
        "bands": {
            "demonstrated": len(demonstrated),
            "approaching": len(approaching),
            "developing": len(developing),
            "notEnoughEvidence": len(sparse),
        },
        "detail": detail,
    }


def _habits(
    accuracy: Dict[str, Any],
    pace: Dict[str, Any],
    hints: Dict[str, Any],
    routine: Dict[str, Any],
    mastery: Dict[str, Any],
) -> List[Dict[str, str]]:
    habits: List[Dict[str, str]] = []

    if hints["state"] == "measured":
        tone = "watch" if (hints["hintRate"] or 0) >= 60 else "positive"
        habits.append(
            {
                "id": "hint-use",
                "tone": tone,
                "title": hints["label"],
                "detail": hints["detail"],
            }
        )

    if pace["state"] == "measured":
        habits.append(
            {
                "id": "pace",
                "tone": "neutral",
                "title": pace["label"],
                "detail": pace["detail"],
            }
        )

    if routine["state"] == "measured":
        habits.append(
            {
                "id": "routine",
                "tone": "positive" if (routine["consistencyScore"] or 0) >= 40 else "watch",
                "title": f"{routine['consistencyLabel']} · {routine['bestWindow']['label'] if routine.get('bestWindow') else 'No best window'}",
                "detail": routine["detail"],
            }
        )

    if accuracy["state"] == "measured":
        tone = {
            "improving": "positive",
            "needs_support": "watch",
            "steady": "neutral",
            "starting": "neutral",
        }.get(accuracy["trend"], "neutral")
        habits.append(
            {
                "id": "accuracy",
                "tone": tone,
                "title": {
                    "improving": "Accuracy is improving",
                    "needs_support": "Accuracy dipped recently",
                    "steady": "Accuracy is steady",
                    "starting": "Building an accuracy baseline",
                }.get(accuracy["trend"], "Accuracy recorded"),
                "detail": accuracy["detail"],
            }
        )

    if mastery["state"] == "measured" and mastery["focusAreas"]:
        first = mastery["focusAreas"][0]
        habits.append(
            {
                "id": "focus",
                "tone": "watch" if first["band"] == "developing" else "neutral",
                "title": f"Focus: {first['label']}",
                "detail": (
                    f"{first['band'].replace('_', ' ')} with "
                    f"{first['score'] if first['score'] is not None else 'no'}% from "
                    f"{first['evidenceCount']} evidence point(s)."
                ),
            }
        )

    return habits


def build_learner_insights(db: Session, owner_id: uuid.UUID) -> Dict[str, Any]:
    profile = db.query(UserProfile).filter(UserProfile.id == owner_id).first()
    events = (
        db.query(StudyEvent)
        .filter(StudyEvent.owner_id == owner_id)
        .order_by(StudyEvent.occurred_at.asc())
        .all()
    )
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.owner_id == owner_id)
        .order_by(QuizAttempt.occurred_at.asc())
        .all()
    )
    evidence_rows = (
        db.query(ConceptEvidence)
        .filter(ConceptEvidence.owner_id == owner_id)
        .all()
    )
    path_count = (
        db.query(LearningPath)
        .filter(LearningPath.owner_id == owner_id, LearningPath.status.in_(["active", "generating"]))
        .count()
    )
    ready_lesson_count = (
        db.query(PathLesson)
        .join(LearningPath, LearningPath.id == PathLesson.path_id)
        .filter(
            LearningPath.owner_id == owner_id,
            LearningPath.status.in_(["active", "generating"]),
            PathLesson.status == "ready",
        )
        .count()
    )

    accuracy = _accuracy_block(attempts)
    pace = _pace_block(attempts, events, profile)
    hints = _hint_block(attempts)
    routine = _routine_block(attempts, events)
    mastery = _mastery_block(db, owner_id)
    habits = _habits(accuracy, pace, hints, routine, mastery)

    total_minutes = round(sum((event.seconds or 0) for event in events) / 60, 1)
    active_days = len({
        _utc_naive(event.occurred_at).date()
        for event in events
        if _utc_naive(event.occurred_at) is not None
    })

    if not events and not attempts:
        confidence = "none"
        confidence_detail = "No study event or graded answer exists yet."
        summary = (
            "No learning activity is recorded yet. Open a ready lesson, read a section "
            "or answer a question, and SETU will start building your study profile."
        )
    else:
        if len(attempts) >= 10 and len(mastery["concepts"]) >= 3:
            confidence = "high"
        elif len(attempts) >= 4:
            confidence = "medium"
        else:
            confidence = "low"
        confidence_detail = (
            f"{len(attempts)} graded answer(s), {len(events)} study event(s) and "
            f"{len(evidence_rows)} concept evidence row(s) back this profile."
        )
        summary_parts = [
            f"You have {total_minutes:g} recorded minutes across {active_days} active "
            f"{'day' if active_days == 1 else 'days'} and {len(attempts)} graded "
            f"{'answer' if len(attempts) == 1 else 'answers'}."
        ]
        if accuracy["overall"] is not None:
            summary_parts.append(f"Overall accuracy is {accuracy['overall']}% ({accuracy['trend'].replace('_', ' ')}).")
        if routine.get("bestWindow"):
            summary_parts.append(
                f"Your strongest recorded study window is {routine['bestWindow']['label'].lower()}."
            )
        if hints["hintRate"] is not None:
            summary_parts.append(f"Hints are used on {hints['hintRate']}% of attempts.")
        if mastery["strengths"]:
            summary_parts.append(f"Strongest concept: {mastery['strengths'][0]['label']}.")
        if mastery["focusAreas"]:
            summary_parts.append(f"Next focus: {mastery['focusAreas'][0]['label']}.")
        summary = " ".join(summary_parts)

    return {
        "generatedAt": datetime.datetime.now(UTC).isoformat(),
        "state": "measured" if (events or attempts or mastery["concepts"]) else "no_evidence",
        "confidence": confidence,
        "confidenceDetail": confidence_detail,
        "summary": summary,
        "library": {
            "activePaths": path_count,
            "readyLessons": ready_lesson_count,
        },
        "evidence": {
            "studyEvents": len(events),
            "gradedAttempts": len(attempts),
            "practiceAttempts": sum(1 for row in attempts if (row.attempt_kind or "practice") == "practice"),
            "checkpointAttempts": sum(1 for row in attempts if row.attempt_kind == "checkpoint"),
            "conceptEvidence": len(evidence_rows),
            "activeDays": active_days,
            "totalMinutes": total_minutes,
        },
        "accuracy": accuracy,
        "pace": pace,
        "hintReliance": hints,
        "routine": routine,
        "mastery": mastery,
        "habits": habits,
    }
