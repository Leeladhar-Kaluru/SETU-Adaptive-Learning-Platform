import datetime
import re
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.learning import (
    ConceptEvidence,
    ConceptMasterySnapshot,
    LearningPath,
    LessonVersion,
    PathLesson,
    Question,
    QuizAttempt,
    StudyEvent,
)
from app.services.adaptive_engine import adaptive_engine
from app.services.coach_service import build_attempt_coaching
from app.services.generation_queue import enqueue_lesson_generation


class AttemptNotFoundError(Exception):
    """The question does not exist or the learner does not own it."""


class UnsupportedQuestionTypeError(Exception):
    """The question type cannot be graded deterministically."""


class InvalidAnswerKeyError(Exception):
    """The question has no validated answer key."""


@dataclass(frozen=True)
class AttemptOutcome:
    attempt_id: uuid.UUID
    is_correct: bool
    score: float
    feedback: str
    correct_answer: Any
    mastery: dict
    next_action: dict
    already_recorded: bool
    concept_ids: list
    coaching: Optional[dict] = None


def _normalize(value: Any) -> str:
    return " ".join(str(value).split()).strip().casefold()


_SHORT_WORD = re.compile(r"[a-z0-9]+")
_SHORT_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "with", "that", "this",
    "from", "have", "has", "had", "but", "not", "you", "your", "all",
    "can", "get", "out", "one", "two", "his", "her", "its", "our",
}


def _short_text_tokens(value: Any) -> set[str]:
    normalized = _normalize(value)
    return {
        token
        for token in _SHORT_WORD.findall(normalized)
        if len(token) > 1 and token not in _SHORT_STOPWORDS
    }


def _short_text_match(response: Any, accepted: list) -> bool:
    """Grade a short answer tolerantly, the way a teacher reads one.

    Kids write "gondwana" where the key says "Gondwana land". Exact string
    equality is too brittle, so an answer is correct when it is an exact
    accepted form, or when one side's content words are contained in the
    other side's, or when nearly all expected content words appear.
    """
    given = _normalize(response)
    accepted_values = [_normalize(item) for item in accepted if str(item).strip()]
    if not accepted_values or not given:
        return False
    if given in accepted_values:
        return True
    given_tokens = _short_text_tokens(given)
    if not given_tokens:
        return False
    for expected_text in accepted_values:
        expected_tokens = _short_text_tokens(expected_text)
        if not expected_tokens:
            continue
        if expected_tokens <= given_tokens or given_tokens <= expected_tokens:
            return True
        overlap = len(given_tokens & expected_tokens)
        if overlap >= max(2, len(expected_tokens) - 1):
            return True
    return False


def grade_response(question: Question, response: Any) -> tuple[bool, float, str, Any]:
    answer_key = question.answer_key_json or {}
    expected = answer_key.get("answer")
    if expected is None or str(expected).strip() == "":
        raise InvalidAnswerKeyError("This question has no validated answer key.")
    feedback = str(answer_key.get("feedback") or "")

    if question.type == "multiple_choice":
        correct = _normalize(response) == _normalize(expected)
    elif question.type == "numeric":
        try:
            given_value = float(str(response).strip().replace(",", ""))
            expected_value = float(str(expected).strip().replace(",", ""))
        except (TypeError, ValueError) as exc:
            raise ValueError("Enter a numeric answer.") from exc
        correct = abs(given_value - expected_value) <= max(1e-6, abs(expected_value) * 0.001)
    elif question.type == "short_text":
        accepted = answer_key.get("acceptedAnswers") or [expected]
        correct = _short_text_match(response, accepted)
    else:
        raise UnsupportedQuestionTypeError(
            f"Question type '{question.type}' cannot be graded deterministically."
        )
    # Model-authored feedback may assert "Correct!" even for a wrong answer, so
    # only surface it when the server has actually graded the response correct.
    display_feedback = feedback if correct else f"Not quite. The correct answer is: {expected}."
    return correct, 1.0 if correct else 0.0, display_feedback, expected


