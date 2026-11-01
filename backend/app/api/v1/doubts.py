import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.doubts import Doubt
from app.services.sync_service import sync_service

router = APIRouter()

class DoubtSubmission(BaseModel):
    clientDoubtId: str = Field(min_length=1, max_length=100)
    questionText: str = Field(min_length=3, max_length=2000)
    pathId: Optional[str] = None
    lessonVersionId: Optional[str] = None
    blockId: Optional[str] = None
    sourcePage: Optional[int] = Field(default=None, ge=1)

    @field_validator("clientDoubtId")
    @classmethod
    def _strip_client_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("clientDoubtId is required.")
        return stripped

    @field_validator("questionText")
    @classmethod
    def _require_question(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("A question of at least 3 characters is required.")
        return stripped


def _as_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None

@router.post("")
async def create_or_sync_doubt(
    sub: DoubtSubmission,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Submits or synchronises a contextual doubt.
    Guaranteed idempotent by (owner_id, client_doubt_id).
    Returns grounded answer with citations or truthful retry/processing state.
    """
    result = await sync_service.sync_doubt(
        db=db,
        owner_id=owner_id,
        client_doubt_id=sub.clientDoubtId,
        question_text=sub.questionText,
        path_id=_as_uuid(sub.pathId),
        lesson_version_id=_as_uuid(sub.lessonVersionId),
        block_id=sub.blockId,
        source_page=sub.sourcePage
    )
    return result

@router.get("")
def list_user_doubts(
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    doubts = db.query(Doubt).filter(Doubt.owner_id == owner_id).order_by(Doubt.created_at.desc()).all()
    return [
        {
            "id": str(d.id),
            "clientDoubtId": d.client_doubt_id,
            "status": d.status,
            "questionText": d.question_text,
            "answerJson": d.answer_json,
            "lastErrorCode": d.last_error_code,
            "pathId": str(d.path_id) if d.path_id else None,
            "lessonVersionId": str(d.lesson_version_id) if d.lesson_version_id else None,
            "sourcePage": d.source_page,
            "blockId": d.block_id,
            "createdAt": d.created_at.isoformat()
        }
        for d in doubts
    ]

