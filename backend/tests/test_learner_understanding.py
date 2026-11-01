"""Truth tests for the learner-understanding, planning and coaching layer.

Every fixture is written to the disposable test database. The assertions read
the same evidence a student produces: study events, graded attempts, concept
mastery snapshots and the source chunks a lesson cites.
"""

import datetime
import json
import uuid

import pytest

from app.models.classroom import Classroom
from app.models.documents import Document, DocumentChunk
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
from app.models.profiles import UserProfile
from app.services.coach_service import build_lesson_coaching, diagnose_root_gap
from app.services.learner_insights import build_learner_insights
from app.services.smart_check import build_smart_check, next_smart_question
from app.services.study_plan import build_study_plan
from tests.conftest import auth_headers
from tests.fixtures import valid_lesson_package


def _profile(db, role="student", name=None, goal=30):
    user_id = uuid.uuid4()
    db.add(
        UserProfile(
            id=user_id,
            email=f"{role}-{user_id.hex[:8]}@example.com",
            display_name=name or f"{role.title()} {user_id.hex[:4]}",
            role=role,
            grade=9,
            board_id="board-cbse",
            preferred_language="en-IN",
            daily_goal_minutes=goal,
        )
    )
    db.commit()
    return user_id


def _book(
    db,
    owner_id,
    *,
    subject_id="subject-science",
    title="Science book",
    lesson_titles=("Cell structure", "Cell division"),
    concept_prefix="cell",
    source_text=(
        "The cell is the structural and functional unit of life. "
        "Robert Hooke first observed cells in cork more than three hundred years ago."
    ),
):
    document = Document(
        owner_id=owner_id,
        original_filename=f"{subject_id}.pdf",
        storage_key=f"tests/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        grade=9,
        subject_id=subject_id,
        status="ready",
        page_count=6,
    )
    db.add(document)
    db.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        page_start=4,
        page_end=4,
        heading_path=["Chapter 1"],
        chunk_index=0,
        text=source_text,
        text_hash=uuid.uuid4().hex,
        language_tag="en-IN",
    )
    db.add(chunk)
    db.flush()

    path = LearningPath(
        owner_id=owner_id,
        document_id=document.id,
        grade=9,
        subject_id=subject_id,
        outline_json={"title": title},
        status="active",
    )
    db.add(path)
    db.flush()

    lessons = []
    versions = []
    questions = []
    for index, lesson_title in enumerate(lesson_titles, start=1):
        lesson = PathLesson(
            path_id=path.id,
            lesson_key=f"unit-{index}",
            title=lesson_title,
            sequence=index,
            status="ready",
        )
        db.add(lesson)
        db.flush()
        package = valid_lesson_package(
            lesson_id=str(lesson.id), path_id=str(path.id), title=lesson_title
        )
        package["sourceRefs"][0]["chunkId"] = str(chunk.id)
        package["sourceRefs"][0]["pageStart"] = 4
        package["sourceRefs"][0]["pageEnd"] = 4
        package["takeaways"] = [
            f"{lesson_title} is explained by the source on page 4."
        ]
        version = LessonVersion(
            path_lesson_id=lesson.id,
            version_number=1,
            lesson_package_json=package,
            validation_status="ready",
        )
        db.add(version)
        db.flush()
        concept_id = f"concept-{concept_prefix}-{index}"
        question = Question(
            lesson_version_id=version.id,
            question_key=f"q-{concept_prefix}-{index}",
            type="multiple_choice",
            prompt_json={
                "text": f"Which statement about {lesson_title.lower()} matches the source?",
                "options": ["A", "B", "C", "D"],
            },
            answer_key_json={"answer": "A", "feedback": "A matches the source."},
            concept_ids=[concept_id],
            difficulty="challenge" if index == 2 else "standard",
        )
        db.add(question)
        db.flush()
        lessons.append(lesson)
        versions.append(version)
        questions.append(question)
    db.commit()
    return {
        "document": document,
        "chunk": chunk,
        "path": path,
        "lessons": lessons,
        "versions": versions,
        "questions": questions,
    }


def _snapshot(db, owner_id, concept_id, band, score, evidence=3, when=None):
    db.add(
        ConceptMasterySnapshot(
            owner_id=owner_id,
            concept_id=concept_id,
            estimate_band=band,
            numeric_estimate=score,
            evidence_count=evidence,
            calculated_at=when or datetime.datetime.utcnow(),
        )
    )
    db.commit()


