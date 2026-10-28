import uuid
import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=True)
    role = Column(String(50), default="student", index=True)  # "student", "teacher", "parent", "admin"
    display_name = Column(String(150), nullable=False)
    preferred_language = Column(String(20), nullable=True)
    board_id = Column(String(50), ForeignKey("curriculum_boards.id"), nullable=True)
    grade = Column(Integer, nullable=True, index=True)
    subjects_interested = Column(JSON, default=list)  # ["subject-science", "subject-math", ...]
    learning_goals = Column(JSON, default=list)  # ["Board Exam Prep", "Concept Mastery", ...]
    target_date = Column(DateTime, nullable=True)
    daily_goal_minutes = Column(Integer, nullable=True)
    accessibility_preferences = Column(JSON, default=dict)  # {"font_size": "medium", "reduced_motion": false, "high_contrast": false}
    onboarding_completed = Column(Boolean, default=False)
    tour_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

