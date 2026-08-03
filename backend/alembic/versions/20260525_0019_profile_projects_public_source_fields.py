"""add profile project public-source fields

Revision ID: 20260525_0019
Revises: 20260522_0018
Create Date: 2026-05-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260525_0019"
down_revision = "20260522_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profile_projects", sa.Column("source_type", sa.Enum(name="source_type", create_type=False), nullable=True))
    op.add_column("profile_projects", sa.Column("project_url", sa.String(length=1000), nullable=True))
    op.add_column("profile_projects", sa.Column("repo_url", sa.String(length=1000), nullable=True))
    op.add_column("profile_projects", sa.Column("metric_bullets", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("profile_projects", "metric_bullets")
    op.drop_column("profile_projects", "repo_url")
    op.drop_column("profile_projects", "project_url")
    op.drop_column("profile_projects", "source_type")
