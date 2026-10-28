"""lesson versioning, question keys, and attempt truth"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Repair databases that already stored duplicate version numbers before the
    # constraint exists. Renumber only lesson groups that actually contain a
    # duplicate, preserving each group's chronological order.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   path_lesson_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY path_lesson_id
                       ORDER BY version_number, created_at, id
                   ) AS new_version
            FROM lesson_versions
        ),
        dupes AS (
            SELECT path_lesson_id
            FROM lesson_versions
            GROUP BY path_lesson_id
            HAVING COUNT(*) <> COUNT(DISTINCT version_number)
        )
        UPDATE lesson_versions AS lv
        SET version_number = ranked.new_version
        FROM ranked
        JOIN dupes ON dupes.path_lesson_id = ranked.path_lesson_id
        WHERE lv.id = ranked.id
        """
    )
    op.create_unique_constraint(
        "uq_lesson_version_number", "lesson_versions", ["path_lesson_id", "version_number"]
    )
    op.create_unique_constraint(
        "uq_question_key_per_version", "questions", ["lesson_version_id", "question_key"]
    )
    # `001` created a globally unique sync key, which lets one learner's retry
    # block another learner's identical client key. Scope it to the owner.
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("quiz_attempts"):
        if constraint.get("column_names") == ["sync_idempotency_key"]:
            op.drop_constraint(constraint["name"], "quiz_attempts", type_="unique")
    op.create_unique_constraint(
        "uq_quiz_attempt_owner_sync", "quiz_attempts", ["owner_id", "sync_idempotency_key"]
    )
    op.add_column(
        "quiz_attempts",
        sa.Column("attempt_kind", sa.String(20), nullable=False, server_default="practice"),
    )
    op.add_column(
        "concept_evidence",
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("concept_evidence", "hints_used")
    op.drop_column("quiz_attempts", "attempt_kind")
    op.drop_constraint("uq_quiz_attempt_owner_sync", "quiz_attempts", type_="unique")
    op.create_unique_constraint(
        "quiz_attempts_sync_idempotency_key_key", "quiz_attempts", ["sync_idempotency_key"]
    )
    op.drop_constraint("uq_question_key_per_version", "questions", type_="unique")
    op.drop_constraint("uq_lesson_version_number", "lesson_versions", type_="unique")
