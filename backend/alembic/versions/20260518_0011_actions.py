"""add actions table

Revision ID: 20260518_0011
Revises: 20260517_0010
Create Date: 2026-05-18 00:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260518_0011"
down_revision: Union[str, None] = "20260517_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    action_status = postgresql.ENUM(
        "open",
        "completed",
        "dismissed",
        name="action_status",
        create_type=False,
    )
    action_status.create(op.get_bind(), checkfirst=True)

    action_type = postgresql.ENUM(
        "submit_application",
        "send_follow_up",
        "respond_to_recruiter",
        "schedule_interview",
        "prepare_interview",
        "complete_assessment",
        "send_documents",
        "complete_form",
        "review_offer",
        "archive_rejection",
        name="action_type",
        create_type=False,
    )
    action_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_key", sa.String(length=255), nullable=False),
        sa.Column("action_type", action_type, nullable=False),
        sa.Column("status", action_status, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_key", name="uq_actions_action_key"),
    )
    op.create_index(op.f("ix_actions_application_id"), "actions", ["application_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_actions_application_id"), table_name="actions")
    op.drop_table("actions")
    postgresql.ENUM(name="action_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="action_status").drop(op.get_bind(), checkfirst=True)
