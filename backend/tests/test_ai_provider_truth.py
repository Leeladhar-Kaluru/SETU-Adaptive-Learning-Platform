import httpx
import pytest

from app.core.ai_provider import ai_provider


@pytest.mark.asyncio
async def test_empty_text_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        await ai_provider.get_embedding("   ")


@pytest.mark.asyncio
async def test_wrong_dimension_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1] * 12}]}

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ValueError, match="dimension"):
        await ai_provider.get_embedding("real text")


@pytest.mark.asyncio
async def test_batch_count_mismatch_is_rejected(monkeypatch):
    class FakeResponse:
        status_code = 200
        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1] * 768}]}

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(ValueError, match="count"):
        await ai_provider.get_embeddings_batch(["one", "two"])
