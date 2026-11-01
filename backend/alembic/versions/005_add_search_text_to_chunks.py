"""005 add search_text tsvector to document_chunks for full-text search

Revision ID: 005
Revises: 004
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Add generated tsvector column for FTS on document_chunks
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN IF NOT EXISTS search_text tsvector
            GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED
    """)
    # GIN index for fast FTS queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_search_text
        ON document_chunks USING gin(search_text)
    """)
    # Also add a composite index for owner-scoped vector search performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_doc_chunk
        ON document_chunks (document_id, chunk_index)
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_text")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_doc_chunk")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_text")

