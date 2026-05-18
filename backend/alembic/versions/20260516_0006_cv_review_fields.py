"""cv review fields

Revision ID: 20260516_0006
Revises: 20260516_0005
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260516_0006"
down_revision: Union[str, None] = "20260516_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cv_versions", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("cv_versions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("cv_versions", "reviewed_at")
    op.drop_column("cv_versions", "review_notes")
