"""add notification summaries table

Revision ID: 20260518_0012
Revises: 20260518_0011
Create Date: 2026-05-18 00:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260518_0012"
down_revision: Union[str, None] = "20260518_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    notification_channel = postgresql.ENUM(
        "console",
        "api",
        "email",
        name="notification_channel",
        create_type=False,
    )
    notification_channel.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notification_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_summaries_summary_date"), "notification_summaries", ["summary_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_summaries_summary_date"), table_name="notification_summaries")
    op.drop_table("notification_summaries")
    postgresql.ENUM(name="notification_channel").drop(op.get_bind(), checkfirst=True)
