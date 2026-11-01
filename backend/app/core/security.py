import asyncio
import base64
import hashlib
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any

import httpx
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.classroom import Classroom
from app.models.profiles import UserProfile

logger = logging.getLogger(__name__)

# Supabase Auth is the authority. Verifying each request with a fresh HTTPS call
# made every page load depend on an external round trip and caused intermittent
# 401s when several dashboard requests arrived together. Cache successful
# verifications briefly and collapse concurrent checks of the same token into a
# single upstream request.
_TOKEN_CACHE_TTL_SECONDS = 60.0
_TOKEN_CACHE_MAX_ENTRIES = 512
_token_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_inflight_checks: Dict[str, asyncio.Task] = {}
_http_client: Optional[httpx.AsyncClient] = None


class AuthUpstreamError(Exception):
    """Supabase Auth could not answer; this is not proof of an invalid token."""


def _decode_claims(token: str) -> Dict[str, Any]:
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}


def _token_expiry(token: str) -> Optional[float]:
    exp = _decode_claims(token).get("exp")
    return float(exp) if isinstance(exp, (int, float)) else None


def _cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _auth_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(6.0, connect=3.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={
                "apikey": settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY,
            },
        )
    return _http_client


async def _fetch_supabase_user(token: str) -> Optional[Dict[str, Any]]:
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {"Authorization": f"Bearer {token}"}
    last_error: Optional[Exception] = None

    for attempt in range(2):
        try:
            resp = await _auth_client().get(url, headers=headers)
        except httpx.HTTPError as exc:
            last_error = exc
        else:
            if resp.status_code == 200:
                try:
                    body = resp.json()
                except ValueError as exc:
                    last_error = exc
                else:
                    return body if isinstance(body, dict) else None
            if resp.status_code in (401, 403):
                return None
            last_error = RuntimeError(f"Supabase Auth returned {resp.status_code}")
        if attempt == 0:
            await asyncio.sleep(0.15)

    raise AuthUpstreamError(str(last_error) if last_error else "Supabase Auth unavailable")


async def _fetch_and_cache(token: str, key: str) -> Optional[Dict[str, Any]]:
    try:
        user_info = await _fetch_supabase_user(token)
        if user_info:
            now = time.time()
            expires_at = _token_expiry(token)
            ttl = min(_TOKEN_CACHE_TTL_SECONDS, (expires_at - now) if expires_at else _TOKEN_CACHE_TTL_SECONDS)
            if ttl > 0:
                if len(_token_cache) >= _TOKEN_CACHE_MAX_ENTRIES:
                    for stale in [k for k, (until, _) in _token_cache.items() if until <= now]:
                        _token_cache.pop(stale, None)
                _token_cache[key] = (now + ttl, user_info)
        return user_info
    finally:
        _inflight_checks.pop(key, None)


async def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a Supabase Bearer token, with a short cache and single-flight."""
    if not settings.SUPABASE_URL or not token:
        return None

    expires_at = _token_expiry(token)
    now = time.time()
    if expires_at is not None and expires_at <= now:
        return None

    key = _cache_key(token)
    cached = _token_cache.get(key)
    if cached and cached[0] > now:
        return cached[1]
    if cached:
        _token_cache.pop(key, None)

    task = _inflight_checks.get(key)
    if task is None:
        task = asyncio.create_task(_fetch_and_cache(token, key))
        _inflight_checks[key] = task
    return await task


def _test_auth_enabled() -> bool:
    """X-User-Id is a test-harness credential, never a production one."""
    return settings.APP_ENV == "test" and settings.SETU_TEST_AUTH is True


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> uuid.UUID:
    """
    Resolves the authenticated user UUID from a Bearer JWT or, in the isolated
    test harness only, from X-User-Id. Returns HTTP 401 if no valid credential
    is present.
    """
    if x_user_id and _test_auth_enabled():
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format in request header",
            )

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        try:
            user_info = await verify_supabase_token(token)
        except AuthUpstreamError:
            logger.warning("Supabase auth verification unavailable")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SETU could not verify your session right now. Please retry in a moment.",
                headers={"Retry-After": "2"},
            )
        if user_info and "id" in user_info:
            try:
                return uuid.UUID(user_info["id"])
            except ValueError:
                pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_teacher_id(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Resolves a teacher (or admin) user UUID; 403 for every other role."""
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not profile or profile.role not in ("teacher", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A teacher account is required for this action.",
        )
    return user_id


async def get_current_educator_id(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> uuid.UUID:
    """Resolve a teacher/admin, or the recorded owner of a real classroom.

    A profile whose role is still `student` but which owns classrooms is a
    data-entry conflict, not a security boundary. Ownership is checked against
    the classroom rows themselves and every teacher endpoint still scopes its
    query to `owner_teacher_id == this id`, so an owner can only read or change
    classrooms they actually own. This avoids mutating production roles just to
    unblock a legitimate classroom owner.
    """
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if profile and profile.role in ("teacher", "admin"):
        return user_id
    owns_classroom = (
        db.query(Classroom.id)
        .filter(Classroom.owner_teacher_id == user_id)
        .first()
        is not None
    )
    if owns_classroom:
        return user_id
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="A teacher account or classroom ownership is required for this action.",
    )
