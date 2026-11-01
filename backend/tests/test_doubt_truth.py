import uuid

import pytest

from app.models.doubts import Doubt
from app.services import sync_service as sync_module
from app.services.sync_service import sync_service


def _evidence():
    return {
        "results": [{
            "citationId": "cite_1", "pageStart": 1, "pageEnd": 1,
            "headingPath": ["Chapter 1"], "text": "Cells are the basic unit of life.",
        }],
        "insufficient_evidence": False,
    }


@pytest.mark.asyncio
async def test_provider_failure_is_retryable_then_answered(db, monkeypatch):
    owner_id = uuid.uuid4()
    calls = {"count": 0}

    async def fake_search(**kwargs):
        return _evidence()

    async def flaky_chat(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("provider offline")
        return "Cells are the basic unit of life."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", flaky_chat)

    first = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-1",
        question_text="What is a cell?",
    )
    assert first["status"] == "needs_retry"
    assert first["answerJson"]["retryable"] is True
    assert first["answerJson"]["answer"] is None
    assert db.query(Doubt).filter(Doubt.owner_id == owner_id).count() == 1

    second = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-1",
        question_text="What is a cell?",
    )
    assert second["status"] == "answered"
    assert second["alreadyExisted"] is True
    assert "basic unit" in second["answerJson"]["answer"]
    assert second["answerJson"]["limitations"] == "general_knowledge"
    assert second["answerJson"]["citations"] == []


@pytest.mark.asyncio
async def test_insufficient_evidence_is_refused_without_calling_provider(db, monkeypatch):
    from app.models.documents import Document, DocumentChunk
    from app.models.learning import LearningPath

    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id, original_filename="science.pdf", storage_key="documents/science.pdf",
        mime_type="application/pdf", size_bytes=100, status="ready",
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentChunk(
            document_id=doc.id, page_start=1, page_end=1, chunk_index=0,
            heading_path=["Chapter 1"], text="Cells are the basic unit of life.",
            text_hash="insufficient-evidence-chunk",
        )
    )
    path = LearningPath(
        owner_id=owner_id, document_id=doc.id, grade=9, subject_id="subject-science",
        status="active", outline_json={"chapters": []},
    )
    db.add(path)
    db.commit()

    called = {"provider": 0, "search": 0}

    async def fake_search(**kwargs):
        called["search"] += 1
        return {"results": [], "insufficient_evidence": True}

    async def fake_chat(**kwargs):
        called["provider"] += 1
        return "This must never be used when a source exists."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-2",
        question_text="What is photosynthesis?", path_id=path.id,
    )
    assert result["status"] == "answered"
    assert result["answerJson"]["citations"] == []
    assert result["answerJson"]["limitations"] == "insufficient_source_evidence"
    assert "does not contain enough evidence" in result["answerJson"]["answer"]
    assert called["provider"] == 0
    assert called["search"] == 1


@pytest.mark.asyncio
async def test_general_question_with_library_but_no_path_never_consults_retrieval(db, monkeypatch):
    from app.models.documents import Document

    owner_id = uuid.uuid4()
    db.add(Document(
        owner_id=owner_id, original_filename="science.pdf", storage_key="documents/science.pdf",
        mime_type="application/pdf", size_bytes=100, status="ready",
    ))
    db.commit()

    called = {"search": 0}

    async def fake_search(**kwargs):
        called["search"] += 1
        return _evidence()

    async def fake_chat(**kwargs):
        return "Photosynthesis converts light energy into chemical energy."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-general-library",
        question_text="What is photosynthesis?",
    )
    assert result["status"] == "answered"
    assert result["answerJson"]["limitations"] == "general_knowledge"
    assert result["answerJson"]["citations"] == []
    assert "light energy" in result["answerJson"]["answer"]
    assert called["search"] == 0


@pytest.mark.asyncio
async def test_general_question_without_source_is_answered_and_labeled(db, monkeypatch):
    owner_id = uuid.uuid4()
    captured = {"prompt": None}

    async def fake_search(**kwargs):
        return {"results": [], "insufficient_evidence": True}

    async def fake_chat(messages=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "Photosynthesis converts light energy into chemical energy."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-no-source",
        question_text="What is photosynthesis?",
    )

    assert result["status"] == "answered"
    assert result["answerJson"]["limitations"] == "general_knowledge"
    assert result["answerJson"]["citations"] == []
    assert "light energy" in result["answerJson"]["answer"]
    assert "photosynthesis" in captured["prompt"]
    assert "general knowledge" in captured["prompt"]


@pytest.mark.asyncio
async def test_general_knowledge_answer_never_invents_page_references(db, monkeypatch):
    owner_id = uuid.uuid4()
    captured = {"prompt": None}

    async def fake_search(**kwargs):
        return {"results": [], "insufficient_evidence": True}

    async def fake_chat(messages=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "Gravity pulls objects toward Earth. (See page 12.)"

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-no-source-2",
        question_text="What is gravity?",
    )
    assert result["status"] == "answered"
    assert result["answerJson"]["limitations"] == "general_knowledge"
    assert result["answerJson"]["citations"] == []
    assert "never invent a page reference" in captured["prompt"]


