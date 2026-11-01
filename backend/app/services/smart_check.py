"""Adaptive diagnostic questioning.

The goal is to spend the fewest answers possible to find the concepts that
need teaching. Selection is based on stored mastery uncertainty, the learner's
current plan tasks and the real questions attached to ready lessons. The
endpoint never exposes answer keys.
"""

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.learning import (
    ConceptMasterySnapshot,
    LearningPath,
    LessonVersion,
    PathLesson,
    Question,
    QuizAttempt,
)
from app.services.learner_insights import concept_label
from app.services.study_plan import build_study_plan

BAND_PRIORITY = {
    "not_enough_evidence": 0,
    "developing": 1,
    "approaching": 2,
    "demonstrated": 3,
}


def _latest_versions(db: Session, path_id: uuid.UUID) -> Dict[uuid.UUID, LessonVersion]:
    rows = (
        db.query(LessonVersion)
        .join(PathLesson, PathLesson.id == LessonVersion.path_lesson_id)
        .filter(PathLesson.path_id == path_id)
        .order_by(LessonVersion.version_number.desc())
        .all()
    )
    latest: Dict[uuid.UUID, LessonVersion] = {}
    for row in rows:
        latest.setdefault(row.path_lesson_id, row)
    return latest


def _snapshots(db: Session, owner_id: uuid.UUID) -> Dict[str, ConceptMasterySnapshot]:
    rows = (
        db.query(ConceptMasterySnapshot)
        .filter(ConceptMasterySnapshot.owner_id == owner_id)
        .order_by(ConceptMasterySnapshot.calculated_at.desc())
        .all()
    )
    latest: Dict[str, ConceptMasterySnapshot] = {}
    for row in rows:
        latest.setdefault(row.concept_id, row)
    return latest


def _package_question(version: LessonVersion, question_key: str) -> Dict[str, Any]:
    """Find the full generated question, including its options.

    Older lessons persisted only the prompt text in ``questions.prompt_json``
    while the options stayed in ``lesson_package_json``. Reading both keeps
    multiple-choice checks answerable without rewriting historical lessons.
    """
    package = version.lesson_package_json if isinstance(version.lesson_package_json, dict) else {}
    for section in ("practice", "checkpointTest"):
        for item in package.get(section, []) or []:
            if isinstance(item, dict) and item.get("questionId") == question_key:
                return item
    return {}


def _normalise_options(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    options: List[str] = []
    for item in raw:
        if isinstance(item, dict):
            value = item.get("text") or item.get("label") or item.get("value")
        else:
            value = item
        text = str(value).strip() if value is not None else ""
        if text:
            options.append(text)
    return options


def _question_payload(
    question: Question,
    lesson: PathLesson,
    version: LessonVersion,
    path: LearningPath,
    concept_id: str,
    snapshot: Optional[ConceptMasterySnapshot],
    why: str,
) -> Dict[str, Any]:
    prompt = question.prompt_json or {}
    package_question = _package_question(version, question.question_key)
    text = prompt.get("text") or prompt.get("prompt") or prompt.get("question") or ""
    if not text:
        text = str(package_question.get("prompt") or prompt)[:500]
    options = _normalise_options(prompt.get("options"))
    if not options:
        options = _normalise_options(package_question.get("options"))
    return {
        "questionKey": question.question_key,
        "lessonVersionId": str(version.id),
        "lessonId": str(lesson.id),
        "pathId": str(path.id),
        "lessonTitle": lesson.title,
        "pathTitle": (path.outline_json or {}).get("title") or f"Class {path.grade}",
        "subjectId": path.subject_id,
        "subjectLabel": str(path.subject_id or "").replace("subject-", "").replace("-", " ").title(),
        "conceptId": concept_id,
        "conceptLabel": concept_label(concept_id),
        "prompt": text,
        "type": question.type,
        "options": options,
        "difficulty": question.difficulty or "standard",
        "why": why,
        "mastery": {
            "band": snapshot.estimate_band if snapshot else "not_enough_evidence",
            "score": (
                int(round((snapshot.numeric_estimate or 0) * 100))
                if snapshot and snapshot.numeric_estimate is not None
                else None
            ),
            "evidenceCount": snapshot.evidence_count if snapshot else 0,
        },
    }


def _candidate_questions(
    db: Session, owner_id: uuid.UUID
) -> List[Dict[str, Any]]:
    paths = (
        db.query(LearningPath)
        .filter(
            LearningPath.owner_id == owner_id,
            LearningPath.status.in_(["active", "generating"]),
        )
        .order_by(LearningPath.created_at.asc())
        .all()
    )
    snapshots = _snapshots(db, owner_id)
    plan = build_study_plan(db, owner_id)
    remediation_concepts = {
        task["conceptId"] for task in plan.get("tasks", []) if task.get("conceptId")
    }
    recent = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.owner_id == owner_id)
        .order_by(QuizAttempt.occurred_at.desc())
        .limit(60)
        .all()
    )
    recently_correct = {row.question_id for row in recent if row.is_correct}
    recently_wrong = {row.question_id for row in recent if not row.is_correct}

    candidates: List[Dict[str, Any]] = []
    for path in paths:
        lessons = (
            db.query(PathLesson)
            .filter(PathLesson.path_id == path.id, PathLesson.status == "ready")
            .order_by(PathLesson.sequence.asc())
            .all()
        )
        versions = _latest_versions(db, path.id)
        for lesson in lessons:
            version = versions.get(lesson.id)
            if not version:
                continue
            questions = (
                db.query(Question)
                .filter(Question.lesson_version_id == version.id)
                .all()
            )
            for question in questions:
                concepts = [str(item) for item in (question.concept_ids or [])]
                if not concepts:
                    continue
                concept_id = concepts[0]
                snapshot = snapshots.get(concept_id)
                band = snapshot.estimate_band if snapshot else "not_enough_evidence"
                score = (
                    int(round((snapshot.numeric_estimate or 0) * 100))
                    if snapshot and snapshot.numeric_estimate is not None
                    else None
                )
                if question.id in recently_correct:
                    continue
                priority = 100 - (BAND_PRIORITY.get(band, 0) * 20)
                if concept_id in remediation_concepts:
                    priority += 15
                if question.id in recently_wrong:
                    priority += 8
                if question.difficulty == "challenge" and band != "demonstrated":
                    priority -= 12
                if not snapshot:
                    why = (
                        f"No mastery evidence exists yet for {concept_label(concept_id)}. "
                        "This question is the shortest recorded route to a first signal."
                    )
                elif band == "developing":
                    why = (
                        f"Your evidence for {concept_label(concept_id)} is developing "
                        f"({score if score is not None else 'no'}% across "
                        f"{snapshot.evidence_count} observations)."
                    )
                elif band == "approaching":
                    why = (
                        f"You are approaching mastery on {concept_label(concept_id)}. "
                        "A new answer will show whether it holds without support."
                    )
                else:
                    why = (
                        f"{concept_label(concept_id)} is already demonstrated. "
                        "This question checks whether it transfers to a new wording."
                    )
                candidates.append(
                    {
                        "priority": priority,
                        "conceptId": concept_id,
                        "band": band,
                        "question": question,
                        "lesson": lesson,
                        "version": version,
                        "path": path,
                        "snapshot": snapshot,
                        "why": why,
                    }
                )

    candidates.sort(
        key=lambda item: (
            -item["priority"],
            BAND_PRIORITY.get(item["band"], 0),
            item["lesson"].sequence,
        )
    )

    # One question per concept first, then fill with the remaining candidates.
    selected: List[Dict[str, Any]] = []
    seen_concepts = set()
    for candidate in candidates:
        if candidate["conceptId"] in seen_concepts:
            continue
        selected.append(candidate)
        seen_concepts.add(candidate["conceptId"])
    for candidate in candidates:
        if candidate not in selected:
            selected.append(candidate)
    return selected


