"""Cross-book adaptive study planning from recorded evidence.

The planner reads every active learning path, the concepts each ready lesson
actually teaches, the learner's latest mastery snapshots and the learner's
attempt / reading history. It then returns one ordered plan across all books.
No task is produced unless a real lesson and a real reason exist.
"""

import datetime
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.documents import Document
from app.models.curriculum import Subject
from app.models.learning import (
    ConceptMasterySnapshot,
    LearningPath,
    LessonVersion,
    PathLesson,
    Question,
    QuizAttempt,
    StudyEvent,
)
from app.services.learner_insights import concept_label

UTC = datetime.timezone.utc

BAND_RANK = {
    "not_enough_evidence": 0,
    "developing": 1,
    "approaching": 2,
    "demonstrated": 3,
}

TASK_LABELS = {
    "remediate": "Rebuild the foundation",
    "review": "Review this concept",
    "continue": "Finish this unit",
    "next_lesson": "Open the next unit",
    "practice": "Build evidence",
    "stretch": "Take the stretch task",
}

SLOT_LABELS = ("Start here", "Next", "Then", "Stretch")


def _utc_naive(value: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _subject_labels(db: Session) -> Dict[str, str]:
    """Canonical subject names straight from the reference table.

    The slug fallback ("subject-math" -> "Math") is only used when a subject
    row is missing, so the plan always speaks the catalogue's own words.
    """
    labels = {
        str(row.id): str(row.canonical_name).strip()
        for row in db.query(Subject.id, Subject.canonical_name).all()
        if row.canonical_name and str(row.canonical_name).strip()
    }
    return labels


def _subject_label(subject_id: str, labels: Optional[Dict[str, str]] = None) -> str:
    if labels and labels.get(str(subject_id)):
        return labels[str(subject_id)]
    value = str(subject_id or "").replace("subject-", "").replace("-", " ").strip()
    return value[:1].upper() + value[1:] if value else "Subject"


def _percent(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value * 100))


def _path_title(path: LearningPath, labels: Optional[Dict[str, str]] = None) -> str:
    outline = path.outline_json or {}
    title = outline.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return f"Class {path.grade} {_subject_label(path.subject_id, labels)}"


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
        if row.path_lesson_id not in latest:
            latest[row.path_lesson_id] = row
    return latest


def _path_concepts(
    db: Session, version_ids: List[uuid.UUID]
) -> Tuple[Dict[uuid.UUID, List[str]], Dict[str, List[uuid.UUID]]]:
    if not version_ids:
        return {}, {}
    questions = (
        db.query(Question)
        .filter(Question.lesson_version_id.in_(version_ids))
        .all()
    )
    by_version: Dict[uuid.UUID, List[str]] = {}
    by_concept: Dict[str, List[uuid.UUID]] = {}
    for question in questions:
        for concept in question.concept_ids or []:
            concept_id = str(concept)
            by_version.setdefault(question.lesson_version_id, [])
            if concept_id not in by_version[question.lesson_version_id]:
                by_version[question.lesson_version_id].append(concept_id)
            by_concept.setdefault(concept_id, [])
            if question.lesson_version_id not in by_concept[concept_id]:
                by_concept[concept_id].append(question.lesson_version_id)
    return by_version, by_concept


def _latest_snapshot_map(db: Session, owner_id: uuid.UUID) -> Dict[str, ConceptMasterySnapshot]:
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


