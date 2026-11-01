"""Full vertical slice: upload -> outline -> queue -> ready -> plan -> evidence -> plan change.

The AI provider is replaced by a deterministic package, but every other layer is
real: PostgreSQL rows, the worker's own ``process_job``, question persistence,
attempt grading, mastery snapshots and the adaptive planner.
"""

import asyncio
import copy
import uuid

from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.jobs import GenerationJob
from app.models.learning import LearningPath, LessonVersion, PathLesson, Question
from app.services import lesson_generator as lesson_generator_module
from app.services.lesson_generator import lesson_generator_service
from app.worker import process_job
from tests.fixtures import valid_lesson_package


def _document(db, owner_id, *, filename, headings, chunk_text, concept_ids):
    doc = Document(
        owner_id=owner_id,
        original_filename=filename,
        storage_key=f"documents/{owner_id}/{filename}",
        mime_type="application/pdf",
        size_bytes=1200,
        status="awaiting_review",
        page_count=len(headings),
    )
    db.add(doc)
    db.flush()

    for index, heading in enumerate(headings, start=1):
        text = f"{heading}\n{chunk_text[index - 1]}"
        db.add(
            DocumentPage(
                document_id=doc.id,
                page_number=index,
                extracted_text=text,
                char_count=len(text),
                word_count=len(text.split()),
            )
        )
        db.add(
            DocumentChunk(
                document_id=doc.id,
                page_start=index,
                page_end=index,
                chunk_index=index - 1,
                heading_path=[heading],
                text=text,
                text_hash=f"{doc.id}-{index}-{uuid.uuid4().hex[:8]}",
                embedding=[0.01] * 768,
                embedding_model_id="text-embedding-nomic-embed-text-v1.5",
                embedding_dimension=768,
            )
        )
    db.commit()
    return doc, concept_ids


def _fake_package_factory(concepts_by_lesson):
    async def fake_generate_lesson_package(
        *,
        lesson_id,
        lesson_title,
        path_id,
        grade,
        subject,
        evidence_chunks,
        language_tag="en-IN",
    ):
        package = copy.deepcopy(valid_lesson_package())
        package.update(
            {
                "lessonId": lesson_id,
                "pathId": path_id,
                "title": lesson_title,
                "grade": grade,
                "subjectId": subject,
                "languageTag": language_tag,
                "validation": {"status": "ready", "checks": []},
            }
        )
        concept = concepts_by_lesson[lesson_id]
        for question in package["practice"] + package["checkpointTest"]:
            question["conceptIds"] = [concept]
        return package

    return fake_generate_lesson_package


def _process_all_jobs(db, path_id):
    job_ids = [
        row[0]
        for row in db.query(GenerationJob.id)
        .filter(GenerationJob.path_id == path_id)
        .order_by(GenerationJob.created_at.asc())
        .all()
    ]
    for job_id in job_ids:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).one()
        assert asyncio.run(process_job(db, job)) is True


def _first_question(db, path_id):
    lesson = (
        db.query(PathLesson)
        .filter(PathLesson.path_id == path_id)
        .order_by(PathLesson.sequence.asc())
        .first()
    )
    version = (
        db.query(LessonVersion)
        .filter(LessonVersion.path_lesson_id == lesson.id)
        .order_by(LessonVersion.version_number.desc())
        .first()
    )
    question = (
        db.query(Question)
        .filter(Question.lesson_version_id == version.id)
        .order_by(Question.question_key.asc())
        .first()
    )
    return version, question


def _attempt(client, headers, version, question, *, response, key, kind="practice"):
    return client.post(
        "/api/v1/attempts",
        headers=headers,
        json={
            "lessonVersionId": str(version.id),
            "questionKey": question.question_key,
            "response": response,
            "hintLevel": 0,
            "hintsUsed": [],
            "elapsedSeconds": 31,
            "attemptKind": kind,
            "syncIdempotencyKey": key,
        },
    )