@pytest.mark.asyncio
async def test_general_knowledge_provider_failure_stays_retryable(db, monkeypatch):
    owner_id = uuid.uuid4()

    async def fake_search(**kwargs):
        return {"results": [], "insufficient_evidence": True}

    async def broken_chat(**kwargs):
        raise RuntimeError("provider offline")

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", broken_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-general-fail",
        question_text="What is photosynthesis?",
    )
    assert result["status"] == "needs_retry"
    assert result["answerJson"]["retryable"] is True
    assert result["answerJson"]["answer"] is None


@pytest.mark.asyncio
async def test_answers_use_the_students_preferred_language(db, monkeypatch):
    from app.models.profiles import UserProfile

    owner_id = uuid.uuid4()
    db.add(UserProfile(id=owner_id, display_name="Hindi Student", preferred_language="hi"))
    db.commit()

    captured = {"prompt": None}

    async def fake_search(**kwargs):
        return {"results": [], "insufficient_evidence": True}

    async def fake_chat(messages=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "प्रकाश संश्लेषण वह प्रक्रिया है।"

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-hindi",
        question_text="What is photosynthesis?",
    )
    assert result["status"] == "answered"
    assert result["answerJson"]["limitations"] == "general_knowledge"
    assert "language code: hi" in captured["prompt"]


def test_blank_question_is_rejected(client):
    response = client.post(
        "/api/v1/doubts",
        headers={"X-User-Id": str(uuid.uuid4())},
        json={"clientDoubtId": "doubt-3", "questionText": "   "},
    )
    assert response.status_code == 422


def test_citations_exclude_unrelated_chapters():
    from app.services.sync_service import select_supporting_citations

    results = [
        {
            "citationId": "cite_1",
            "pageStart": 1,
            "pageEnd": 1,
            "text": (
                "The plasma membrane is selectively permeable. Osmosis is the "
                "movement of water across a selectively permeable membrane."
            ),
        },
        {
            "citationId": "cite_2",
            "pageStart": 2,
            "pageEnd": 2,
            "text": "A tissue is a group of cells that work together.",
        },
        {
            "citationId": "cite_3",
            "pageStart": 3,
            "pageEnd": 3,
            "text": "Living organisms show diversity in size, shape and habitat.",
        },
    ]
    selected = select_supporting_citations(
        results, "What is osmosis and why is the cell membrane selectively permeable?"
    )
    assert [row["citationId"] for row in selected] == ["cite_1"]


@pytest.mark.asyncio
async def test_provider_truncation_is_retryable_not_embedded(db, monkeypatch):
    from app.core.ai_provider import IncompleteGenerationError

    owner_id = uuid.uuid4()

    async def fake_search(**kwargs):
        return _evidence()

    async def truncated_chat(**kwargs):
        raise IncompleteGenerationError("The model stopped before finishing its answer.")

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", truncated_chat)

    result = await sync_service.sync_doubt(
        db=db,
        owner_id=owner_id,
        client_doubt_id="doubt-truncated",
        question_text="What is a cell?",
    )
    assert result["status"] == "needs_retry"
    assert result["answerJson"]["answer"] is None
    assert result["answerJson"]["retryable"] is True

@pytest.mark.asyncio
async def test_doubt_retrieval_is_scoped_to_the_lesson_document(db, monkeypatch):
    from app.models.documents import Document
    from app.models.learning import LearningPath

    owner_id = uuid.uuid4()
    doc = Document(
        owner_id=owner_id, original_filename="cells.pdf", storage_key="documents/cells.pdf",
        mime_type="application/pdf", size_bytes=100, status="ready",
    )
    db.add(doc)
    db.flush()
    path = LearningPath(
        owner_id=owner_id, document_id=doc.id, grade=9, subject_id="subject-science",
        status="active", outline_json={"chapters": []},
    )
    db.add(path)
    db.commit()

    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {
            "results": [{
                "citationId": "cite_1", "documentVersionId": str(doc.id),
                "pageStart": 3, "pageEnd": 3, "headingPath": ["Chapter 1"],
                "text": "Cells are the basic unit of life.",
            }],
            "insufficient_evidence": False,
        }

    async def fake_chat(**kwargs):
        return "Cells are the basic unit of life."

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)
    monkeypatch.setattr(sync_module.ai_provider, "generate_chat", fake_chat)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-scoped",
        question_text="What is a cell?", path_id=path.id,
    )

    assert captured["document_id"] == doc.id
    citation = result["answerJson"]["citations"][0]
    assert citation["sourceTitle"] == "cells.pdf"
    assert citation["documentId"] == str(doc.id)
