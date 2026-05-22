"""add job description resolution fields

Revision ID: 20260522_0018
Revises: 20260521_0017
Create Date: 2026-05-22 09:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260522_0018"
down_revision: Union[str, None] = "20260521_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("description_status", sa.String(length=50), nullable=False, server_default="missing"),
    )
    op.add_column(
        "jobs",
        sa.Column("description_quality", sa.String(length=50), nullable=False, server_default="unknown"),
    )
    op.add_column("jobs", sa.Column("description_source", sa.String(length=100), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("fetch_status", sa.String(length=50), nullable=False, server_default="pending"),
    )
    op.add_column("jobs", sa.Column("resolved_description", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("resolved_description_html", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("resolved_description_url", sa.String(length=1000), nullable=True))
    op.add_column("jobs", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("resolution_confidence", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("resolution_notes", sa.Text(), nullable=True))

    op.create_table(
        "job_description_resolution_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempted_source", sa.String(length=100), nullable=False),
        sa.Column("attempted_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("raw_response_ref", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_job_description_resolution_attempts_job_id"),
        "job_description_resolution_attempts",
        ["job_id"],
        unique=False,
    )

    op.alter_column("jobs", "description_status", server_default=None)
    op.alter_column("jobs", "description_quality", server_default=None)
    op.alter_column("jobs", "fetch_status", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_description_resolution_attempts_job_id"), table_name="job_description_resolution_attempts")
    op.drop_table("job_description_resolution_attempts")
    op.drop_column("jobs", "resolution_notes")
    op.drop_column("jobs", "resolution_confidence")
    op.drop_column("jobs", "resolved_at")
    op.drop_column("jobs", "resolved_description_url")
    op.drop_column("jobs", "resolved_description_html")
    op.drop_column("jobs", "resolved_description")
    op.drop_column("jobs", "fetch_status")
    op.drop_column("jobs", "description_source")
    op.drop_column("jobs", "description_quality")
    op.drop_column("jobs", "description_status")
