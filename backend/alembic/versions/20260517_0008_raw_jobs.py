"""add raw_jobs table

Revision ID: 20260517_0008
Revises: 20260516_0007
Create Date: 2026-05-17 22:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260517_0008"
down_revision: Union[str, None] = "20260516_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_company_key", sa.String(length=255), nullable=False),
        sa.Column("external_job_id", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("job_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["normalized_job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "source_company_key",
            "external_job_id",
            name="uq_raw_jobs_source_company_external",
        ),
    )
    op.create_index(op.f("ix_raw_jobs_source"), "raw_jobs", ["source"], unique=False)
    op.create_index(op.f("ix_raw_jobs_source_company_key"), "raw_jobs", ["source_company_key"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_raw_jobs_source_company_key"), table_name="raw_jobs")
    op.drop_index(op.f("ix_raw_jobs_source"), table_name="raw_jobs")
    op.drop_table("raw_jobs")
