import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base

class CurriculumBoard(Base):
    __tablename__ = "curriculum_boards"

    id = Column(String(50), primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    region = Column(String(100), nullable=True)
    official_url = Column(String(500), nullable=True)
    active = Column(Boolean, default=True)

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(String(50), primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    canonical_name = Column(String(100), nullable=False)
    active = Column(Boolean, default=True)

class Language(Base):
    __tablename__ = "languages"

    id = Column(String(50), primary_key=True)
    bcp47_tag = Column(String(20), unique=True, nullable=False)
    native_name = Column(String(100), nullable=False)
    script = Column(String(50), nullable=False)
    active = Column(Boolean, default=True)

class ResourceSource(Base):
    __tablename__ = "resource_sources"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_url = Column(String(500), nullable=False)
    terms_url = Column(String(500), nullable=True)
    verification_status = Column(String(50), default="unverified")
    allowed_actions = Column(JSON, nullable=True)
    rights_notes = Column(String(1000), nullable=True)
    last_verified_at = Column(DateTime, default=datetime.datetime.utcnow)

class Resource(Base):
    __tablename__ = "resources"

    id = Column(String(100), primary_key=True)
    source_id = Column(String(100), ForeignKey("resource_sources.id"), nullable=False)
    title = Column(String(300), nullable=False)
    board_id = Column(String(50), ForeignKey("curriculum_boards.id"), nullable=True)
    grade = Column(Integer, nullable=True)
    subject_id = Column(String(50), ForeignKey("subjects.id"), nullable=True)
    language_id = Column(String(50), ForeignKey("languages.id"), nullable=True)
    publisher = Column(String(150), nullable=True)
    edition = Column(String(50), nullable=True)
    resource_kind = Column(String(50), default="textbook")
    external_url = Column(String(500), nullable=True)
    verification_status = Column(String(50), default="unverified")

class ResourceRight(Base):
    __tablename__ = "resource_rights"

    id = Column(String(100), primary_key=True)
    resource_id = Column(String(100), ForeignKey("resources.id"), nullable=False)
    license_name = Column(String(150), nullable=False)
    license_url = Column(String(500), nullable=True)
    rights_notes = Column(String(1000), nullable=True)
    can_link = Column(Boolean, default=False)
    can_download = Column(Boolean, default=False)
    can_store = Column(Boolean, default=False)
    can_process = Column(Boolean, default=False)
    can_embed = Column(Boolean, default=False)
    can_offline_cache = Column(Boolean, default=False)
    can_redistribute = Column(Boolean, default=False)
    reviewed_at = Column(DateTime, default=datetime.datetime.utcnow)

