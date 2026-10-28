import uuid
import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    path_version = Column(Integer, default=1)
    grade = Column(Integer, nullable=False)
    subject_id = Column(String(50), nullable=False)
    language_tag = Column(String(20), default="en-IN")
    goal = Column(String(100), default="concept_understanding")
    status = Column(String(50), default="active")
    outline_json = Column(JSON, nullable=False)
    rationale = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PathLesson(Base):
    __tablename__ = "path_lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path_id = Column(UUID(as_uuid=True), ForeignKey("learning_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_key = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    sequence = Column(Integer, nullable=False)
    status = Column(String(50), default="queued")  # queued, generating, ready, failed

class LessonVersion(Base):
    __tablename__ = "lesson_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path_lesson_id = Column(UUID(as_uuid=True), ForeignKey("path_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, default=1)
    lesson_package_json = Column(JSON, nullable=False)
    source_version_ids = Column(JSON, nullable=True)
    validation_status = Column(String(50), default="draft")  # draft, validating, ready, rejected
    estimated_bytes = Column(Integer, default=15000)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_version_id = Column(UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_key = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)  # multiple_choice, short_text, numeric, diagram_label
    prompt_json = Column(JSON, nullable=False)
    answer_key_json = Column(JSON, nullable=False)
    rubric_json = Column(JSON, nullable=True)
    concept_ids = Column(JSON, nullable=False)  # List[str]
    difficulty = Column(String(50), default="standard")
    validation_status = Column(String(50), default="ready")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    lesson_version_id = Column(UUID(as_uuid=True), ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False)
    response_json = Column(JSON, nullable=False)
    score = Column(Float, default=0.0)
    is_correct = Column(Boolean, default=False)
    hint_level = Column(Integer, default=0)
    hints_used = Column(JSON, nullable=True)
    elapsed_seconds = Column(Integer, default=0)
    feedback_json = Column(JSON, nullable=True)
    sync_idempotency_key = Column(String(100), unique=True, nullable=True)
    occurred_at = Column(DateTime, default=datetime.datetime.utcnow)

class ConceptEvidence(Base):
    __tablename__ = "concept_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    concept_id = Column(String(100), nullable=False, index=True)
    source_attempt_id = Column(UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=True)
    evidence_type = Column(String(50), default="practice_attempt")
    outcome = Column(String(50), nullable=False)  # correct, incorrect, partially_correct
    weight = Column(Float, default=1.0)
    rationale = Column(String(300), nullable=True)
    occurred_at = Column(DateTime, default=datetime.datetime.utcnow)

class ConceptMasterySnapshot(Base):
    __tablename__ = "concept_mastery_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    concept_id = Column(String(100), nullable=False, index=True)
    estimate_band = Column(String(50), default="not_enough_evidence")  # not_enough_evidence, developing, approaching, demonstrated
    numeric_estimate = Column(Float, nullable=True)
    evidence_count = Column(Integer, default=0)
    freshness = Column(String(50), default="current")
    explanation_json = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, default=datetime.datetime.utcnow)
