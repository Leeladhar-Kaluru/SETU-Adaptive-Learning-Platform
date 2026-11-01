"""Grounded, evidence-driven coaching.

The coach never invents an explanation. It composes a response from:
- the question the learner just answered and the server's graded answer,
- the learner's real hints, timing, accuracy, mastery band and routine,
- the generated lesson's own takeaways / blocks,
- an actual source chunk (with page number) belonging to that book.

If the source has no suitable sentence, the source card is omitted instead of
being replaced with a fabricated fact.
"""

import datetime
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentChunk
from app.models.learning import ConceptMasterySnapshot, LessonVersion, PathLesson, Question
from app.services.learner_insights import build_learner_insights, concept_label

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_FACT_MARKERS = (
    "largest", "smallest", "only", "first", "called", "known as", "about",
    "almost", "more than", "less than", "percent", "%", "million", "billion",
    "thousand", "hundred", "two", "three", "four", "five",
)


def _pick(items: List[Any], seed: int) -> Any:
    if not items:
        return None
    return items[abs(seed) % len(items)]


def _clean_sentence(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _sentences(text: str, limit: int = 240) -> List[str]:
    clean = _clean_sentence(text)
    if not clean:
        return []
    pieces = [_clean_sentence(part) for part in _SENTENCE_SPLIT.split(clean)]
    return [part for part in pieces if 35 <= len(part) <= limit]


def _package_sections(package: Dict[str, Any]) -> List[str]:
    sections: List[str] = []
    for item in package.get("takeaways") or []:
        text = _clean_sentence(item)
        if text:
            sections.append(text)
    for block in package.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        heading = _clean_sentence(block.get("heading") or "")
        content = _clean_sentence(block.get("content") or "")
        if heading and content:
            sections.append(f"{heading}: {content}")
        elif content:
            sections.append(content)
    return sections


def _key_point(package: Dict[str, Any], seed: int, concept_id: Optional[str]) -> Optional[Dict[str, str]]:
    takeaways = [_clean_sentence(item) for item in (package.get("takeaways") or []) if _clean_sentence(item)]
    if takeaways:
        return {"title": "Key point from this lesson", "body": _pick(takeaways, seed)}

    blocks = [block for block in (package.get("blocks") or []) if isinstance(block, dict)]
    if concept_id:
        needle = concept_id.replace("-", " ").replace("_", " ").lower()
        matching = [
            block for block in blocks
            if needle and needle in str(block.get("content") or "").lower()
        ]
        if matching:
            blocks = matching
    if blocks:
        block = _pick(blocks, seed)
        body = _clean_sentence(block.get("content") or "")
        if body:
            title = _clean_sentence(block.get("heading") or "") or "Key point from this lesson"
            return {"title": title, "body": body[:500]}
    return None


def _source_material(db: Session, package: Dict[str, Any], seed: int) -> List[Dict[str, Any]]:
    refs = [ref for ref in (package.get("sourceRefs") or []) if isinstance(ref, dict)]
    chunk_ids = []
    for ref in refs:
        raw = ref.get("chunkId")
        if not raw:
            continue
        try:
            chunk_ids.append(uuid.UUID(str(raw)))
        except (ValueError, TypeError):
            continue
    if not chunk_ids:
        return []

    chunks = db.query(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids)).all()
    doc_ids = {chunk.document_id for chunk in chunks}
    documents = {
        doc.id: doc
        for doc in db.query(Document).filter(Document.id.in_(doc_ids)).all()
    } if doc_ids else {}

    material: List[Dict[str, Any]] = []
    for chunk in chunks:
        body = _clean_sentence(chunk.text)
        if not body:
            continue
        document = documents.get(chunk.document_id)
        sentences = _sentences(body)
        if not sentences:
            sentences = [body[:240]]
        for sentence in sentences:
            material.append(
                {
                    "text": sentence,
                    "page": chunk.page_start,
                    "sourceTitle": (
                        document.original_filename if document else "Uploaded document"
                    ),
                    "chunkId": str(chunk.id),
                }
            )
    return material


def _source_spotlight(material: List[Dict[str, Any]], seed: int) -> Optional[Dict[str, Any]]:
    if not material:
        return None
    return _pick(material, seed)


