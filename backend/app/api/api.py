from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.catalogue import router as catalogue_router
from app.api.v1.documents import router as documents_router
from app.api.v1.learning_paths import router as paths_router
from app.api.v1.attempts import router as attempts_router
from app.api.v1.doubts import router as doubts_router
from app.api.v1.sync import router as sync_router
from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.teacher import router as teacher_router
from app.api.v1.study import router as study_router
from app.api.v1.classroom import router as classroom_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(profile_router, prefix="/profile", tags=["Profile"])
api_router.include_router(catalogue_router, prefix="/catalogue", tags=["Catalogue"])
api_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_router.include_router(paths_router, prefix="/learning-paths", tags=["Learning Paths"])
api_router.include_router(attempts_router, prefix="/attempts", tags=["Attempts"])
api_router.include_router(doubts_router, prefix="/doubts", tags=["Doubts"])
api_router.include_router(sync_router, prefix="/sync", tags=["Sync"])
api_router.include_router(teacher_router, prefix="/teacher", tags=["Teacher"])
api_router.include_router(study_router, prefix="/study", tags=["Study"])
api_router.include_router(classroom_router, prefix="/classroom", tags=["Classroom"])

