import uuid

from sqlalchemy.orm import Session

from app.models.profiles import UserProfile

VALID_ROLES = ("student", "teacher", "parent", "admin")


def ensure_profile_from_auth(
    db: Session,
    user_id: uuid.UUID,
    *,
    email: str | None,
    display_name: str,
    role: str = "student",
    grade: int | None = None,
    board_id: str | None = None,
    preferred_language: str | None = None,
) -> UserProfile:
    """Return the existing profile or create one from real signup values only.

    No academic context (grade, board, language, pace) is invented here: any
    value that the caller did not supply stays null so onboarding can ask for
    it instead of guessing.
    """
    profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if profile:
        return profile
    profile = UserProfile(
        id=user_id,
        email=email,
        display_name=display_name.strip()[:150],
        role=role if role in VALID_ROLES else "student",
        grade=grade,
        board_id=board_id,
        preferred_language=preferred_language,
        onboarding_completed=False,
        tour_completed=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