def build_smart_check(db: Session, owner_id: uuid.UUID) -> Dict[str, Any]:
    candidates = _candidate_questions(db, owner_id)
    if not candidates:
        return {
            "state": "no_questions",
            "message": (
                "No ready question exists yet. Build a learning plan and wait for the first "
                "unit to finish generating."
            ),
            "questions": [],
            "maxQuestions": 5,
        }

    questions = [
        _question_payload(
            item["question"],
            item["lesson"],
            item["version"],
            item["path"],
            item["conceptId"],
            item["snapshot"],
            item["why"],
        )
        for item in candidates[:5]
    ]
    concepts = {item["conceptId"] for item in candidates}
    measured = {
        item["conceptId"]
        for item in candidates
        if item["snapshot"] is not None
    }
    return {
        "state": "ready",
        "message": (
            f"A short check across {len(questions)} question(s) covering "
            f"{len(concepts & {item['conceptId'] for item in candidates})} available concept(s). "
            "Answers are graded on the server and update mastery immediately."
        ),
        "questions": questions,
        "maxQuestions": 5,
        "coverage": {
            "availableConcepts": len(concepts),
            "measuredConcepts": len(measured),
            "unknownConcepts": len(concepts - measured),
        },
    }


def next_smart_question(
    db: Session,
    owner_id: uuid.UUID,
    answered_question_keys: List[str],
    max_questions: int = 5,
) -> Dict[str, Any]:
    answered = {str(key) for key in answered_question_keys if key}
    candidates = _candidate_questions(db, owner_id)
    remaining = [
        item for item in candidates
        if item["question"].question_key not in answered
    ]
    if not answered:
        pass
    if not remaining:
        return {
            "state": "complete",
            "stopReason": "no_more_questions",
            "message": "All available diagnostic questions have been answered.",
            "question": None,
            "answeredCount": len(answered),
        }

    if len(answered) >= max_questions:
        return {
            "state": "complete",
            "stopReason": "max_questions",
            "message": (
                f"You reached the {max_questions}-question limit. The evidence collected is "
                "already reflected in your plan."
            ),
            "question": None,
            "answeredCount": len(answered),
        }

    if len(answered) >= 3:
        unresolved = [
            item for item in remaining
            if item["band"] in ("not_enough_evidence", "developing")
        ]
        if not unresolved:
            return {
                "state": "complete",
                "stopReason": "enough_evidence",
                "message": (
                    "The remaining concepts already have enough evidence for the plan. "
                    "Stop here and act on the updated tasks."
                ),
                "question": None,
                "answeredCount": len(answered),
            }

    chosen = remaining[0]
    question = _question_payload(
        chosen["question"],
        chosen["lesson"],
        chosen["version"],
        chosen["path"],
        chosen["conceptId"],
        chosen["snapshot"],
        chosen["why"],
    )
    return {
        "state": "question",
        "stopReason": None,
        "message": chosen["why"],
        "question": question,
        "answeredCount": len(answered),
        "remaining": len(remaining),
    }