def test_new_subject_document_becomes_a_plan_that_reacts_to_performance(
    client, db, monkeypatch
):
    owner_id = uuid.uuid4()
    headers = {"X-User-Id": str(owner_id)}

    maths_doc, _ = _document(
        db,
        owner_id,
        filename="Class 7 Mathematics Practice.pdf",
        headings=["Chapter 1: Integers", "Chapter 2: Fractions"],
        chunk_text=[
            "Integers include positive numbers, negative numbers and zero. "
            "A number line shows their order.",
            "A fraction represents equal parts of a whole. Equivalent fractions "
            "name the same value.",
        ],
        concept_ids=["integers", "fractions"],
    )

    fake = _fake_package_factory({"lesson_1": "integers", "lesson_2": "fractions"})
    monkeypatch.setattr(
        lesson_generator_service, "generate_lesson_package", fake
    )
    monkeypatch.setattr(
        lesson_generator_module.lesson_generator_service,
        "generate_lesson_package",
        fake,
    )

    maths = client.post(
        "/api/v1/learning-paths",
        headers=headers,
        json={
            "documentId": str(maths_doc.id),
            "grade": 7,
            "subjectId": "subject-math",
        },
    )
    assert maths.status_code == 200, maths.text
    maths_path_id = uuid.UUID(maths.json()["pathId"])
    assert maths.json()["totalLessons"] == 2

    _process_all_jobs(db, maths_path_id)
    lessons = (
        db.query(PathLesson)
        .filter(PathLesson.path_id == maths_path_id)
        .order_by(PathLesson.sequence.asc())
        .all()
    )
    assert [lesson.status for lesson in lessons] == ["ready", "ready"]

    plan = client.get("/api/v1/study/plan", headers=headers)
    assert plan.status_code == 200, plan.text
    body = plan.json()
    assert body["state"] == "active"
    assert body["bookCount"] == 1
    assert body["subjectMix"] == ["Mathematics"]
    assert body["tasks"]
    first_task = body["tasks"][0]
    assert first_task["lessonId"] == str(lessons[0].id)
    assert first_task["kind"] == "next_lesson"
    assert "Integers" in first_task["title"]

    version, question = _first_question(db, maths_path_id)

    # Two wrong answers create real developing-band evidence.
    for index in range(2):
        result = _attempt(
            client,
            headers,
            version,
            question,
            response="not the answer",
            key=f"wrong-{index}",
        )
        assert result.status_code == 200, result.text
    assert result.json()["mastery"]["band"] == "developing"

    adapted = client.get("/api/v1/study/plan", headers=headers).json()
    rebuild = [
        task for task in adapted["tasks"] if task["kind"] == "remediate"
    ]
    assert rebuild, adapted
    assert rebuild[0]["conceptId"] == "integers"
    assert "2 evidence point" in rebuild[0]["reason"]
    assert rebuild[0]["lessonId"] == str(lessons[0].id)

    # Enough independent checkpoint evidence moves the same concept to
    # demonstrated and removes the rebuild task from the next plan.
    for index in range(5):
        result = _attempt(
            client,
            headers,
            version,
            question,
            response="A",
            key=f"correct-{index}",
            kind="checkpoint",
        )
        assert result.status_code == 200, result.text
    assert result.json()["mastery"]["band"] == "demonstrated"

    recovered = client.get("/api/v1/study/plan", headers=headers).json()
    assert not [
        task
        for task in recovered["tasks"]
        if task["kind"] == "remediate" and task["conceptId"] == "integers"
    ], recovered
    assert recovered["tasks"], recovered

    # A second, different subject proves the plan is cross-book and not tied
    # to one textbook family.
    english_doc, _ = _document(
        db,
        owner_id,
        filename="Class 8 English Poems.pdf",
        headings=["Chapter 1: The Road Not Taken"],
        chunk_text=[
            "The poem uses a fork in the road as a metaphor for a life choice."
        ],
        concept_ids=["metaphor"],
    )
    fake_english = _fake_package_factory({"lesson_1": "metaphor"})
    monkeypatch.setattr(
        lesson_generator_service, "generate_lesson_package", fake_english
    )
    english = client.post(
        "/api/v1/learning-paths",
        headers=headers,
        json={
            "documentId": str(english_doc.id),
            "grade": 8,
            "subjectId": "subject-english",
        },
    )
    assert english.status_code == 200, english.text
    english_path_id = uuid.UUID(english.json()["pathId"])
    _process_all_jobs(db, english_path_id)

    combined = client.get("/api/v1/study/plan", headers=headers).json()
    assert combined["bookCount"] == 2, combined
    assert set(combined["subjectMix"]) == {"Mathematics", "English"}
    assert combined["taskCount"] >= 2
    assert {task["pathId"] for task in combined["tasks"]} == {
        str(maths_path_id),
        str(english_path_id),
    }
    assert any(task["subjectLabel"] == "English" for task in combined["tasks"])
    assert any(task["subjectLabel"] == "Mathematics" for task in combined["tasks"])

    # Paths and lessons are private to their owner.
    intruder = {"X-User-Id": str(uuid.uuid4())}
    assert client.get("/api/v1/study/plan", headers=intruder).json()["bookCount"] == 0
    assert client.get("/api/v1/learning-paths", headers=intruder).json() == []


def test_doubt_in_full_flow_switches_from_general_to_grounded(db, monkeypatch):
    """A student with no book gets a labeled general-knowledge answer; the same
    question asked from inside a lesson (pathId) is grounded with citations."""
    from app.models.learning import LearningPath
    from app.services import sync_service as sync_module
    from app.services.sync_service import sync_service

    owner_without_book = uuid.uuid4()
    owner_with_book = uuid.uuid4()
    doc, _ = _document(
        db,
        owner_with_book,
        filename="Class 7 Mathematics Practice.pdf",
        headings=["Chapter 1: Integers"],
        chunk_text=["Integers include positive numbers, negative numbers and zero."],
        concept_ids=["integers"],
    )
    path = LearningPath(
        owner_id=owner_with_book,
        document_id=doc.id,
        grade=7,
        subject_id="subject-math",
        outline_json={"title": "Mathematics"},
        status="active",
    )
    db.add(path)
    db.commit()

    async def fake_search(**kwargs):
        if kwargs.get("document_id") is None:
            return {"results": [], "insufficient_evidence": True}
        return {
            "results": [{
                "citationId": "cite_1",
                "documentVersionId": str(doc.id),
                "pageStart": 1,
                "pageEnd": 1,
                "headingPath": ["Chapter 1: Integers"],
                "text": "Integers include positive numbers, negative numbers and zero.",
            }],
            "insufficient_evidence": False,
        }

    async def fake_chat(**kwargs):
        return "Integers are whole numbers that can be positive, negative, or zero."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    general = asyncio.run(sync_service.sync_doubt(
        db=db, owner_id=owner_without_book, client_doubt_id="doubt-general",
        question_text="What are integers?",
    ))
    assert general["status"] == "answered"
    assert general["answerJson"]["limitations"] == "general_knowledge"
    assert general["answerJson"]["citations"] == []

    grounded = asyncio.run(sync_service.sync_doubt(
        db=db, owner_id=owner_with_book, client_doubt_id="doubt-grounded",
        question_text="What are integers?", path_id=path.id,
    ))
    assert grounded["status"] == "answered"
    assert grounded["answerJson"]["limitations"] is None
    citations = grounded["answerJson"]["citations"]
    assert citations and citations[0]["sourceTitle"] == "Class 7 Mathematics Practice.pdf"
    assert citations[0]["pageStart"] == 1