def _concept_evidence_records(db: Session, owner_id: uuid.UUID, concept_id: str) -> list[dict]:
    evidence_rows = (
        db.query(ConceptEvidence)
        .filter(
            ConceptEvidence.owner_id == owner_id,
            ConceptEvidence.concept_id == concept_id,
        )
        .order_by(ConceptEvidence.occurred_at.asc(), ConceptEvidence.id.asc())
        .all()
    )
    return [
        {"outcome": row.outcome, "hints_used": row.hints_used or 0}
        for row in evidence_rows
    ]


def _mastery_for_concept(db: Session, owner_id: uuid.UUID, concept_id: str) -> dict:
    return adaptive_engine.calculate_mastery(
        _concept_evidence_records(db, owner_id, concept_id)
    )


def _upsert_mastery_snapshot(
    db: Session, owner_id: uuid.UUID, concept_id: str, mastery: dict
) -> None:
    snapshot = (
        db.query(ConceptMasterySnapshot)
        .filter(
            ConceptMasterySnapshot.owner_id == owner_id,
            ConceptMasterySnapshot.concept_id == concept_id,
        )
        .first()
    )
    if snapshot is None:
        snapshot = ConceptMasterySnapshot(
            owner_id=owner_id,
            concept_id=concept_id,
            estimate_band=mastery["band"],
            numeric_estimate=mastery["score"],
            evidence_count=mastery["evidenceCount"],
            explanation_json=mastery,
        )
        db.add(snapshot)
    else:
        snapshot.estimate_band = mastery["band"]
        snapshot.numeric_estimate = mastery["score"]
        snapshot.evidence_count = mastery["evidenceCount"]
        snapshot.explanation_json = mastery
    db.flush()