def _fun_fact(material: List[Dict[str, Any]], seed: int) -> Optional[Dict[str, Any]]:
    candidates = [
        item for item in material
        if any(marker in item["text"].lower() for marker in _FACT_MARKERS)
    ]
    if not candidates:
        return None
    return _pick(candidates, seed)


def _study_tip(insights: Dict[str, Any], *, is_correct: Optional[bool] = None) -> Optional[Dict[str, str]]:
    hint = insights.get("hintReliance") or {}
    pace = insights.get("pace") or {}
    routine = insights.get("routine") or {}
    accuracy = insights.get("accuracy") or {}

    if hint.get("state") == "measured" and (hint.get("hintRate") or 0) >= 60:
        return {
            "title": "Try one independent pass first",
            "body": (
                f"Your recorded hint use is {hint['hintRate']}% across "
                f"{hint['totalAttempts']} attempts. On the next question, attempt an answer "
                "before opening the first hint, then compare what changed."
            ),
        }
    if pace.get("medianAnswerSeconds") is not None:
        seconds = pace["medianAnswerSeconds"]
        session_note = "."
        if pace.get("medianSessionMinutes") is not None:
            minutes = round(pace["medianSessionMinutes"])
            unit = "minute" if minutes == 1 else "minutes"
            session_note = f", and your median reading session is {minutes} {unit}."
        return {
            "title": "Your working pace",
            "body": (
                f"Your median recorded answer time is {seconds:.0f} seconds"
                + session_note
                + " Use that as a baseline, not a target: slow down when the wording is new."
            ),
        }
    if routine.get("bestWindow"):
        window = routine["bestWindow"]
        return {
            "title": "Use your strongest window",
            "body": (
                f"Most of your recorded work is strongest in the {window['label'].lower()} window "
                f"({window['minutes']:g} minutes across {window['sessions']} sessions). "
                "Schedule the hardest unit there."
            ),
        }
    if accuracy.get("state") == "measured":
        return {
            "title": "Build a second data point",
            "body": (
                "There are not enough timed sessions yet for a pace baseline. "
                "Complete one more practice set so SETU can compare your next attempt."
            ),
        }
    return None


