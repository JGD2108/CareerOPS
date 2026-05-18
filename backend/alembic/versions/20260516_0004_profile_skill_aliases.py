"""profile skill aliases

Revision ID: 20260516_0004
Revises: 20260516_0003
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260516_0004"
down_revision: Union[str, None] = "20260516_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_skill_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("profile_skill_id", sa.UUID(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_skill_id"], ["profile_skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias", name="uq_profile_skill_alias"),
    )
    op.create_index(op.f("ix_profile_skill_aliases_profile_skill_id"), "profile_skill_aliases", ["profile_skill_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_profile_skill_aliases_profile_skill_id"), table_name="profile_skill_aliases")
    op.drop_table("profile_skill_aliases")
