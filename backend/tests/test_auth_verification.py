import asyncio
import base64
import json
import time

import pytest

from app.core import security


def _token(exp: float) -> str:
    def enc(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{enc({'alg': 'HS256', 'typ': 'JWT'})}.{enc({'sub': 'user-1', 'exp': exp})}.signature"


@pytest.fixture(autouse=True)
def _clear_cache():
    security._token_cache.clear()
    security._inflight_checks.clear()
    yield
    security._token_cache.clear()
    security._inflight_checks.clear()


def test_valid_token_is_cached_and_concurrent_checks_share_one_upstream_call(monkeypatch):
    monkeypatch.setattr(security.settings, "SUPABASE_URL", "https://example.supabase.co")
    calls = []

    async def fake_fetch(token: str):
        calls.append(token)
        await asyncio.sleep(0.05)
        return {"id": "8f7e6d5c-4b3a-4918-8271-665544332211", "email": "student@example.com"}

    monkeypatch.setattr(security, "_fetch_supabase_user", fake_fetch)
    token = _token(time.time() + 3600)

    async def run():
        return await asyncio.gather(*(security.verify_supabase_token(token) for _ in range(6)))

    results = asyncio.run(run())

    assert all(result and result["id"].startswith("8f7e") for result in results)
    assert len(calls) == 1


def test_expired_token_is_rejected_without_an_upstream_call(monkeypatch):
    monkeypatch.setattr(security.settings, "SUPABASE_URL", "https://example.supabase.co")
    calls = []

    async def fake_fetch(token: str):
        calls.append(token)
        return {"id": "unexpected"}

    monkeypatch.setattr(security, "_fetch_supabase_user", fake_fetch)

    assert asyncio.run(security.verify_supabase_token(_token(time.time() - 60))) is None
    assert calls == []


def test_upstream_failure_is_not_treated_as_an_invalid_token(monkeypatch):
    monkeypatch.setattr(security.settings, "SUPABASE_URL", "https://example.supabase.co")

    async def failing_fetch(token: str):
        raise security.AuthUpstreamError("Supabase Auth returned 503")

    monkeypatch.setattr(security, "_fetch_supabase_user", failing_fetch)

    with pytest.raises(security.AuthUpstreamError):
        asyncio.run(security.verify_supabase_token(_token(time.time() + 3600)))
