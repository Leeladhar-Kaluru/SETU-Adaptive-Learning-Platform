"""remove seeded catalogue and academic profile defaults"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEEDED_RESOURCE_IDS = (
    "res-ncert-sci-9", "res-ncert-math-9", "res-ncert-sci-10",
    "res-cbse-6-sci-food", "res-cbse-6-math-num", "res-cbse-6-soc-hist",
    "res-cbse-6-eng-sun", "res-cbse-6-hin-vas",
    "res-cbse-7-sci-nutri", "res-cbse-7-math-frac", "res-cbse-7-soc-env",
    "res-cbse-7-eng-comb",
    "res-cbse-8-sci-crop", "res-cbse-8-math-linear", "res-cbse-8-soc-res",
    "res-cbse-8-eng-dew",
    "res-cbse-9-sci-matter", "res-cbse-9-math-geom", "res-cbse-9-soc-dem",
    "res-cbse-9-soc-eco", "res-cbse-9-it-comp",
    "res-cbse-10-sci-light", "res-cbse-10-math-quad", "res-cbse-10-math-trig",
    "res-cbse-10-soc-india", "res-cbse-10-it-ai",
)


def upgrade() -> None:
    ids = ", ".join(f"'{resource_id}'" for resource_id in SEEDED_RESOURCE_IDS)
    op.execute(f"UPDATE documents SET resource_id = NULL WHERE resource_id IN ({ids})")
    op.execute(f"DELETE FROM resource_rights WHERE resource_id IN ({ids})")
    op.execute(f"DELETE FROM resources WHERE id IN ({ids})")
    op.execute(
        "DELETE FROM resource_sources WHERE id = 'ncert-portal' "
        "AND NOT EXISTS (SELECT 1 FROM resources WHERE source_id = 'ncert-portal')"
    )
    op.alter_column("user_profiles", "board_id", server_default=None)
    op.alter_column(
        "user_profiles", "grade", existing_type=sa.Integer(),
        nullable=True, server_default=None,
    )
    op.alter_column(
        "user_profiles", "daily_goal_minutes", existing_type=sa.Integer(),
        nullable=True, server_default=None,
    )
    op.alter_column(
        "user_profiles", "preferred_language", existing_type=sa.String(20),
        nullable=True, server_default=None,
    )


def downgrade() -> None:
    op.alter_column("user_profiles", "board_id", server_default="board-cbse")
    op.execute("UPDATE user_profiles SET grade = 9 WHERE grade IS NULL")
    op.execute("UPDATE user_profiles SET daily_goal_minutes = 25 WHERE daily_goal_minutes IS NULL")
    op.execute("UPDATE user_profiles SET preferred_language = 'en-IN' WHERE preferred_language IS NULL")
    op.alter_column(
        "user_profiles", "grade", existing_type=sa.Integer(),
        nullable=False, server_default="9",
    )
    op.alter_column(
        "user_profiles", "daily_goal_minutes", existing_type=sa.Integer(),
        nullable=False, server_default="25",
    )
    op.alter_column(
        "user_profiles", "preferred_language", existing_type=sa.String(20),
        nullable=False, server_default="en-IN",
    )
