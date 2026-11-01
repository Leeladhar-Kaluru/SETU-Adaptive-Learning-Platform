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


def test_corrupt_output_is_repaired_and_stored():
    from app.core.ai_provider import _clean_generated_text

    cleaned = _clean_generated_text("Osmosis moves water.\ufffd\x00")
    assert "\ufffd" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "Osmosis moves water."


def test_prose_completeness_requires_a_finished_thought():
    from app.core.ai_provider import _is_complete_prose

    assert _is_complete_prose("Cells are the basic unit of life.")
    assert _is_complete_prose("The answer is on page 3")
    assert _is_complete_prose('The answer is "diffusion."')
    assert _is_complete_prose("Which organelle is this?")
    assert not _is_complete_prose("As your SETU Academic Tutor")
    assert not _is_complete_prose("The answer is")
    assert not _is_complete_prose("")


@pytest.mark.asyncio
async def test_chat_truncation_is_rejected_even_with_stop_finish(monkeypatch):
    from app.core.ai_provider import IncompleteGenerationError

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "choices": [{
                    "message": {"content": "As your SETU Academic Tutor"},
                    "finish_reason": "stop",
                }]
            }

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(IncompleteGenerationError, match="finishing"):
        await ai_provider.generate_chat(
            [{"role": "user", "content": "Explain osmosis."}],
            require_complete=True,
        )


@pytest.mark.asyncio
async def test_chat_cleans_corrupt_bytes_without_failing(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "choices": [{
                    "message": {"content": "Osmosis moves water.\ufffd\x00"},
                    "finish_reason": "stop",
                }]
            }

    async def fake_post(self, url, json):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    answer = await ai_provider.generate_chat(
        [{"role": "user", "content": "Explain osmosis."}],
        require_complete=True,
    )
    assert answer == "Osmosis moves water."


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

