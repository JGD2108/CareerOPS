"""add gmail email tables

Revision ID: 20260517_0010
Revises: 20260517_0009
Create Date: 2026-05-17 23:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260517_0010"
down_revision: Union[str, None] = "20260517_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    email_category = postgresql.ENUM(
        "interview_invitation",
        "coding_assessment",
        "recruiter_follow_up",
        "rejection",
        "offer",
        "documents_requested",
        "form_pending",
        "other",
        name="email_category",
        create_type=False,
    )
    email_category.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "raw_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=False),
        sa.Column("history_id", sa.String(length=255), nullable=True),
        sa.Column("label_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gmail_message_id", name="uq_raw_emails_gmail_message_id"),
    )
    op.create_index(op.f("ix_raw_emails_gmail_message_id"), "raw_emails", ["gmail_message_id"], unique=False)
    op.create_index(op.f("ix_raw_emails_gmail_thread_id"), "raw_emails", ["gmail_thread_id"], unique=False)

    op.create_table(
        "emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_email_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("from_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("category", email_category, nullable=False),
        sa.Column("urgency", sa.String(length=50), nullable=False),
        sa.Column("requires_reply", sa.Boolean(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("gmail_draft_id", sa.String(length=255), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["raw_email_id"], ["raw_emails.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_email_id", name="uq_emails_raw_email_id"),
    )
    op.create_index(op.f("ix_emails_company_name"), "emails", ["company_name"], unique=False)
    op.create_index(op.f("ix_emails_from_email"), "emails", ["from_email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_emails_from_email"), table_name="emails")
    op.drop_index(op.f("ix_emails_company_name"), table_name="emails")
    op.drop_table("emails")
    op.drop_index(op.f("ix_raw_emails_gmail_thread_id"), table_name="raw_emails")
    op.drop_index(op.f("ix_raw_emails_gmail_message_id"), table_name="raw_emails")
    op.drop_table("raw_emails")
    sa.Enum(name="email_category").drop(op.get_bind(), checkfirst=True)