def test_insights_are_derived_from_recorded_events_and_attempts(db):
    student_id = _profile(db, name="Asha", goal=30)
    book = _book(db, student_id)
    evening = datetime.datetime.utcnow().replace(hour=18, minute=30, second=0, microsecond=0)
    for offset in range(3):
        db.add(
            StudyEvent(
                owner_id=student_id,
                path_id=book["path"].id,
                lesson_id=str(book["lessons"][0].id),
                lesson_title=book["lessons"][0].title,
                event_type="reading",
                seconds=600,
                occurred_at=evening - datetime.timedelta(days=offset),
            )
        )
    for index in range(4):
        db.add(
            QuizAttempt(
                owner_id=student_id,
                question_id=book["questions"][0].id,
                lesson_version_id=book["versions"][0].id,
                response_json={"answer": "A" if index < 3 else "B"},
                score=1.0 if index < 3 else 0.0,
                is_correct=index < 3,
                hints_used=["Look at the first block."] if index == 3 else [],
                hint_level=1 if index == 3 else 0,
                elapsed_seconds=45,
                attempt_kind="practice",
                occurred_at=evening - datetime.timedelta(days=index),
            )
        )
    db.add(
        ConceptEvidence(
            owner_id=student_id,
            concept_id="concept-cell-1",
            evidence_type="practice_attempt",
            outcome="correct",
            occurred_at=evening,
        )
    )
    _snapshot(db, student_id, "concept-cell-1", "demonstrated", 0.9, evidence=4)
    _snapshot(db, student_id, "concept-cell-2", "developing", 0.35, evidence=2)

    insights = build_learner_insights(db, student_id)

    assert insights["state"] == "measured"
    assert insights["evidence"]["gradedAttempts"] == 4
    assert insights["evidence"]["studyEvents"] == 3
    assert insights["accuracy"]["overall"] == 75
    assert insights["hintReliance"]["hintRate"] == 25
    assert insights["hintReliance"]["hintedAttempts"] == 1
    assert insights["routine"]["bestWindow"]["id"] == "evening"
    assert insights["routine"]["currentStreak"] == 3
    assert insights["mastery"]["bands"]["demonstrated"] == 1
    assert insights["mastery"]["bands"]["developing"] == 1
    assert insights["mastery"]["strengths"][0]["conceptId"] == "concept-cell-1"
    assert insights["mastery"]["focusAreas"][0]["conceptId"] == "concept-cell-2"
    assert insights["confidence"] == "medium"
    assert "75%" in insights["summary"]
    assert any(habit["id"] == "hint-use" for habit in insights["habits"])


def test_cross_book_plan_reorders_after_mastery_changes(db):
    student_id = _profile(db, name="Bilal")
    science = _book(db, student_id, concept_prefix="cell", title="Science book")
    maths = _book(
        db,
        student_id,
        subject_id="subject-mathematics",
        title="Mathematics book",
        lesson_titles=("Linear equations",),
        concept_prefix="algebra",
    )
    _snapshot(db, student_id, "concept-cell-1", "developing", 0.32, evidence=3)

    plan = build_study_plan(db, student_id)

    assert plan["state"] == "active"
    assert plan["bookCount"] == 2
    assert set(plan["subjectMix"]) == {"Science", "Mathematics"}
    assert {task["pathId"] for task in plan["tasks"]} == {
        str(science["path"].id),
        str(maths["path"].id),
    }
    remediation = [
        task for task in plan["tasks"]
        if task["kind"] == "remediate" and task["conceptId"] == "concept-cell-1"
    ]
    assert remediation, plan["tasks"]
    assert "developing" in remediation[0]["reason"]

    _snapshot(db, student_id, "concept-cell-1", "demonstrated", 0.92, evidence=6)
    adapted = build_study_plan(db, student_id)
    still_remedial = [
        task for task in adapted["tasks"]
        if task["kind"] == "remediate" and task["conceptId"] == "concept-cell-1"
    ]
    assert not still_remedial, adapted["tasks"]
    assert adapted["books"][0]["mastery"]["demonstrated"] >= 1


