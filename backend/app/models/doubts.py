import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Doubt(Base):
    __tablename__ = "doubts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    client_doubt_id = Column(String(100), nullable=False)
    path_id = Column(UUID(as_uuid=True), ForeignKey("learning_paths.id", ondelete="SET NULL"), nullable=True)
    lesson_version_id = Column(UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="SET NULL"), nullable=True)
    block_id = Column(String(100), nullable=True)
    source_page = Column(Integer, nullable=True)
    question_text = Column(Text, nullable=False)
    status = Column(String(50), default="queued_offline")  # queued_offline, sending, processing, answered, needs_retry
    answer_json = Column(JSON, nullable=True)  # {"answer": "...", "citations": [...], "limitations": "..."}
    last_error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("owner_id", "client_doubt_id", name="uq_owner_client_doubt"),
    )

class SyncEvent(Base):
    __tablename__ = "sync_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    client_event_id = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)  # attempt_sync, doubt_sync
    payload_json = Column(JSON, nullable=False)
    applied_at = Column(DateTime, default=datetime.datetime.utcnow)
    result_json = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("owner_id", "client_event_id", name="uq_owner_client_event"),
    )
