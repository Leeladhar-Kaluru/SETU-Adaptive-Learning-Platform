import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(String(50), default="generate_lesson")
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    path_id = Column(UUID(as_uuid=True), ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False)
    path_version = Column(Integer, default=1)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("path_lessons.id", ondelete="CASCADE"), nullable=False)
    priority = Column(Integer, default=10)  # Lower is higher priority (e.g. 1 for first 3 lessons, 10 for later)
    status = Column(String(50), default="queued", index=True)  # queued, claimed, generating, validating, ready, retry_wait, failed, cancelled
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    not_before = Column(DateTime, default=datetime.datetime.utcnow)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String(150), unique=True, nullable=False)
    error_code = Column(String(50), nullable=True)
    safe_error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_generation_idempotency_key"),
    )