def test_root_gap_and_attempt_coaching_use_real_source_and_evidence(client, db):
    student_id = _profile(db, name="Chen")
    book = _book(db, student_id)
    _snapshot(db, student_id, "concept-cell-1", "developing", 0.3, evidence=2)

    wrong = client.post(
        "/api/v1/attempts",
        headers=auth_headers(student_id),
        json={
            "lessonVersionId": str(book["versions"][1].id),
            "questionKey": book["questions"][1].question_key,
            "response": "B",
            "hintsUsed": [],
            "elapsedSeconds": 70,
            "attemptKind": "practice",
        },
    )
    assert wrong.status_code == 200, wrong.text
    payload = wrong.json()
    coaching = payload["coaching"]
    assert coaching and coaching["tone"] == "retry"
    assert coaching["rootGap"]["conceptId"] == "concept-cell-1"
    assert coaching["rootGap"]["lessonTitle"] == "Cell structure"
    assert coaching["source"]["page"] == 4
    assert coaching["source"]["excerpt"] in (
        "The cell is the structural and functional unit of life.",
        "Robert Hooke first observed cells in cork more than three hundred years ago.",
    )
    assert coaching["keyPoint"]["body"]
    assert coaching["evidence"]["isCorrect"] is False
    assert "B" in coaching["body"]

    gap = diagnose_root_gap(
        db,
        owner_id=student_id,
        lesson=book["lessons"][1],
        concept_ids=["concept-cell-2"],
    )
    assert gap["conceptId"] == "concept-cell-1"
    assert gap["sequence"] == 1


def test_lesson_coaching_omits_cards_when_no_source_exists(db):
    student_id = _profile(db, name="Divya")
    book = _book(db, student_id)
    version = book["versions"][0]
    package = dict(version.lesson_package_json or {})
    package["sourceRefs"] = []
    package["takeaways"] = []
    package["blocks"] = []
    version.lesson_package_json = package
    db.commit()

    coaching = build_lesson_coaching(
        db, owner_id=student_id, lesson=book["lessons"][0], lesson_version=version
    )
    kinds = {moment["kind"] for moment in coaching["moments"]}
    assert "source_spotlight" not in kinds
    assert "fun_fact" not in kinds
    assert coaching["state"] in ("ready", "no_source_material")


def test_smart_check_uses_fewest_questions_and_stops(db):
    student_id = _profile(db, name="Esha")
    book = _book(
        db,
        student_id,
        lesson_titles=("Cells", "Tissues", "Organs"),
        concept_prefix="body",
    )
    extra = _book(
        db,
        student_id,
        subject_id="subject-mathematics",
        title="Number book",
        lesson_titles=("Numbers", "Factors", "Fractions"),
        concept_prefix="number",
    )
    all_questions = book["questions"] + extra["questions"]

    check = build_smart_check(db, student_id)
    assert check["state"] == "ready"
    assert 1 <= len(check["questions"]) <= 5
    assert check["questions"][0]["why"]

    first = next_smart_question(db, student_id, answered_question_keys=[])
    assert first["state"] == "question"
    assert first["question"]["questionKey"]

    for question in all_questions:
        _snapshot(db, student_id, question.concept_ids[0], "demonstrated", 0.9, evidence=5)

    stopped = next_smart_question(
        db,
        student_id,
        answered_question_keys=[question.question_key for question in all_questions[:3]],
    )
    assert stopped["state"] == "complete"
    assert stopped["stopReason"] == "enough_evidence"

    limit = next_smart_question(
        db,
        student_id,
        answered_question_keys=[question.question_key for question in all_questions[:5]],
    )
    assert limit["state"] == "complete"
    assert limit["stopReason"] == "max_questions"


def test_smart_check_recovers_multiple_choice_options_from_lesson_package(db):
    student_id = _profile(db, name="Farah")
    book = _book(db, student_id, lesson_titles=("Cells", "Tissues"), concept_prefix="body")

    for question in book["questions"]:
        version = (
            db.query(LessonVersion)
            .filter(LessonVersion.id == question.lesson_version_id)
            .first()
        )
        package = json.loads(json.dumps(version.lesson_package_json))
        for section in ("practice", "checkpointTest"):
            for item in package.get(section, []) or []:
                item["questionId"] = question.question_key
                item["options"] = ["A", "B", "C", "D"]
        version.lesson_package_json = package
        # Reproduce lessons saved before options were copied into prompt_json.
        question.prompt_json = {"text": (question.prompt_json or {}).get("text", "")}
    db.commit()

    check = build_smart_check(db, student_id)

    assert check["state"] == "ready"
    assert check["questions"]
    for payload in check["questions"]:
        assert payload["options"] == ["A", "B", "C", "D"]


