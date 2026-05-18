"""job scores

Revision ID: 20260516_0003
Revises: 20260516_0002
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260516_0003"
down_revision: Union[str, None] = "20260516_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    recommendation = postgresql.ENUM("APPLY_NOW", "REVIEW", "IGNORE", name="job_recommendation", create_type=False)
    postgresql.ENUM("APPLY_NOW", "REVIEW", "IGNORE", name="job_recommendation").create(
        op.get_bind(), checkfirst=True
    )

    op.create_table(
        "job_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("recommendation", recommendation, nullable=False),
        sa.Column("extracted_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matched_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_or_weak_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_scores_job_id"), "job_scores", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_scores_job_id"), table_name="job_scores")
    op.drop_table("job_scores")
    postgresql.ENUM(name="job_recommendation").drop(op.get_bind(), checkfirst=True)
