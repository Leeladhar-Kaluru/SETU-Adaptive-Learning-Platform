from fastapi import APIRouter
from app.core.database import check_db_health
from app.core.storage import storage_service
from app.core.ai_provider import ai_provider

router = APIRouter()

@router.get("/health")
async def get_system_health():
    """
    Observable health check endpoint probing DB, Storage, and AI provider.
    Never exposes keys or secrets.
    """
    db_ok = check_db_health()
    storage_ok = await storage_service.check_health()
    ai_status = await ai_provider.check_health()

    all_healthy = db_ok and storage_ok and ai_status.get("chat_ready", False) and ai_status.get("embed_ready", False)

    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": {
            "database": {"connected": db_ok, "engine": "PostgreSQL 17 (pgvector 768d)"},
            "storage": {"connected": storage_ok, "bucket": "setu-documents"},
            "ai_provider": ai_status
        }
    }

