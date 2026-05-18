"""message drafts

Revision ID: 20260516_0007
Revises: 20260516_0006
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260516_0007"
down_revision: Union[str, None] = "20260516_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    draft_type = postgresql.ENUM(
        "LINKEDIN",
        "APPLICATION_EMAIL",
        "SHORT_COVER_LETTER",
        "FOLLOW_UP",
        "RECRUITER_REPLY",
        name="message_draft_type",
        create_type=False,
    )
    draft_status = postgresql.ENUM(
        "DRAFT",
        "APPROVED",
        "REJECTED",
        name="message_draft_status",
        create_type=False,
    )
    postgresql.ENUM(
        "LINKEDIN",
        "APPLICATION_EMAIL",
        "SHORT_COVER_LETTER",
        "FOLLOW_UP",
        "RECRUITER_REPLY",
        name="message_draft_type",
    ).create(op.get_bind(), checkfirst=True)
    postgresql.ENUM("DRAFT", "APPROVED", "REJECTED", name="message_draft_status").create(
        op.get_bind(), checkfirst=True
    )

    op.create_table(
        "message_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("cv_version_id", sa.UUID(), nullable=True),
        sa.Column("draft_type", draft_type, nullable=False),
        sa.Column("status", draft_status, nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cv_version_id"], ["cv_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_drafts_job_id"), "message_drafts", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_message_drafts_job_id"), table_name="message_drafts")
    op.drop_table("message_drafts")
    postgresql.ENUM(name="message_draft_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="message_draft_type").drop(op.get_bind(), checkfirst=True)
