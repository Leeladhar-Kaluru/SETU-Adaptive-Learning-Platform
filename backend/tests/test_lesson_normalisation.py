from app.services.chunking import chunking_service
from app.services.lesson_generator import lesson_generator_service
from tests.fixtures import evidence_chunks


def _raw_llm_package():
    return {
        "schemaVersion": "1.0.0",
        "lessonId": "wrong-id",
        "lessonVersion": 1,
        "pathId": "wrong-path",
        "pathVersion": 1,
        "title": "wrong title",
        "grade": 9,
        "subjectId": "subject-science",
        "languageTag": "en-IN",
        "objectives": ["Describe the cell.", "Explain the membrane."],
        "blocks": [
            {
                "kind": "explanation",
                "content": {"title": "The Cell", "text": "Cells are the unit of life."},
            }
        ],
        "visuals": [
            {
                "type": "concept_map",
                "spec": {
                    "title": "Cell map",
                    "nodes": [{"id": "cell", "label": "Cell"}],
                    "edges": [],
                },
            }
        ],
        "workedExamples": [
            {"prompt": "What is a cell?", "steps": ["Read the source."], "answer": "The unit of life."}
        ],
        "practice": [
            {
                "questionId": "q1",
                "prompt": "Which is the unit of life?",
                "type": "multiple_choice",
                "options": ["Cell", "Tissue"],
                "conceptIds": ["cell"],
                "answerKey": "Cell",
                "feedback": "A cell is the unit of life.",
                "hints": "Look at the definition.",
                "validator": "string_match:Cell",
            },
            {
                "questionId": "q2",
                "prompt": "What covers the cell?",
                "type": "fill_in_the_blank",
                "answerKey": "plasma membrane",
                "explanation": "The plasma membrane covers the cell.",
            },
        ],
        "checkpointTest": [
            {
                "questionId": "q1",
                "prompt": "What does the membrane control?",
                "type": "multiple_choice",
                "answerKey": "Entry and exit",
            }
        ],
        "takeaways": ["Cells are the unit of life."],
    }


def test_llm_shaped_package_is_normalised_without_inventing_content():
    normalised = lesson_generator_service._normalise_package(
        _raw_llm_package(),
        lesson_id="lesson_1",
        lesson_title="Chapter 1: The Fundamental Unit of Life",
        path_id="path-real",
        grade=9,
        subject_id="subject-science",
    )
    normalised["sourceRefs"] = [
        {
            "citationId": "cite_1",
            "chunkId": "chunk-1",
            "documentVersionId": "doc-1",
            "pageStart": 1,
            "pageEnd": 1,
            "headingPath": ["Chapter 1"],
            "sourceTitle": "e2e_science.pdf",
        }
    ]

    assert normalised["lessonId"] == "lesson_1"
    assert normalised["pathId"] == "path-real"
    assert normalised["title"] == "Chapter 1: The Fundamental Unit of Life"
    assert normalised["blocks"][0]["blockId"] == "block_1"
    assert normalised["blocks"][0]["heading"] == "The Cell"
    assert normalised["blocks"][0]["content"] == "Cells are the unit of life."

    visual = normalised["visuals"][0]
    assert visual["visualId"] == "visual_1"
    assert visual["spec"]["data"]["nodes"] == [{"id": "cell", "label": "Cell"}]
    assert "Cell" in visual["altText"]

    questions = {question["questionId"]: question for question in normalised["practice"]}
    assert questions["q1"]["type"] == "multiple_choice"
    assert questions["q1"]["hints"] == ["Look at the definition."]
    assert questions["q1"]["validator"] == "deterministic"
    assert questions["q2"]["type"] == "short_text"
    assert questions["q2"]["conceptIds"] == ["lesson_1"]
    assert questions["q2"]["feedback"] == "The plasma membrane covers the cell."

    checkpoint = normalised["checkpointTest"][0]
    assert checkpoint["questionId"] == "q1_2"
    assert checkpoint["type"] == "short_text"
    assert checkpoint["conceptIds"] == ["lesson_1"]

    validation = lesson_generator_service.validate_package(normalised, evidence_chunks())
    assert validation["status"] == "ready", validation
    for check in validation["checks"]:
        assert check["passed"] is True, f"{check['name']}: {check['details']}"
    assert any(c["name"] == "gradable_question_types" for c in validation["checks"])


def test_chunks_keep_the_heading_of_the_text_they_actually_contain():
    pages = [
        {"page_number": 1, "text": "Chapter 1: The Cell\n" + "cells " * 30},
        {"page_number": 2, "text": "Chapter 2: Tissues\n" + "tissue " * 30},
        {"page_number": 3, "text": "body " * 30},
    ]
    chunks = chunking_service.create_chunks(pages, chunk_size_words=20, overlap_words=4)

    assert chunks
    page_one = [chunk for chunk in chunks if chunk["heading_path"] == ["Chapter 1: The Cell"]]
    page_two = [chunk for chunk in chunks if chunk["heading_path"] == ["Chapter 2: Tissues"]]
    assert page_one and page_two
    assert all("Chapter 2" not in chunk["text"] for chunk in page_one)
    assert all("Chapter 1" not in chunk["text"] for chunk in page_two)
    assert "Chapter 1: The Cell" in page_one[0]["text"]
    assert "Chapter 2: Tissues" in page_two[0]["text"]

    # Page three has no heading of its own, so it stays with Chapter 2 and is
    # merged into that heading group with an honest page range.
    assert any("body" in chunk["text"] for chunk in page_two)
    assert any(chunk["page_end"] == 3 for chunk in page_two)
    assert all(chunk["page_start"] <= chunk["page_end"] for chunk in chunks)


def test_chunk_ids_are_stable_and_unique_across_pages():
    pages = [
        {"page_number": 1, "text": "Chapter 1: Cells\n" + "a " * 60},
        {"page_number": 2, "text": "Chapter 2: Tissues\n" + "b " * 60},
    ]
    chunks = chunking_service.create_chunks(pages, chunk_size_words=25, overlap_words=5)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert len({chunk["text_hash"] for chunk in chunks}) == len(chunks)


def test_generate_lesson_package_reaches_the_normaliser(monkeypatch):
    """Regression: ``text_value`` was defined inside the normaliser only.

    ``generate_lesson_package`` used it for the language tag before parsing the
    model output, so every worker job failed with ``NameError: text_value`` and
    no lesson could become ready.
    """
    import asyncio
    import json

    from app.services import lesson_generator as module

    payload = _raw_llm_package()

    async def fake_generate_chat(**kwargs):
        return json.dumps(payload)

    monkeypatch.setattr(module.ai_provider, "generate_chat", fake_generate_chat)

    package = asyncio.run(
        lesson_generator_service.generate_lesson_package(
            lesson_id="lesson-regression",
            lesson_title="Chapter 1: The Fundamental Unit of Life",
            path_id="path-regression",
            grade=9,
            subject="subject-science",
            evidence_chunks=evidence_chunks(),
            language_tag="en-IN",
        )
    )

    assert package["lessonId"] == "lesson-regression"
    assert package["languageTag"] == "en-IN"
    assert package["sourceRefs"]
    assert package["practice"]

