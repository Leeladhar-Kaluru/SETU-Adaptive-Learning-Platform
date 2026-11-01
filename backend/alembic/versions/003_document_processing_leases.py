"""Add document processing leases for the background worker.

Revision ID: 003
Revises: 002
Create Date: 2026-10-28 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("lease_owner", sa.String(length=100), nullable=True))
    op.add_column("documents", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_documents_processing_queue",
        "documents",
        ["created_at"],
        postgresql_where=sa.text("status = 'stored' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_processing_queue", table_name="documents")
    op.drop_column("documents", "attempt_count")
    op.drop_column("documents", "lease_expires_at")
    op.drop_column("documents", "lease_owner")
