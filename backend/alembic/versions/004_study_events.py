"""Record reading time and checkpoint scores.

Revision ID: 004
Revises: 003
Create Date: 2026-10-28 17:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "study_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lesson_id", sa.String(length=80), nullable=True),
        sa.Column("lesson_title", sa.String(length=200), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_study_events_owner_id", "study_events", ["owner_id"])
    op.create_index("ix_study_events_occurred_at", "study_events", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_study_events_occurred_at", table_name="study_events")
    op.drop_index("ix_study_events_owner_id", table_name="study_events")
    op.drop_table("study_events")
