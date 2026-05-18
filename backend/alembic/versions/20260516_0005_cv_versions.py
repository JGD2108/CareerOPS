"""cv versions

Revision ID: 20260516_0005
Revises: 20260516_0004
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260516_0005"
down_revision: Union[str, None] = "20260516_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status = postgresql.ENUM("PLAN_DRAFT", "GENERATED", "APPROVED", "REJECTED", name="cv_version_status", create_type=False)
    postgresql.ENUM("PLAN_DRAFT", "GENERATED", "APPROVED", "REJECTED", name="cv_version_status").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "cv_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("status", status, nullable=False),
        sa.Column("tailoring_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_file_path", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cv_versions_job_id"), "cv_versions", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cv_versions_job_id"), table_name="cv_versions")
    op.drop_table("cv_versions")
    postgresql.ENUM(name="cv_version_status").drop(op.get_bind(), checkfirst=True)
