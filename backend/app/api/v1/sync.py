import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.sync_service import sync_service

router = APIRouter()

class SyncDoubtsRequest(BaseModel):
    doubts: List[Dict[str, Any]]

@router.post("/doubts")
async def sync_doubts_endpoint(
    req: SyncDoubtsRequest,
    owner_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Idempotent batch synchronisation endpoint specifically for student doubts.
    Malformed items are rejected individually instead of reaching the service.
    """
    results = []
    for d in req.doubts:
        client_doubt_id = d.get("clientDoubtId")
        question_text = str(d.get("questionText") or "").strip()
        if not client_doubt_id or len(question_text) < 3:
            results.append({
                "clientDoubtId": client_doubt_id,
                "status": "rejected",
                "error": "clientDoubtId and a question of at least 3 characters are required.",
            })
            continue

        path_uuid = None
        if d.get("pathId"):
            try:
                path_uuid = uuid.UUID(d["pathId"])
            except Exception:
                pass

        les_ver_uuid = None
        if d.get("lessonVersionId"):
            try:
                les_ver_uuid = uuid.UUID(d["lessonVersionId"])
            except Exception:
                pass

        res = await sync_service.sync_doubt(
            db=db,
            owner_id=owner_id,
            client_doubt_id=client_doubt_id,
            question_text=question_text,
            path_id=path_uuid,
            lesson_version_id=les_ver_uuid,
            block_id=d.get("blockId"),
            source_page=d.get("sourcePage")
        )
        results.append(res)
    return {"results": results}
