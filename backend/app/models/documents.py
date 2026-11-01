import uuid
import datetime
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    source_mode = Column(String(50), default="upload")  # "upload" or "catalog"
    resource_id = Column(String(100), ForeignKey("resources.id"), nullable=True)
    original_filename = Column(String(300), nullable=False)
    storage_bucket = Column(String(100), default="setu-documents")
    storage_key = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=True)
    language_tag = Column(String(20), default="en-IN")
    grade = Column(Integer, nullable=True)
    subject_id = Column(String(50), nullable=True)
    status = Column(String(50), default="queued_for_extraction", index=True)
    page_count = Column(Integer, default=0)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(50), nullable=True)
    safe_error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)
    char_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    is_scanned_ocr_needed = Column(Boolean, default=False)
    extraction_quality = Column(String(50), default="high")
    parser_metadata = Column(JSON, nullable=True)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    heading_path = Column(JSON, nullable=True)  # List[str] e.g. ["Chapter 5", "5.2 Diffusion"]
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False)
    language_tag = Column(String(20), default="en-IN")
    access_scope = Column(String(50), default="private")
    embedding_model_id = Column(String(100), default="text-embedding-nomic-embed-text-v1.5")
    embedding_dimension = Column(Integer, default=768)
    embedding = Column(Vector(768), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

