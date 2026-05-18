"""add discovery source and run tables

Revision ID: 20260517_0009
Revises: 20260517_0008
Create Date: 2026-05-17 23:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260517_0009"
down_revision: Union[str, None] = "20260517_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_discovery_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("company_key", sa.String(length=255), nullable=False),
        sa.Column("company_name_override", sa.String(length=255), nullable=True),
        sa.Column("role_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("seniority_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("work_modes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("include_description", sa.Boolean(), nullable=False),
        sa.Column("create_applications", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "company_key", name="uq_job_discovery_source_company_key"),
    )
    op.create_index(op.f("ix_job_discovery_sources_source"), "job_discovery_sources", ["source"], unique=False)

    op.create_table(
        "job_discovery_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("raw_jobs_saved", sa.Integer(), nullable=False),
        sa.Column("normalized_jobs_created", sa.Integer(), nullable=False),
        sa.Column("applications_created", sa.Integer(), nullable=False),
        sa.Column("deduplicated_jobs", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_discovery_runs_status"), "job_discovery_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_discovery_runs_status"), table_name="job_discovery_runs")
    op.drop_table("job_discovery_runs")
    op.drop_index(op.f("ix_job_discovery_sources_source"), table_name="job_discovery_sources")
    op.drop_table("job_discovery_sources")
