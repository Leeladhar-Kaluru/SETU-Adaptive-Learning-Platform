import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.sync_service import sync_service

router = APIRouter()

class SyncBatchRequest(BaseModel):
    events: List[Dict[str, Any]]

class DoubtSyncItem(BaseModel):
    clientDoubtId: str
    questionText: str
    pathId: Optional[Any] = None
    lessonVersionId: Optional[Any] = None
    blockId: Optional[str] = None
    sourcePage: Optional[int] = None
    submittedAt: Optional[str] = None

class SyncDoubtsRequest(BaseModel):
    doubts: List[DoubtSyncItem]

@router.post("/doubts")
async def sync_doubts(
    req: SyncDoubtsRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Idempotent batch sync endpoint for offline doubts outbox.
    """
    results = []
    for d in req.doubts:
        # Parse path_id if UUID string
        p_id = None
        if d.pathId:
            try:
                p_id = uuid.UUID(str(d.pathId))
            except Exception:
                p_id = None

        res = await sync_service.sync_doubt(
            db=db,
            owner_id=owner_id,
            client_doubt_id=d.clientDoubtId,
            question_text=d.questionText,
            path_id=p_id,
            block_id=d.blockId,
            source_page=d.sourcePage
        )
        results.append(res)
    return {"results": results}

@router.post("/events")
@router.post("/batch")
def sync_batch_events(
    req: SyncBatchRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Idempotent batch synchronisation endpoint for offline client actions.
    """
    results = sync_service.sync_batch_events(
        db=db,
        owner_id=owner_id,
        events=req.events
    )
    return {"results": results}