def _book_summary(
    path: LearningPath,
    document: Optional[Document],
    lessons: List[Dict[str, Any]],
    snapshots: Dict[str, ConceptMasterySnapshot],
    path_concepts: List[str],
    labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    bands = {"demonstrated": 0, "approaching": 0, "developing": 0, "notEnoughEvidence": 0}
    scored = []
    for concept_id in path_concepts:
        snapshot = snapshots.get(concept_id)
        if snapshot is None:
            bands["notEnoughEvidence"] += 1
            continue
        if snapshot.estimate_band == "demonstrated":
            bands["demonstrated"] += 1
        elif snapshot.estimate_band == "approaching":
            bands["approaching"] += 1
        elif snapshot.estimate_band == "developing":
            bands["developing"] += 1
        else:
            bands["notEnoughEvidence"] += 1
        scored.append(
            {
                "conceptId": concept_id,
                "label": concept_label(concept_id),
                "band": snapshot.estimate_band,
                "score": _percent(snapshot.numeric_estimate),
                "evidenceCount": snapshot.evidence_count or 0,
            }
        )
    scored.sort(key=lambda item: (BAND_RANK.get(item["band"], 0), item["score"] or 0))
    focus = scored[0] if scored else None
    strongest = scored[-1] if scored else None

    completed = sum(1 for lesson in lessons if lesson["completed"])
    ready = sum(1 for lesson in lessons if lesson["status"] == "ready")
    in_progress = next((lesson for lesson in lessons if lesson["inProgress"]), None)
    next_ready = next(
        (lesson for lesson in lessons if lesson["status"] == "ready" and not lesson["completed"]),
        None,
    )

    return {
        "pathId": str(path.id),
        "title": _path_title(path, labels),
        "documentTitle": document.original_filename if document else None,
        "grade": path.grade,
        "subjectId": path.subject_id,
        "subjectLabel": _subject_label(path.subject_id, labels),
        "status": path.status,
        "totalLessons": len(lessons),
        "readyLessons": ready,
        "completedLessons": completed,
        "mastery": bands,
        "strongestConcept": strongest,
        "focusConcept": focus,
        "inProgressLesson": {
            "lessonId": in_progress["lessonId"],
            "title": in_progress["title"],
        } if in_progress else None,
        "nextLesson": {
            "lessonId": next_ready["lessonId"],
            "title": next_ready["title"],
        } if next_ready else None,
    }


def build_study_plan(db: Session, owner_id: uuid.UUID) -> Dict[str, Any]:
    now = datetime.datetime.now(UTC).replace(tzinfo=None)
    paths = (
        db.query(LearningPath)
        .filter(
            LearningPath.owner_id == owner_id,
            LearningPath.status.in_(["active", "generating"]),
        )
        .order_by(LearningPath.created_at.asc())
        .all()
    )
    documents = {
        doc.id: doc
        for doc in db.query(Document).filter(Document.owner_id == owner_id).all()
    }
    labels = _subject_labels(db)
    snapshots = _latest_snapshot_map(db, owner_id)
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.owner_id == owner_id)
        .order_by(QuizAttempt.occurred_at.desc())
        .all()
    )
    events = (
        db.query(StudyEvent)
        .filter(StudyEvent.owner_id == owner_id)
        .order_by(StudyEvent.occurred_at.desc())
        .all()
    )
    # StudyEvent.lesson_id is a free-form string: a PathLesson UUID or a lesson_key.
    # Resolve every reference to the lesson UUID so reading evidence attaches to the plan.
    def _normalized_ref(ref: str) -> str:
        try:
            return str(uuid.UUID(ref))
        except (ValueError, TypeError):
            return ref

    ref_to_lesson: Dict[str, uuid.UUID] = {}
    uuid_refs: List[uuid.UUID] = []
    key_refs: List[str] = []
    seen_refs: set[str] = set()
    for event in events:
        if not event.lesson_id or event.lesson_id in seen_refs:
            continue
        seen_refs.add(event.lesson_id)
        try:
            uuid_refs.append(uuid.UUID(event.lesson_id))
        except (ValueError, TypeError):
            key_refs.append(event.lesson_id)
    if uuid_refs:
        for lesson in (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(PathLesson.id.in_(uuid_refs), LearningPath.owner_id == owner_id)
            .all()
        ):
            ref_to_lesson[str(lesson.id)] = lesson.id
    if key_refs:
        for lesson in (
            db.query(PathLesson)
            .join(LearningPath, LearningPath.id == PathLesson.path_id)
            .filter(
                PathLesson.lesson_key.in_(key_refs),
                LearningPath.owner_id == owner_id,
            )
            .all()
        ):
            ref_to_lesson[lesson.lesson_key] = lesson.id
    events_by_lesson: Dict[uuid.UUID, List[StudyEvent]] = {}
    for event in events:
        if not event.lesson_id:
            continue
        resolved = ref_to_lesson.get(_normalized_ref(event.lesson_id))
        if resolved is not None:
            events_by_lesson.setdefault(resolved, []).append(event)

    all_tasks: List[Dict[str, Any]] = []
    books: List[Dict[str, Any]] = []
    roadmaps: List[Dict[str, Any]] = []
    waiting_books = 0

    for path in paths:
        lessons = (
            db.query(PathLesson)
            .filter(PathLesson.path_id == path.id)
            .order_by(PathLesson.sequence.asc())
            .all()
        )
        versions = _latest_versions(db, path.id)
        version_ids = [version.id for version in versions.values()]
        concepts_by_version, versions_by_concept = _path_concepts(db, version_ids)
        attempts_by_version: Dict[uuid.UUID, List[QuizAttempt]] = {}
        for attempt in attempts:
            attempts_by_version.setdefault(attempt.lesson_version_id, []).append(attempt)

        path_concepts: List[str] = []
        lesson_rows: List[Dict[str, Any]] = []
        concept_lessons: Dict[str, List[Dict[str, Any]]] = {}
        for lesson in lessons:
            version = versions.get(lesson.id)
            concept_ids = concepts_by_version.get(version.id, []) if version else []
            for concept_id in concept_ids:
                if concept_id not in path_concepts:
                    path_concepts.append(concept_id)
            lesson_attempts = attempts_by_version.get(version.id, []) if version else []
            lesson_events = events_by_lesson.get(lesson.id, [])
            reading_events = [event for event in lesson_events if event.event_type == "reading"]
            reading_seconds = sum(event.seconds or 0 for event in reading_events)
            checkpoint_attempts = [row for row in lesson_attempts if row.attempt_kind == "checkpoint"]
            practice_attempts = [row for row in lesson_attempts if row.attempt_kind != "checkpoint"]
            last_attempt = max(
                (row.occurred_at for row in lesson_attempts if row.occurred_at),
                default=None,
            )
            completed = bool(checkpoint_attempts) and lesson.status == "ready"
            in_progress = (
                lesson.status == "ready"
                and not completed
                and (bool(reading_events) or bool(practice_attempts))
            )
            opened = bool(reading_events) or bool(lesson_attempts)
            correct = sum(1 for row in lesson_attempts if row.is_correct)
            row = {
                "lessonId": str(lesson.id),
                "lessonKey": lesson.lesson_key,
                "title": lesson.title,
                "sequence": lesson.sequence,
                "status": lesson.status,
                "concepts": [concept_label(concept_id) for concept_id in concept_ids],
                "attempts": len(lesson_attempts),
                "correct": correct,
                "readingMinutes": round(reading_seconds / 60, 1),
                "completed": completed,
                "inProgress": in_progress,
                "opened": opened,
                "lastAttemptAt": _utc_naive(last_attempt).isoformat() if last_attempt else None,
                "estimatedMinutes": (
                    (version.lesson_package_json or {}).get("estimatedMinutes")
                    if version and isinstance(version.lesson_package_json, dict)
                    else None
                ),
            }
            lesson_rows.append(row)
            for concept_id in concept_ids:
                concept_lessons.setdefault(concept_id, []).append(row)

        ready_rows = [row for row in lesson_rows if row["status"] == "ready"]
        if not ready_rows and lessons:
            waiting_books += 1

        # 1. Concept-level remediation and review over ready lessons.
        for concept_id in path_concepts:
            target_rows = [
                row for row in concept_lessons.get(concept_id, [])
                if row["status"] == "ready"
            ]
            if not target_rows:
                continue
            target = next(
                (row for row in target_rows if row["inProgress"]),
                target_rows[0],
            )
            snapshot = snapshots.get(concept_id)
            if snapshot is None:
                if target["opened"]:
                    all_tasks.append(
                        {
                            "id": f"practice:{path.id}:{target['lessonId']}:{concept_id}",
                            "kind": "practice",
                            "priority": 52,
                            "title": f"Build evidence on {concept_label(concept_id)}",
                            "reason": (
                                f"You opened {target['title']} but no mastery evidence exists for "
                                f"{concept_label(concept_id)} yet. Answer its practice or checkpoint questions."
                            ),
                            "actionLabel": "Continue practice",
                            "pathId": str(path.id),
                            "pathTitle": _path_title(path, labels),
                            "subjectId": path.subject_id,
                            "subjectLabel": _subject_label(path.subject_id, labels),
                            "lessonId": target["lessonId"],
                            "lessonTitle": target["title"],
                            "conceptId": concept_id,
                            "conceptLabel": concept_label(concept_id),
                            "evidence": {
                                "band": "not_enough_evidence",
                                "score": None,
                                "evidenceCount": 0,
                                "attempts": target["attempts"],
                            },
                        }
                    )
                continue

            evidence_count = snapshot.evidence_count or 0
            score = _percent(snapshot.numeric_estimate)
            calculated = _utc_naive(snapshot.calculated_at)
            age_days = (now - calculated).days if calculated else None
            if snapshot.estimate_band == "developing":
                all_tasks.append(
                    {
                        "id": f"remediate:{path.id}:{target['lessonId']}:{concept_id}",
                        "kind": "remediate",
                        "priority": 100 + (100 - (score if score is not None else 50)) / 10,
                        "title": f"Rebuild {concept_label(concept_id)}",
                        "reason": (
                            f"Your recorded mastery for {concept_label(concept_id)} is "
                            f"{score if score is not None else 'not yet scored'}% from "
                            f"{evidence_count} evidence point(s), which is the developing band. "
                            f"{target['title']} contains this concept."
                        ),
                        "actionLabel": "Rebuild this concept",
                        "pathId": str(path.id),
                        "pathTitle": _path_title(path, labels),
                        "subjectId": path.subject_id,
                        "subjectLabel": _subject_label(path.subject_id, labels),
                        "lessonId": target["lessonId"],
                        "lessonTitle": target["title"],
                        "conceptId": concept_id,
                        "conceptLabel": concept_label(concept_id),
                        "evidence": {
                            "band": snapshot.estimate_band,
                            "score": score,
                            "evidenceCount": evidence_count,
                            "lastCalculatedAt": calculated.isoformat() if calculated else None,
                        },
                    }
                )
            elif snapshot.estimate_band == "approaching" and (
                (age_days is not None and age_days >= 2) or (score is not None and score < 75)
            ):
                stale = (
                    f"It was last measured {age_days} days ago."
                    if age_days is not None and age_days >= 2
                    else "Its recorded score is below the independent-mastery range."
                )
                all_tasks.append(
                    {
                        "id": f"review:{path.id}:{target['lessonId']}:{concept_id}",
                        "kind": "review",
                        "priority": 70 + (100 - (score if score is not None else 50)) / 20,
                        "title": f"Review {concept_label(concept_id)}",
                        "reason": (
                            f"You are approaching mastery on {concept_label(concept_id)} "
                            f"({score if score is not None else 'not yet scored'}% across "
                            f"{evidence_count} evidence point(s)). {stale}"
                        ),
                        "actionLabel": "Quick review",
                        "pathId": str(path.id),
                        "pathTitle": _path_title(path, labels),
                        "subjectId": path.subject_id,
                        "subjectLabel": _subject_label(path.subject_id, labels),
                        "lessonId": target["lessonId"],
                        "lessonTitle": target["title"],
                        "conceptId": concept_id,
                        "conceptLabel": concept_label(concept_id),
                        "evidence": {
                            "band": snapshot.estimate_band,
                            "score": score,
                            "evidenceCount": evidence_count,
                            "lastCalculatedAt": calculated.isoformat() if calculated else None,
                        },
                    }
                )

        # 2. Lesson-level continuation tasks.
        in_progress_rows = [row for row in ready_rows if row["inProgress"]]
        if in_progress_rows:
            target = in_progress_rows[0]
            all_tasks.append(
                {
                    "id": f"continue:{path.id}:{target['lessonId']}",
                    "kind": "continue",
                    "priority": 95,
                    "title": f"Finish {target['title']}",
                    "reason": (
                        f"You have {target['readingMinutes']:g} recorded reading minutes and "
                        f"{target['attempts']} answer(s) in this unit, but no checkpoint attempt yet."
                    ),
                    "actionLabel": "Continue this unit",
                    "pathId": str(path.id),
                    "pathTitle": _path_title(path, labels),
                    "subjectId": path.subject_id,
                    "subjectLabel": _subject_label(path.subject_id, labels),
                    "lessonId": target["lessonId"],
                    "lessonTitle": target["title"],
                    "conceptId": None,
                    "conceptLabel": None,
                    "evidence": {
                        "readingMinutes": target["readingMinutes"],
                        "attempts": target["attempts"],
                        "correct": target["correct"],
                    },
                }
            )
        else:
            unopened = [row for row in ready_rows if not row["opened"] and not row["completed"]]
            if unopened:
                target = unopened[0]
                all_tasks.append(
                    {
                        "id": f"next:{path.id}:{target['lessonId']}",
                        "kind": "next_lesson",
                        "priority": 75 if lesson_rows[0] is target else 62,
                        "title": f"Start {target['title']}",
                        "reason": (
                            f"This is the next ready unit by sequence in {_path_title(path, labels)}. "
                            "No reading or answer is recorded for it yet."
                        ),
                        "actionLabel": "Open this unit",
                        "pathId": str(path.id),
                        "pathTitle": _path_title(path, labels),
                        "subjectId": path.subject_id,
                        "subjectLabel": _subject_label(path.subject_id, labels),
                        "lessonId": target["lessonId"],
                        "lessonTitle": target["title"],
                        "conceptId": None,
                        "conceptLabel": None,
                        "evidence": {
                            "sequence": target["sequence"],
                            "readyLessons": len(ready_rows),
                        },
                    }
                )

        # 3. If every ready unit is complete in this book, offer a stretch task.
        if ready_rows and all(row["completed"] for row in ready_rows):
            all_tasks.append(
                {
                    "id": f"stretch:{path.id}",
                    "kind": "stretch",
                    "priority": 35,
                    "title": f"Stretch beyond {_path_title(path, labels)}",
                    "reason": (
                        f"Every ready unit in this book ({len(ready_rows)}) has a checkpoint attempt. "
                        "Revisit a demonstrated concept with a challenge question, or add another book."
                    ),
                    "actionLabel": "Choose a challenge",
                    "pathId": str(path.id),
                    "pathTitle": _path_title(path, labels),
                    "subjectId": path.subject_id,
                    "subjectLabel": _subject_label(path.subject_id, labels),
                    "lessonId": None,
                    "lessonTitle": None,
                    "conceptId": None,
                    "conceptLabel": None,
                    "evidence": {"readyLessons": len(ready_rows)},
                }
            )

        books.append(
            _book_summary(
                path,
                documents.get(path.document_id) if path.document_id else None,
                lesson_rows,
                snapshots,
                path_concepts,
                labels,
            )
        )
        roadmaps.append(
            {
                "pathId": str(path.id),
                "title": _path_title(path, labels),
                "subjectLabel": _subject_label(path.subject_id, labels),
                "lessons": [
                    {
                        "lessonId": row["lessonId"],
                        "title": row["title"],
                        "sequence": row["sequence"],
                        "status": (
                            "completed"
                            if row["completed"]
                            else "in_progress"
                            if row["inProgress"]
                            else row["status"]
                        ),
                        "attempts": row["attempts"],
                        "readingMinutes": row["readingMinutes"],
                    }
                    for row in lesson_rows
                ],
            }
        )

    # Cross-book selection: one strong task from each book, then fill by priority.
    all_tasks.sort(key=lambda task: (-float(task["priority"]), task["title"]))
    selected: List[Dict[str, Any]] = []
    selected_ids = set()
    used_books = set()
    for task in all_tasks:
        if task["pathId"] in used_books:
            continue
        selected.append(task)
        selected_ids.add(task["id"])
        used_books.add(task["pathId"])
        if len(selected) >= 4:
            break
    for task in all_tasks:
        if len(selected) >= 4:
            break
        if task["id"] in selected_ids:
            continue
        selected.append(task)
        selected_ids.add(task["id"])

    selected.sort(key=lambda task: -float(task["priority"]))
    for index, task in enumerate(selected):
        task["slot"] = SLOT_LABELS[min(index, len(SLOT_LABELS) - 1)]

    subjects = []
    for book in books:
        if book["subjectLabel"] not in subjects:
            subjects.append(book["subjectLabel"])

    if selected:
        first = selected[0]
        plan_summary = (
            f"{len(selected)} task(s) across {len(books)} book(s). "
            f"Start with “{first['title']}” in {first['subjectLabel']}: {first['reason']}"
        )
    elif waiting_books:
        plan_summary = (
            "Your books are still being prepared. No unit is ready to open yet."
        )
    elif books:
        plan_summary = (
            "All ready units are complete. Add another book or revisit a concept to keep the plan moving."
        )
    else:
        plan_summary = "Add a source and build a learning plan. Tasks will appear from your own evidence."

    return {
        "generatedAt": datetime.datetime.now(UTC).isoformat(),
        "state": "active" if selected else ("preparing" if waiting_books else "empty"),
        "summary": plan_summary,
        "subjectMix": subjects,
        "bookCount": len(books),
        "taskCount": len(selected),
        "tasks": selected,
        "books": books,
        "roadmap": roadmaps,
        "counts": {
            "completedLessons": sum(book["completedLessons"] for book in books),
            "readyLessons": sum(book["readyLessons"] for book in books),
            "totalLessons": sum(book["totalLessons"] for book in books),
            "waitingBooks": waiting_books,
        },
    }