def test_classroom_owner_can_open_teacher_evidence_without_role_mutation(client, db):
    owner_id = _profile(db, role="student", name="Owner")
    outsider_id = _profile(db, role="student", name="Outsider")
    room = Classroom(
        owner_teacher_id=owner_id,
        name="Owner's real classroom",
        board_id="board-cbse",
        grade=9,
        subject_scope="subject-science",
        join_code="OWNER1",
    )
    db.add(room)
    db.commit()

    rooms = client.get("/api/v1/teacher/classrooms", headers=auth_headers(owner_id))
    assert rooms.status_code == 200, rooms.text
    assert rooms.json()[0]["id"] == str(room.id)

    matrix = client.get(
        f"/api/v1/teacher/classrooms/{room.id}/evidence-matrix",
        headers=auth_headers(owner_id),
    )
    assert matrix.status_code == 200, matrix.text
    assert "classGaps" in matrix.json()

    blocked = client.get("/api/v1/teacher/classrooms", headers=auth_headers(outsider_id))
    assert blocked.status_code == 403


def test_lesson_coaching_tip_references_real_concept_and_source_page(db):
    source_text = (
        "The cell is the structural and functional unit of life. "
        "Robert Hooke first observed cells in cork more than three hundred years ago."
    )
    student_id = _profile(db, name="Gita")
    book = _book(db, student_id, source_text=source_text)

    coaching = build_lesson_coaching(
        db, owner_id=student_id, lesson=book["lessons"][0], lesson_version=book["versions"][0]
    )

    assert coaching["state"] == "ready", coaching
    lesson_title = book["lessons"][0].title
    for moment in coaching["moments"]:
        if moment["kind"] in ("key_point", "fun_fact", "source_spotlight"):
            body = moment.get("body") or ""
            assert lesson_title in body or "cell" in body.lower(), moment
        if moment["kind"] == "source_spotlight":
            assert moment["source"]["page"] == 4
            assert moment["body"] in source_text


def test_attempt_coaching_key_point_is_never_random(client, db):
    student_id = _profile(db, name="Hari")
    book = _book(db, student_id)

    wrong = client.post(
        "/api/v1/attempts",
        headers=auth_headers(student_id),
        json={
            "lessonVersionId": str(book["versions"][0].id),
            "questionKey": book["questions"][0].question_key,
            "response": "B",
            "hintsUsed": ["Think about the source."],
            "elapsedSeconds": 40,
            "attemptKind": "practice",
        },
    )
    assert wrong.status_code == 200, wrong.text
    coaching = wrong.json()["coaching"]
    package = book["versions"][0].lesson_package_json
    assert coaching["keyPoint"]["body"] in package["takeaways"]
    assert coaching["source"]["excerpt"] in (
        "The cell is the structural and functional unit of life.",
        "Robert Hooke first observed cells in cork more than three hundred years ago.",
    )


def test_plan_continue_task_requires_real_in_progress_evidence(db):
    student_id = _profile(db, name="Isha")
    book = _book(db, student_id)

    plan = build_study_plan(db, student_id)
    kinds = [task["kind"] for task in plan["tasks"]]
    assert "continue" not in kinds

    db.add(
        StudyEvent(
            owner_id=student_id,
            path_id=book["path"].id,
            lesson_id=str(book["lessons"][0].id),
            lesson_title=book["lessons"][0].title,
            event_type="reading",
            seconds=120,
            occurred_at=datetime.datetime.utcnow(),
        )
    )
    db.add(
        QuizAttempt(
            owner_id=student_id,
            question_id=book["questions"][0].id,
            lesson_version_id=book["versions"][0].id,
            response_json={"answer": "A"},
            score=1.0,
            is_correct=True,
            hints_used=[],
            hint_level=0,
            elapsed_seconds=30,
            attempt_kind="practice",
            occurred_at=datetime.datetime.utcnow(),
        )
    )
    db.commit()

    in_progress_plan = build_study_plan(db, student_id)
    continue_tasks = [task for task in in_progress_plan["tasks"] if task["kind"] == "continue"]
    assert continue_tasks, in_progress_plan["tasks"]
    reason = continue_tasks[0]["reason"]
    assert "2 recorded reading minutes" in reason
    assert "1 answer(s)" in reason

    db.add(
        QuizAttempt(
            owner_id=student_id,
            question_id=book["questions"][0].id,
            lesson_version_id=book["versions"][0].id,
            response_json={"answer": "A"},
            score=1.0,
            is_correct=True,
            hints_used=[],
            hint_level=0,
            elapsed_seconds=60,
            attempt_kind="checkpoint",
            occurred_at=datetime.datetime.utcnow(),
        )
    )
    db.commit()

    completed_plan = build_study_plan(db, student_id)
    assert not any(task["kind"] == "continue" for task in completed_plan["tasks"])
