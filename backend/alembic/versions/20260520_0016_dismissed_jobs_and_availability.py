"""add dismissed jobs and availability fields

Revision ID: 20260520_0016
Revises: 20260518_0015
Create Date: 2026-05-20 10:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260520_0016"
down_revision: Union[str, None] = "20260518_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("availability_status", sa.String(length=50), nullable=False, server_default="unknown"),
    )
    op.add_column("jobs", sa.Column("availability_reason", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("availability_checked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "dismissed_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_company_key", sa.String(length=255), nullable=True),
        sa.Column("external_job_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index(op.f("ix_dismissed_jobs_fingerprint"), "dismissed_jobs", ["fingerprint"], unique=True)
    op.create_index(op.f("ix_dismissed_jobs_source"), "dismissed_jobs", ["source"], unique=False)

    op.alter_column("jobs", "availability_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_dismissed_jobs_source"), table_name="dismissed_jobs")
    op.drop_index(op.f("ix_dismissed_jobs_fingerprint"), table_name="dismissed_jobs")
    op.drop_table("dismissed_jobs")
    op.drop_column("jobs", "availability_checked_at")
    op.drop_column("jobs", "availability_reason")
    op.drop_column("jobs", "availability_status")
    op.drop_column("jobs", "application_deadline")
    op.drop_column("jobs", "posted_at")
