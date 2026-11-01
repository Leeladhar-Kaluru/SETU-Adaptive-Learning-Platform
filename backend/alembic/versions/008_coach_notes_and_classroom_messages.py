"""coach note queue and classroom messaging"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("concept_id", sa.String(100), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("lease_owner", sa.String(100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_error_message", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_coach_notes_owner_concept_status", "coach_notes", ["owner_id", "concept_id", "status"])

    op.create_table(
        "classroom_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "classroom_id",
            UUID(as_uuid=True),
            sa.ForeignKey("classrooms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sender_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="group"),  # group | direct
        sa.Column("recipient_id", UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), index=True),
    )


def downgrade() -> None:
    op.drop_table("classroom_messages")
    op.drop_index("ix_coach_notes_owner_concept_status", table_name="coach_notes")
    op.drop_table("coach_notes")