def diagnose_root_gap(
    db: Session,
    *,
    owner_id: uuid.UUID,
    lesson: PathLesson,
    concept_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """Find the earliest weak prerequisite concept behind a wrong answer.

    SETU does not have a hand-authored prerequisite graph, so this uses the
    real structure of the uploaded book: concepts taught in earlier units of
    the same path, ordered by lesson sequence and then by their recorded
    mastery. The result names the earliest concept whose evidence is weaker
    than the concept just tested. When nothing earlier is weak, it returns the
    tested concept itself so the UI never claims a cause that is not recorded.
    """
    if not concept_ids:
        return None

    earlier_lessons = (
        db.query(PathLesson)
        .filter(
            PathLesson.path_id == lesson.path_id,
            PathLesson.sequence < lesson.sequence,
        )
        .order_by(PathLesson.sequence.asc())
        .all()
    )
    if not earlier_lessons:
        return None

    versions = (
        db.query(LessonVersion)
        .filter(LessonVersion.path_lesson_id.in_([row.id for row in earlier_lessons]))
        .all()
    )
    version_by_lesson = {}
    for version in versions:
        current = version_by_lesson.get(version.path_lesson_id)
        if current is None or (version.version_number or 0) > (current.version_number or 0):
            version_by_lesson[version.path_lesson_id] = version
    version_ids = [version.id for version in version_by_lesson.values()]
    if not version_ids:
        return None

    questions = (
        db.query(Question)
        .filter(Question.lesson_version_id.in_(version_ids))
        .all()
    )
    concepts_by_version: Dict[uuid.UUID, List[str]] = {}
    for question in questions:
        for concept in question.concept_ids or []:
            value = str(concept)
            concepts_by_version.setdefault(question.lesson_version_id, [])
            if value not in concepts_by_version[question.lesson_version_id]:
                concepts_by_version[question.lesson_version_id].append(value)

    latest: Dict[str, Any] = {}
    snapshots = (
        db.query(ConceptMasterySnapshot)
        .filter(ConceptMasterySnapshot.owner_id == owner_id)
        .order_by(ConceptMasterySnapshot.calculated_at.desc())
        .all()
    )
    for snapshot in snapshots:
        latest.setdefault(snapshot.concept_id, snapshot)

    rank = {"not_enough_evidence": 0, "developing": 1, "approaching": 2, "demonstrated": 3}
    tested = concept_ids[0]
    tested_snapshot = latest.get(tested)
    tested_rank = rank.get(tested_snapshot.estimate_band, 0) if tested_snapshot else 0
    tested_evidence = (tested_snapshot.evidence_count or 0) if tested_snapshot else 0
    tested_score = (
        tested_snapshot.numeric_estimate
        if tested_snapshot and tested_snapshot.numeric_estimate is not None
        else None
    )

    candidates = []
    for index, earlier in enumerate(earlier_lessons):
        version = version_by_lesson.get(earlier.id)
        if not version:
            continue
        for concept_id in concepts_by_version.get(version.id, []):
            if concept_id in concept_ids or concept_id == tested:
                continue
            snapshot = latest.get(concept_id)
            if snapshot is None:
                continue
            band = snapshot.estimate_band
            concept_rank = rank.get(band, 0)
            if concept_rank >= 3:
                continue
            # A single wrong answer often leaves the tested concept with one
            # observation, so demanding a strictly lower band would hide the
            # earlier weak concept that is the actual prerequisite gap. When
            # the tested concept already has enough evidence, only a weaker
            # (or equal-band, lower-scoring) earlier concept qualifies.
            if tested_evidence >= 2:
                if concept_rank > tested_rank:
                    continue
                if (
                    concept_rank == tested_rank
                    and tested_score is not None
                    and snapshot.numeric_estimate is not None
                    and snapshot.numeric_estimate > tested_score + 0.05
                ):
                    continue
            elif band not in ("not_enough_evidence", "developing"):
                continue
            candidates.append(
                    {
                        "conceptId": concept_id,
                        "label": concept_label(concept_id),
                        "band": band,
                        "score": (
                            int(round((snapshot.numeric_estimate or 0) * 100))
                            if snapshot.numeric_estimate is not None
                            else None
                        ),
                        "evidenceCount": snapshot.evidence_count or 0,
                        "lessonTitle": earlier.title,
                        "sequence": earlier.sequence,
                        "distance": lesson.sequence - earlier.sequence,
                    }
                )

    if not candidates:
        if tested_snapshot and tested_rank < 3:
            return {
                "conceptId": tested,
                "label": concept_label(tested),
                "band": tested_snapshot.estimate_band,
                "score": (
                    int(round((tested_snapshot.numeric_estimate or 0) * 100))
                    if tested_snapshot.numeric_estimate is not None
                    else None
                ),
                "evidenceCount": tested_snapshot.evidence_count or 0,
                "lessonTitle": lesson.title,
                "sequence": lesson.sequence,
                "distance": 0,
                "reason": (
                    "No earlier weak concept is recorded, so the tested concept itself "
                    "is the best-supported gap."
                ),
            }
        return None

    candidates.sort(
        key=lambda item: (
            rank.get(item["band"], 0),
            item["sequence"],
            -(item["distance"]),
        )
    )
    best = candidates[0]
    best["reason"] = (
        f"{best['label']} was taught earlier in “{best['lessonTitle']}” and its "
        f"recorded evidence is {best['band'].replace('_', ' ')} "
        f"({best['score'] if best['score'] is not None else 'no score'}% across "
        f"{best['evidenceCount']} evidence point(s)), so it is the earliest recorded "
        "prerequisite gap behind this answer."
    )
    return best


def _attempt_headline(
    concept: str, is_correct: bool, seed: int, hints_used: int, mastery_band: str
) -> str:
    if is_correct:
        options = [
            f"{concept} is holding.",
            f"Correct — {concept} is getting steadier.",
            f"That answer landed on {concept}.",
        ]
        if hints_used > 0:
            options.append(f"With support, you still reached {concept}.")
        return _pick(options, seed)
    options = [
        f"Not quite — this one turns on {concept}.",
        f"The gap here is {concept}, not the whole unit.",
        f"That answer missed {concept}. Let's pin it down.",
    ]
    if mastery_band == "developing":
        options.append(f"{concept} needs another pass before it sticks.")
    return _pick(options, seed)


def _attempt_body(
    *,
    concept: str,
    correct_answer: Any,
    response: Any,
    is_correct: bool,
    hints_used: int,
    elapsed_seconds: int,
    mastery: Dict[str, Any],
    insights: Dict[str, Any],
) -> str:
    pieces: List[str] = []
    if not is_correct:
        pieces.append(f"The correct answer is {correct_answer}.")
        if response is not None and str(response).strip():
            pieces.append(f"You answered {response}.")
    else:
        pieces.append("The server graded this response as correct.")

    if hints_used > 0:
        pieces.append(
            f"You used {hints_used} hint{'s' if hints_used != 1 else ''} on this attempt."
        )
    else:
        pieces.append("You answered without opening a hint.")

    median = (insights.get("pace") or {}).get("medianAnswerSeconds")
    if elapsed_seconds > 0:
        if median and elapsed_seconds >= median * 1.8 and elapsed_seconds >= 45:
            pieces.append(
                f"This took {elapsed_seconds}s, well above your {median:.0f}s median; "
                "the wording may be the blocker, not the idea."
            )
        elif median and elapsed_seconds <= max(8, median / 3) and not is_correct:
            pieces.append(
                f"This took only {elapsed_seconds}s, so it may be a rushed read rather than a missing idea."
            )
        elif elapsed_seconds >= 90:
            pieces.append(f"You spent {elapsed_seconds}s working through it.")

    band = mastery.get("band")
    evidence_count = mastery.get("evidenceCount")
    if band and evidence_count:
        pieces.append(
            f"Your {concept} evidence is now {str(band).replace('_', ' ')} "
            f"across {evidence_count} observation{'s' if evidence_count != 1 else ''}."
        )
    return " ".join(pieces)


def build_attempt_coaching(
    db: Session,
    *,
    owner_id: uuid.UUID,
    attempt_id: uuid.UUID,
    lesson: PathLesson,
    lesson_version: LessonVersion,
    question: Question,
    response: Any,
    is_correct: bool,
    hints_used: List[str],
    elapsed_seconds: int,
    mastery: Dict[str, Any],
    next_action: Dict[str, Any],
) -> Dict[str, Any]:
    package = lesson_version.lesson_package_json or {}
    concept_ids = [str(item) for item in (question.concept_ids or [])]
    concept = concept_label(concept_ids[0]) if concept_ids else "this concept"
    seed = attempt_id.int if isinstance(attempt_id, uuid.UUID) else uuid.uuid4().int
    insights = build_learner_insights(db, owner_id)

    key_point = _key_point(package, seed, concept_ids[0] if concept_ids else None)
    material = _source_material(db, package, seed)
    spotlight = _source_spotlight(material, seed)
    tip = _study_tip(insights, is_correct=is_correct)
    correct_answer = (question.answer_key_json or {}).get("answer")
    root_gap = None if is_correct else diagnose_root_gap(
        db,
        owner_id=owner_id,
        lesson=lesson,
        concept_ids=concept_ids,
    )

    return {
        "id": f"attempt-{attempt_id}",
        "scope": "attempt",
        "tone": "celebrate" if is_correct else "retry",
        "headline": _attempt_headline(
            concept,
            is_correct,
            seed,
            len(hints_used),
            str(mastery.get("band") or ""),
        ),
        "body": _attempt_body(
            concept=concept,
            correct_answer=correct_answer,
            response=response,
            is_correct=is_correct,
            hints_used=len(hints_used),
            elapsed_seconds=elapsed_seconds,
            mastery=mastery,
            insights=insights,
        ),
        "conceptId": concept_ids[0] if concept_ids else None,
        "conceptLabel": concept if concept_ids else None,
        "rootGap": root_gap,
        "mastery": mastery,
        "nextStep": {
            "title": next_action.get("title"),
            "reason": next_action.get("reason"),
            "action": next_action.get("action"),
        },
        "keyPoint": key_point,
        "source": ({
            "page": spotlight["page"],
            "title": spotlight["sourceTitle"],
            "excerpt": spotlight["text"],
        } if spotlight else None),
        "studyTip": tip,
        "evidence": {
            "isCorrect": is_correct,
            "hintsUsed": len(hints_used),
            "elapsedSeconds": elapsed_seconds,
            "masteryBand": mastery.get("band"),
            "masteryEvidenceCount": mastery.get("evidenceCount"),
            "lessonTitle": lesson.title,
        },
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def build_lesson_coaching(
    db: Session,
    *,
    owner_id: uuid.UUID,
    lesson: PathLesson,
    lesson_version: LessonVersion,
) -> Dict[str, Any]:
    package = lesson_version.lesson_package_json or {}
    seed = uuid.uuid5(uuid.NAMESPACE_URL, f"setu-coach:{lesson.id}").int
    insights = build_learner_insights(db, owner_id)
    material = _source_material(db, package, seed)
    spotlight = _source_spotlight(material, seed)
    fun_fact = _fun_fact(material, seed)
    key_point = _key_point(package, seed, None)
    tip = _study_tip(insights)

    questions = (
        db.query(Question)
        .filter(Question.lesson_version_id == lesson_version.id)
        .all()
    )
    concept_ids: List[str] = []
    challenge_count = 0
    for question in questions:
        if question.difficulty == "challenge":
            challenge_count += 1
        for concept in question.concept_ids or []:
            value = str(concept)
            if value not in concept_ids:
                concept_ids.append(value)

    mastery_by_concept = {
        item["conceptId"]: item for item in (insights.get("mastery") or {}).get("concepts", [])
    }
    developing = [
        concept_label(concept_id)
        for concept_id in concept_ids
        if (mastery_by_concept.get(concept_id) or {}).get("band") == "developing"
    ]

    moments: List[Dict[str, Any]] = []
    if key_point:
        moments.append(
            {
                "id": f"key:{lesson.id}",
                "kind": "key_point",
                "title": key_point["title"],
                "body": key_point["body"],
                "evidence": "Lesson package",
            }
        )
    if spotlight:
        moments.append(
            {
                "id": f"source:{lesson.id}",
                "kind": "source_spotlight",
                "title": f"From your book, page {spotlight['page']}",
                "body": spotlight["text"],
                "evidence": spotlight["sourceTitle"],
                "source": {
                    "page": spotlight["page"],
                    "title": spotlight["sourceTitle"],
                },
            }
        )
    if fun_fact:
        moments.append(
            {
                "id": f"fact:{lesson.id}",
                "kind": "fun_fact",
                "title": f"A detail worth noticing · page {fun_fact['page']}",
                "body": fun_fact["text"],
                "evidence": fun_fact["sourceTitle"],
                "source": {
                    "page": fun_fact["page"],
                    "title": fun_fact["sourceTitle"],
                },
            }
        )
    if tip:
        moments.append(
            {
                "id": f"tip:{lesson.id}",
                "kind": "study_tip",
                "title": tip["title"],
                "body": tip["body"],
                "evidence": "Your recorded study events",
            }
        )

    if challenge_count or developing:
        if challenge_count and developing:
            body = (
                f"This unit has {challenge_count} challenge question"
                f"{'s' if challenge_count != 1 else ''}, and your recorded evidence on "
                f"{', '.join(developing[:2])} is developing. Do the guided practice before the checkpoint."
            )
        elif challenge_count:
            body = (
                f"This unit includes {challenge_count} challenge question"
                f"{'s' if challenge_count != 1 else ''}. Use the worked example before attempting "
                "the checkpoint without hints."
            )
        else:
            body = (
                f"Your recorded evidence on {', '.join(developing[:2])} is developing. "
                "This unit contains that concept, so expect to slow down and use the practice step."
            )
        moments.append(
            {
                "id": f"challenge:{lesson.id}",
                "kind": "challenge",
                "title": "This unit has a tough edge",
                "body": body,
                "evidence": "Lesson questions and mastery evidence",
            }
        )

    intro = (
        f"{lesson.title} has {len(moments)} coaching card"
        f"{'s' if len(moments) != 1 else ''} built from this lesson, its source pages and your recorded work."
    )
    if challenge_count:
        intro += f" {challenge_count} question{'s' if challenge_count != 1 else ''} are marked challenge."
    if developing:
        intro += f" Your evidence is still developing on {', '.join(developing[:2])}."

    return {
        "lessonId": str(lesson.id),
        "lessonTitle": lesson.title,
        "packageLessonId": package.get("lessonId"),
        "state": "ready" if moments else "no_source_material",
        "intro": intro,
        "difficulty": "challenge" if challenge_count else "standard",
        "challengeCount": challenge_count,
        "concepts": [concept_label(concept_id) for concept_id in concept_ids],
        "developingConcepts": developing,
        "moments": moments[:6],
        "autoShowId": f"challenge:{lesson.id}" if (challenge_count or developing) else None,
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
