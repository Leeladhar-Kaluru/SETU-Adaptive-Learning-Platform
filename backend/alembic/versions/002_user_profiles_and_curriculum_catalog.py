"""Add user_profiles table, classroom join_code, and complete Classes 6-10 curriculum catalog

Revision ID: 002
Revises: 001
Create Date: 2026-10-28 14:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create user_profiles table
    op.create_table(
        'user_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='student'),
        sa.Column('display_name', sa.String(150), nullable=False),
        sa.Column('preferred_language', sa.String(20), nullable=False, server_default='en-IN'),
        sa.Column('board_id', sa.String(50), sa.ForeignKey('curriculum_boards.id'), nullable=True, server_default='board-cbse'),
        sa.Column('grade', sa.Integer(), nullable=False, server_default='9'),
        sa.Column('subjects_interested', sa.JSON(), nullable=True),
        sa.Column('learning_goals', sa.JSON(), nullable=True),
        sa.Column('target_date', sa.DateTime(), nullable=True),
        sa.Column('daily_goal_minutes', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('accessibility_preferences', sa.JSON(), nullable=True),
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tour_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )
    op.create_index('ix_user_profiles_role', 'user_profiles', ['role'])
    op.create_index('ix_user_profiles_grade', 'user_profiles', ['grade'])

    # 2. Add join_code to classrooms
    op.add_column('classrooms', sa.Column('join_code', sa.String(15), nullable=True))
    op.create_index('ix_classrooms_join_code', 'classrooms', ['join_code'], unique=True)

    # Ensure subject-it exists
    op.execute(sa.text("""
        INSERT INTO subjects (id, code, canonical_name, active)
        VALUES ('subject-it', 'IT', 'Information Technology', true)
        ON CONFLICT (id) DO NOTHING;
    """))


def downgrade() -> None:
    op.drop_index('ix_classrooms_join_code', table_name='classrooms')
    op.drop_column('classrooms', 'join_code')
    op.drop_index('ix_user_profiles_grade', table_name='user_profiles')
    op.drop_index('ix_user_profiles_role', table_name='user_profiles')
    op.drop_table('user_profiles')
