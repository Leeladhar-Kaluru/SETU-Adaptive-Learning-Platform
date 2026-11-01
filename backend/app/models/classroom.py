import uuid
import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Classroom(Base):
    __tablename__ = "classrooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_teacher_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    board_id = Column(String(50), nullable=True)
    grade = Column(Integer, nullable=False)
    subject_scope = Column(String(100), nullable=False)
    join_code = Column(String(15), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ClassroomMembership(Base):
    __tablename__ = "classroom_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id = Column(UUID(as_uuid=True), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role = Column(String(50), default="student")  # student, teacher, co_teacher
    status = Column(String(50), default="active")  # active, invited, removed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student_membership"),
    )

class TeacherAction(Base):
    __tablename__ = "teacher_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    classroom_id = Column(UUID(as_uuid=True), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # recommend_prerequisite, assign_practice, override_mastery, custom_note
    reason_json = Column(JSON, nullable=False)
    status = Column(String(50), default="proposed")  # proposed, accepted, edited, dismissed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class ClassroomMessage(Base):
    __tablename__ = "classroom_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id = Column(UUID(as_uuid=True), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    kind = Column(String(20), default="group")  # group, direct
    recipient_id = Column(UUID(as_uuid=True), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

