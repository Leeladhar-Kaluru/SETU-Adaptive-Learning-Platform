"""001_initial_setu_schema

Revision ID: 001
Revises: 
Create Date: 2026-10-28 12:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Ensure required extensions exist
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2. Curriculum & Resources
    op.create_table(
        'curriculum_boards',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('code', sa.String(20), unique=True, nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('official_url', sa.String(500), nullable=True),
        sa.Column('active', sa.Boolean(), default=True)
    )

    op.create_table(
        'subjects',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('code', sa.String(20), unique=True, nullable=False),
        sa.Column('canonical_name', sa.String(100), nullable=False),
        sa.Column('active', sa.Boolean(), default=True)
    )

    op.create_table(
        'languages',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('bcp47_tag', sa.String(20), unique=True, nullable=False),
        sa.Column('native_name', sa.String(100), nullable=False),
        sa.Column('script', sa.String(50), nullable=False),
        sa.Column('active', sa.Boolean(), default=True)
    )

    op.create_table(
        'resource_sources',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=False),
        sa.Column('terms_url', sa.String(500), nullable=True),
        sa.Column('verification_status', sa.String(50), default='unverified'),
        sa.Column('allowed_actions', sa.JSON(), nullable=True),
        sa.Column('rights_notes', sa.String(1000), nullable=True),
        sa.Column('last_verified_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'resources',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('source_id', sa.String(100), sa.ForeignKey('resource_sources.id'), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('board_id', sa.String(50), sa.ForeignKey('curriculum_boards.id'), nullable=True),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('subject_id', sa.String(50), sa.ForeignKey('subjects.id'), nullable=True),
        sa.Column('language_id', sa.String(50), sa.ForeignKey('languages.id'), nullable=True),
        sa.Column('publisher', sa.String(150), nullable=True),
        sa.Column('edition', sa.String(50), nullable=True),
        sa.Column('resource_kind', sa.String(50), default='textbook'),
        sa.Column('external_url', sa.String(500), nullable=True),
        sa.Column('verification_status', sa.String(50), default='verified')
    )

    op.create_table(
        'resource_rights',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('resource_id', sa.String(100), sa.ForeignKey('resources.id'), nullable=False),
        sa.Column('license_name', sa.String(150), nullable=False),
        sa.Column('license_url', sa.String(500), nullable=True),
        sa.Column('rights_notes', sa.String(1000), nullable=True),
        sa.Column('can_link', sa.Boolean(), default=True),
        sa.Column('can_download', sa.Boolean(), default=False),
        sa.Column('can_store', sa.Boolean(), default=False),
        sa.Column('can_process', sa.Boolean(), default=False),
        sa.Column('can_embed', sa.Boolean(), default=False),
        sa.Column('can_offline_cache', sa.Boolean(), default=False),
        sa.Column('can_redistribute', sa.Boolean(), default=False),
        sa.Column('reviewed_at', sa.DateTime(), server_default=sa.func.now())
    )

    # 3. Documents & Extraction
    op.create_table(
        'documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('source_mode', sa.String(50), default='upload'),
        sa.Column('resource_id', sa.String(100), sa.ForeignKey('resources.id'), nullable=True),
        sa.Column('original_filename', sa.String(300), nullable=False),
        sa.Column('storage_bucket', sa.String(100), default='setu-documents'),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=True),
        sa.Column('language_tag', sa.String(20), default='en-IN'),
        sa.Column('grade', sa.Integer(), nullable=True),
        sa.Column('subject_id', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), default='queued_for_extraction', index=True),
        sa.Column('page_count', sa.Integer(), default=0),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('safe_error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True)
    )

    op.create_table(
        'document_pages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('char_count', sa.Integer(), default=0),
        sa.Column('word_count', sa.Integer(), default=0),
        sa.Column('is_scanned_ocr_needed', sa.Boolean(), default=False),
        sa.Column('extraction_quality', sa.String(50), default='high'),
        sa.Column('parser_metadata', sa.JSON(), nullable=True)
    )

    op.create_table(
        'document_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('page_start', sa.Integer(), nullable=False),
        sa.Column('page_end', sa.Integer(), nullable=False),
        sa.Column('heading_path', sa.JSON(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('text_hash', sa.String(64), nullable=False),
        sa.Column('language_tag', sa.String(20), default='en-IN'),
        sa.Column('access_scope', sa.String(50), default='private'),
        sa.Column('embedding_model_id', sa.String(100), default='text-embedding-nomic-embed-text-v1.5'),
        sa.Column('embedding_dimension', sa.Integer(), default=768),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    # Hybrid Search columns & indexes on document_chunks
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN search_text tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
    """)
    op.execute("CREATE INDEX idx_chunks_search_text ON document_chunks USING GIN(search_text);")
    op.execute("CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);")

    # 4. Learning Paths & Lessons
    op.create_table(
        'learning_paths',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('path_version', sa.Integer(), default=1),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.String(50), nullable=False),
        sa.Column('language_tag', sa.String(20), default='en-IN'),
        sa.Column('goal', sa.String(100), default='concept_understanding'),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('outline_json', sa.JSON(), nullable=False),
        sa.Column('rationale', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'path_lessons',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('path_id', UUID(as_uuid=True), sa.ForeignKey('learning_paths.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('lesson_key', sa.String(100), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), default='queued')
    )

    op.create_table(
        'lesson_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('path_lesson_id', UUID(as_uuid=True), sa.ForeignKey('path_lessons.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_number', sa.Integer(), default=1),
        sa.Column('lesson_package_json', sa.JSON(), nullable=False),
        sa.Column('source_version_ids', sa.JSON(), nullable=True),
        sa.Column('validation_status', sa.String(50), default='draft'),
        sa.Column('estimated_bytes', sa.Integer(), default=15000),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'questions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('lesson_version_id', UUID(as_uuid=True), sa.ForeignKey('lesson_versions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('question_key', sa.String(100), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('prompt_json', sa.JSON(), nullable=False),
        sa.Column('answer_key_json', sa.JSON(), nullable=False),
        sa.Column('rubric_json', sa.JSON(), nullable=True),
        sa.Column('concept_ids', sa.JSON(), nullable=False),
        sa.Column('difficulty', sa.String(50), default='standard'),
        sa.Column('validation_status', sa.String(50), default='ready')
    )

    op.create_table(
        'quiz_attempts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lesson_version_id', UUID(as_uuid=True), sa.ForeignKey('lesson_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('response_json', sa.JSON(), nullable=False),
        sa.Column('score', sa.Float(), default=0.0),
        sa.Column('is_correct', sa.Boolean(), default=False),
        sa.Column('hint_level', sa.Integer(), default=0),
        sa.Column('hints_used', sa.JSON(), nullable=True),
        sa.Column('elapsed_seconds', sa.Integer(), default=0),
        sa.Column('feedback_json', sa.JSON(), nullable=True),
        sa.Column('sync_idempotency_key', sa.String(100), unique=True, nullable=True),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'concept_evidence',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('concept_id', sa.String(100), nullable=False, index=True),
        sa.Column('source_attempt_id', UUID(as_uuid=True), sa.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('evidence_type', sa.String(50), default='practice_attempt'),
        sa.Column('outcome', sa.String(50), nullable=False),
        sa.Column('weight', sa.Float(), default=1.0),
        sa.Column('rationale', sa.String(300), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'concept_mastery_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('concept_id', sa.String(100), nullable=False, index=True),
        sa.Column('estimate_band', sa.String(50), default='not_enough_evidence'),
        sa.Column('numeric_estimate', sa.Float(), nullable=True),
        sa.Column('evidence_count', sa.Integer(), default=0),
        sa.Column('freshness', sa.String(50), default='current'),
        sa.Column('explanation_json', sa.JSON(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now())
    )

    # 5. Doubts & Offline Sync
    op.create_table(
        'doubts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('client_doubt_id', sa.String(100), nullable=False),
        sa.Column('path_id', UUID(as_uuid=True), sa.ForeignKey('learning_paths.id', ondelete='SET NULL'), nullable=True),
        sa.Column('lesson_version_id', UUID(as_uuid=True), sa.ForeignKey('lesson_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('block_id', sa.String(100), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), default='queued_offline'),
        sa.Column('answer_json', sa.JSON(), nullable=True),
        sa.Column('last_error_code', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('owner_id', 'client_doubt_id', name='uq_owner_client_doubt')
    )

    op.create_table(
        'sync_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('client_event_id', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('applied_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.UniqueConstraint('owner_id', 'client_event_id', name='uq_owner_client_event')
    )

    # 6. Durable Background Generation Jobs
    op.create_table(
        'generation_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('job_type', sa.String(50), default='generate_lesson'),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('path_id', UUID(as_uuid=True), sa.ForeignKey('learning_paths.id', ondelete='CASCADE'), nullable=False),
        sa.Column('path_version', sa.Integer(), default=1),
        sa.Column('lesson_id', UUID(as_uuid=True), sa.ForeignKey('path_lessons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('priority', sa.Integer(), default=10),
        sa.Column('status', sa.String(50), default='queued', index=True),
        sa.Column('attempt_count', sa.Integer(), default=0),
        sa.Column('max_attempts', sa.Integer(), default=3),
        sa.Column('not_before', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('lease_owner', sa.String(100), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(), nullable=True),
        sa.Column('idempotency_key', sa.String(150), unique=True, nullable=False),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('safe_error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('idempotency_key', name='uq_generation_idempotency_key')
    )

    # 7. Classrooms & Teacher Support
    op.create_table(
        'classrooms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('owner_teacher_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('board_id', sa.String(50), nullable=True),
        sa.Column('grade', sa.Integer(), nullable=False),
        sa.Column('subject_scope', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

    op.create_table(
        'classroom_memberships',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('classroom_id', UUID(as_uuid=True), sa.ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('student_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('role', sa.String(50), default='student'),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('classroom_id', 'student_id', name='uq_classroom_student_membership')
    )

    op.create_table(
        'teacher_actions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('teacher_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('classroom_id', UUID(as_uuid=True), sa.ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('reason_json', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(50), default='proposed'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True)
    )

    # 8. Seed Verified Foundation Data (Boards, Subjects, Languages, Catalogues)
    op.execute("""
        INSERT INTO curriculum_boards (id, code, name, region, official_url, active) VALUES
        ('board-cbse', 'CBSE', 'Central Board of Secondary Education', 'National', 'https://www.cbse.gov.in', TRUE),
        ('board-ncert', 'NCERT', 'National Council of Educational Research and Training', 'National', 'https://ncert.nic.in', TRUE),
        ('board-icse', 'ICSE', 'Indian Certificate of Secondary Education', 'National', 'https://cisce.org', TRUE),
        ('board-telangana', 'TS-SCERT', 'Telangana State Board', 'Telangana', 'https://scert.telangana.gov.in', TRUE),
        ('board-karnataka', 'KSEEB', 'Karnataka School Examination and Assessment Board', 'Karnataka', 'https://kseab.karnataka.gov.in', TRUE),
        ('board-maharashtra', 'MSBSHSE', 'Maharashtra State Board', 'Maharashtra', 'https://mahahsscboard.in', TRUE);
    """)

    op.execute("""
        INSERT INTO subjects (id, code, canonical_name, active) VALUES
        ('subject-science', 'SCIENCE', 'Science', TRUE),
        ('subject-math', 'MATH', 'Mathematics', TRUE),
        ('subject-social', 'SOCIAL', 'Social Science', TRUE),
        ('subject-english', 'ENGLISH', 'English', TRUE),
        ('subject-hindi', 'HINDI', 'Hindi', TRUE);
    """)

    op.execute("""
        INSERT INTO languages (id, bcp47_tag, native_name, script, active) VALUES
        ('lang-en', 'en-IN', 'English (India)', 'Latin', TRUE),
        ('lang-hi', 'hi-IN', 'हिन्दी (Hindi)', 'Devanagari', TRUE),
        ('lang-te', 'te-IN', 'తెలుగు (Telugu)', 'Telugu', TRUE),
        ('lang-ur', 'ur-IN', 'اردو (Urdu)', 'Arabic', TRUE);
    """)

    op.execute("""
        INSERT INTO resource_sources (id, name, source_type, source_url, terms_url, verification_status, rights_notes) VALUES
        ('ncert-portal', 'NCERT Online Textbooks', 'official_national_textbook_portal', 'https://ncert.nic.in/textbook.php', 'https://ncert.nic.in', 'verified', 'Official NCERT curriculum textbooks; educational use with page citation.');
    """)

    op.execute("""
        INSERT INTO resources (id, source_id, title, board_id, grade, subject_id, language_id, publisher, edition, resource_kind, external_url) VALUES
        ('res-ncert-sci-9', 'ncert-portal', 'NCERT Class 9 Science', 'board-ncert', 9, 'subject-science', 'lang-en', 'NCERT', '2024-25', 'textbook', 'https://ncert.nic.in/textbook.php?jesc1=0-15'),
        ('res-ncert-math-9', 'ncert-portal', 'NCERT Class 9 Mathematics', 'board-ncert', 9, 'subject-math', 'lang-en', 'NCERT', '2024-25', 'textbook', 'https://ncert.nic.in/textbook.php?jemh1=0-15'),
        ('res-ncert-sci-10', 'ncert-portal', 'NCERT Class 10 Science', 'board-ncert', 10, 'subject-science', 'lang-en', 'NCERT', '2024-25', 'textbook', 'https://ncert.nic.in/textbook.php?jesc2=0-16');
    """)

    op.execute("""
        INSERT INTO resource_rights (id, resource_id, license_name, can_link, can_download, can_store, can_process, can_embed, can_offline_cache, can_redistribute) VALUES
        ('rights-ncert-sci-9', 'res-ncert-sci-9', 'NCERT Educational Fair Use', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, FALSE),
        ('rights-ncert-math-9', 'res-ncert-math-9', 'NCERT Educational Fair Use', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, FALSE),
        ('rights-ncert-sci-10', 'res-ncert-sci-10', 'NCERT Educational Fair Use', TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, FALSE);
    """)

def downgrade() -> None:
    pass
