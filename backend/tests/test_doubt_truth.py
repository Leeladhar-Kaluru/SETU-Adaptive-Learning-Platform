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
    assert len(second["answerJson"]["citations"]) == 1


@pytest.mark.asyncio
async def test_insufficient_evidence_is_answered_without_citations(db, monkeypatch):
    owner_id = uuid.uuid4()

    async def fake_search(**kwargs):
        return {"results": [], "insufficient_evidence": True}

    monkeypatch.setattr(sync_module.retrieval_service, "hybrid_search", fake_search)

    result = await sync_service.sync_doubt(
        db=db, owner_id=owner_id, client_doubt_id="doubt-2",
        question_text="What is photosynthesis?",
    )
    assert result["status"] == "answered"
    assert result["answerJson"]["citations"] == []
    assert result["answerJson"]["limitations"] == "insufficient_source_evidence"
    assert "does not contain enough evidence" in result["answerJson"]["answer"]


def test_blank_question_is_rejected(client):
    response = client.post(
        "/api/v1/doubts",
        headers={"X-User-Id": str(uuid.uuid4())},
        json={"clientDoubtId": "doubt-3", "questionText": "   "},
    )
    assert response.status_code == 422
