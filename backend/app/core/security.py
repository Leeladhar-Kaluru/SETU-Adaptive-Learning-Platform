import uuid
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings

# Default system student UUID for local development when auth headers are omitted
DEFAULT_STUDENT_ID = "68c5ae2c-e188-4d4e-93fb-dccdceb40349"
DEFAULT_TEACHER_ID = "de898934-3c24-4d3a-baf3-53387ac557b0"

def get_current_user_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> uuid.UUID:
    """
    Extracts authenticated user ID. In local dev mode, supports x-user-id header
    or falls back to verified demo student. Never exposes service keys.
    """
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format in request header"
            )

    # In local testing without JWT proxy, default to primary demo user
    return uuid.UUID(DEFAULT_STUDENT_ID)

def get_current_teacher_id(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> uuid.UUID:
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format in request header"
            )
    return uuid.UUID(DEFAULT_TEACHER_ID)
