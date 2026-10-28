import uuid
import httpx
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.profiles import UserProfile


async def verify_supabase_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies a JWT Bearer token against Supabase Auth API."""
    if not settings.SUPABASE_URL or not token:
        return None

    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


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
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        user_info = await verify_supabase_token(token)
        if user_info and "id" in user_info:
            try:
                return uuid.UUID(user_info["id"])
            except ValueError:
                pass

    if x_user_id and _test_auth_enabled():
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format in request header",
            )

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
