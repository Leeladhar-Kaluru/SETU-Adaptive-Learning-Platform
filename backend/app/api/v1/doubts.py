import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.doubts import Doubt
from app.services.sync_service import sync_service

router = APIRouter()

class DoubtSubmission(BaseModel):
    clientDoubtId: str
    questionText: str
    pathId: Optional[uuid.UUID] = None
    lessonVersionId: Optional[uuid.UUID] = None
    blockId: Optional[str] = None
    sourcePage: Optional[int] = None

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
        path_id=sub.pathId,
        lesson_version_id=sub.lessonVersionId,
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
            "sourcePage": d.source_page,
            "blockId": d.block_id,
            "createdAt": d.created_at.isoformat()
        }
        for d in doubts
    ]