def grade_and_record_attempt(
    db: Session,
    *,
    owner_id: uuid.UUID,
    lesson_version_id: uuid.UUID,
    question_key: str,
    response: Any,
    hint_level: int = 0,
    hints_used: Optional[list] = None,
    elapsed_seconds: int = 0,
    attempt_kind: str = "practice",
    idempotency_key: Optional[str] = None,
) -> AttemptOutcome:
    question = (
        db.query(Question)
        .filter(
            Question.lesson_version_id == lesson_version_id,
            Question.question_key == question_key,
        )
        .first()
    )
    if question is None:
        raise AttemptNotFoundError("Question not found for this lesson.")

    lesson_version = (
        db.query(LessonVersion).filter(LessonVersion.id == lesson_version_id).first()
    )
    if lesson_version is None:
        raise AttemptNotFoundError("Question not found for this lesson.")
    lesson = db.query(PathLesson).filter(PathLesson.id == lesson_version.path_lesson_id).first()
    path = db.query(LearningPath).filter(LearningPath.id == lesson.path_id).first() if lesson else None
    if lesson is None or path is None or path.owner_id != owner_id:
        raise AttemptNotFoundError("Question not found for this lesson.")

    concept_ids = list(question.concept_ids or [])
    feedback = str((question.answer_key_json or {}).get("feedback") or "")

    if idempotency_key:
        existing = (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.owner_id == owner_id,
                QuizAttempt.sync_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is not None:
            mastery = (
                _mastery_for_concept(db, owner_id, str(concept_ids[0]))
                if concept_ids
                else adaptive_engine.calculate_mastery([])
            )
            return AttemptOutcome(
                attempt_id=existing.id,
                is_correct=bool(existing.is_correct),
                score=float(existing.score or 0.0),
                feedback=(
                    feedback
                    if existing.is_correct
                    else f"Not quite. The correct answer is: {(question.answer_key_json or {}).get('answer')}."
                ),
                correct_answer=(question.answer_key_json or {}).get("answer"),
                mastery=mastery,
                next_action=adaptive_engine.determine_next_action(mastery),
                already_recorded=True,
                concept_ids=concept_ids,
            )

    is_correct, score, feedback, correct_answer = grade_response(question, response)
    hint_count = len(hints_used) if hints_used is not None else hint_level

    attempt = QuizAttempt(
        owner_id=owner_id,
        question_id=question.id,
        lesson_version_id=lesson_version_id,
        response_json=response,
        score=score,
        is_correct=is_correct,
        hint_level=hint_level,
        hints_used=hints_used,
        elapsed_seconds=elapsed_seconds,
        attempt_kind=attempt_kind,
        sync_idempotency_key=idempotency_key,
    )
    db.add(attempt)
    db.flush()

    mastery: dict = adaptive_engine.calculate_mastery([])
    for index, concept_id in enumerate(concept_ids):
        concept_id = str(concept_id)
        outcome = "correct" if is_correct else "incorrect"
        evidence = ConceptEvidence(
            owner_id=owner_id,
            concept_id=concept_id,
            source_attempt_id=attempt.id,
            evidence_type=f"{attempt_kind}_attempt",
            outcome=outcome,
            weight=1.0,
            hints_used=hint_count,
            rationale=f"{attempt_kind.title()} attempt {outcome} with {hint_count} hint(s) used.",
        )
        db.add(evidence)
        db.flush()
        concept_mastery = _mastery_for_concept(db, owner_id, concept_id)
        _upsert_mastery_snapshot(db, owner_id, concept_id, concept_mastery)
        if index == 0:
            mastery = concept_mastery

    study_event = StudyEvent(
        owner_id=owner_id,
        path_id=path.id,
        lesson_id=str(lesson.id),
        lesson_title=lesson.title,
        event_type=attempt_kind,
        seconds=elapsed_seconds,
        score=score,
        occurred_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(study_event)

    next_action = adaptive_engine.determine_next_action(mastery)

    remediation_injected = False
    if concept_ids and mastery.get("band") == "developing" and attempt_kind == "checkpoint":
        first_concept = str(concept_ids[0])
        safe_rem_key = f"rem_{lesson.sequence}_{first_concept[:16]}"
        existing_rem = (
            db.query(PathLesson)
            .filter(
                PathLesson.path_id == path.id,
                PathLesson.lesson_key == safe_rem_key,
            )
            .first()
        )
        if existing_rem is None:
            later_lessons = (
                db.query(PathLesson)
                .filter(
                    PathLesson.path_id == path.id,
                    PathLesson.sequence > lesson.sequence,
                )
                .all()
            )
            for later_lesson in later_lessons:
                later_lesson.sequence += 1

            remediation_title = f"Foundations & Guided Refresher: {lesson.title}"
            new_lesson = PathLesson(
                path_id=path.id,
                lesson_key=safe_rem_key,
                title=remediation_title,
                sequence=lesson.sequence + 1,
                status="queued",
            )
            db.add(new_lesson)
            db.flush()

            enqueue_lesson_generation(
                db, owner_id=owner_id, path=path, lessons=[new_lesson]
            )
            remediation_injected = True

            next_action["remediationInjected"] = True
            next_action["remediationLessonId"] = str(new_lesson.id)
            next_action["remediationTitle"] = remediation_title
            next_action["title"] = f"Adaptive Refresher: {remediation_title}"
            next_action["reason"] = (
                f"Detected foundational misconceptions on {first_concept}. "
                "We added a guided refresher unit to your Learning Path."
            )

    if not remediation_injected:
        db.commit()

    coaching = build_attempt_coaching(
        db,
        owner_id=owner_id,
        attempt_id=attempt.id,
        lesson=lesson,
        lesson_version=lesson_version,
        question=question,
        response=response,
        is_correct=is_correct,
        hints_used=list(hints_used or []),
        elapsed_seconds=elapsed_seconds,
        mastery=mastery,
        next_action=next_action,
    )

    return AttemptOutcome(
        attempt_id=attempt.id,
        is_correct=is_correct,
        score=score,
        feedback=feedback,
        correct_answer=correct_answer,
        mastery=mastery,
        next_action=next_action,
        already_recorded=False,
        concept_ids=concept_ids,
        coaching=coaching,
    )
