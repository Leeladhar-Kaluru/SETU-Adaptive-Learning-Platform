import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_user_id
from app.models.classroom import Classroom
from app.models.curriculum import CurriculumBoard, Language
from app.models.profiles import UserProfile
from app.services.profiles import ensure_profile_from_auth

router = APIRouter()


def _can_teach(db: Session, profile: UserProfile) -> bool:
    if profile.role in ("teacher", "admin"):
        return True
    return (
        db.query(Classroom.id)
        .filter(Classroom.owner_teacher_id == profile.id)
        .first()
        is not None
    )

class SignupRequest(BaseModel):
    email: str
    password: str
    displayName: str
    role: Optional[str] = "student"
    grade: Optional[int] = None
    boardId: Optional[str] = None
    preferredLanguage: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/signup")
async def signup(req: SignupRequest, db: Session = Depends(get_db)):
    """Creates user in Supabase Auth and initializes their SETU profile."""
    if req.role not in (None, "student", "teacher"):
        raise HTTPException(status_code=422, detail="Choose a valid account role.")
    if req.grade is not None and not 6 <= req.grade <= 10:
        raise HTTPException(status_code=422, detail="Class must be between 6 and 10.")
    if req.boardId:
        board = db.query(CurriculumBoard).filter(
            CurriculumBoard.id == req.boardId,
            CurriculumBoard.active.is_(True),
        ).first()
        if not board:
            raise HTTPException(status_code=422, detail="Choose a curriculum board from the list.")
    if req.preferredLanguage:
        language = db.query(Language).filter(
            Language.bcp47_tag == req.preferredLanguage,
            Language.active.is_(True),
        ).first()
        if not language:
            raise HTTPException(status_code=422, detail="Choose a language from the list.")

    user_id_str = None
    access_token = None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Prefer Supabase Admin API if SECRET_KEY is configured (bypasses email confirmation rate limits)
            if settings.SUPABASE_SECRET_KEY and settings.SUPABASE_URL:
                admin_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"
                admin_headers = {
                    "apikey": settings.SUPABASE_SECRET_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}",
                    "Content-Type": "application/json"
                }
                admin_resp = await client.post(admin_url, headers=admin_headers, json={
                    "email": req.email,
                    "password": req.password,
                    "email_confirm": True,
                    "user_metadata": {"displayName": req.displayName, "role": req.role}
                })
                if admin_resp.status_code in (200, 201):
                    user_data = admin_resp.json()
                    user_id_str = user_data.get("id")
                    
                    # Fetch token via password grant
                    token_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
                    tok_headers = {
                        "apikey": settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY,
                        "Content-Type": "application/json"
                    }
                    tok_resp = await client.post(token_url, headers=tok_headers, json={
                        "email": req.email,
                        "password": req.password
                    })
                    if tok_resp.status_code == 200:
                        access_token = tok_resp.json().get("access_token")
                elif admin_resp.status_code in (400, 422) and "already" in admin_resp.text.lower():
                    raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")
                elif admin_resp.status_code != 200:
                    err_json = admin_resp.json() if admin_resp.headers.get("content-type", "").startswith("application/json") else {}
                    detail_msg = err_json.get("msg") or err_json.get("message") or admin_resp.text
                    if "already" in detail_msg.lower():
                        raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")

            # 2. Fallback to standard signup endpoint if not yet created
            if not user_id_str and settings.SUPABASE_URL:
                auth_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/signup"
                headers = {
                    "apikey": settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY}",
                    "Content-Type": "application/json"
                }
                resp = await client.post(auth_url, headers=headers, json={
                    "email": req.email,
                    "password": req.password,
                    "data": {"displayName": req.displayName, "role": req.role}
                })
                if resp.status_code in (200, 201):
                    data = resp.json()
                    user_id_str = data.get("user", {}).get("id") or data.get("id")
                    access_token = data.get("access_token")
                else:
                    err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    detail_msg = err_json.get("msg") or err_json.get("message") or resp.text
                    if "already registered" in detail_msg.lower():
                        raise HTTPException(status_code=400, detail="An account with this email already exists. Please log in.")
                    raise HTTPException(status_code=resp.status_code, detail=detail_msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="The authentication service is temporarily unavailable. Please try again in a moment."
        )

    if not user_id_str:
        raise HTTPException(
            status_code=503,
            detail="Authentication service did not create an account. Try again in a moment.",
        )
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Authentication token was not issued. Try signing in again.",
        )

    user_uuid = uuid.UUID(user_id_str)

    profile = ensure_profile_from_auth(
        db,
        user_uuid,
        email=req.email,
        display_name=req.displayName,
        role=req.role or "student",
        grade=req.grade,
        board_id=req.boardId,
        preferred_language=req.preferredLanguage,
    )

    return {
        "accessToken": access_token,
        "user": {
            "id": str(profile.id),
            "email": profile.email,
            "role": profile.role,
            "canTeach": _can_teach(db, profile),
            "displayName": profile.display_name,
            "grade": profile.grade,
            "boardId": profile.board_id,
            "preferredLanguage": profile.preferred_language,
            "onboardingCompleted": profile.onboarding_completed,
            "tourCompleted": profile.tour_completed
        }
    }

@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Logs in user with Supabase Auth credentials."""
    auth_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_SECRET_KEY,
        "Content-Type": "application/json"
    }

    user_id_str = None
    access_token = None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(auth_url, headers=headers, json={
                "email": req.email,
                "password": req.password
            })
            if resp.status_code == 200:
                data = resp.json()
                user_id_str = data.get("user", {}).get("id")
                access_token = data.get("access_token")
            else:
                err_data = resp.json()
                raise HTTPException(status_code=401, detail=err_data.get("error_description") or "Invalid email or password")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication server unavailable. Please try again.")

    if not user_id_str or not access_token:
        raise HTTPException(
            status_code=503,
            detail="Authentication token was not issued. Try signing in again.",
        )

    user_uuid = uuid.UUID(user_id_str)
    profile = ensure_profile_from_auth(
        db,
        user_uuid,
        email=req.email,
        display_name=req.email.split("@")[0],
    )

    return {
        "accessToken": access_token,
        "user": {
            "id": str(profile.id),
            "email": profile.email,
            "role": profile.role,
            "canTeach": _can_teach(db, profile),
            "displayName": profile.display_name,
            "grade": profile.grade,
            "boardId": profile.board_id,
            "preferredLanguage": profile.preferred_language,
            "onboardingCompleted": profile.onboarding_completed,
            "tourCompleted": profile.tour_completed
        }
    }

@router.get("/me")
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Complete signup or onboarding.",
        )

    return {
        "id": str(profile.id),
        "email": profile.email,
        "role": profile.role,
        "canTeach": _can_teach(db, profile),
        "displayName": profile.display_name,
        "grade": profile.grade,
        "boardId": profile.board_id,
        "preferredLanguage": profile.preferred_language,
        "subjectsInterested": profile.subjects_interested or [],
        "learningGoals": profile.learning_goals or [],
        "dailyGoalMinutes": profile.daily_goal_minutes,
        "accessibilityPreferences": profile.accessibility_preferences or {},
        "onboardingCompleted": profile.onboarding_completed,
        "tourCompleted": profile.tour_completed
    }

@router.post("/logout")
def logout():
    return {"status": "logged_out"}
