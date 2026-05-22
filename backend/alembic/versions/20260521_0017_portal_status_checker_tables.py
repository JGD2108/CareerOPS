"""add portal status checker tables

Revision ID: 20260521_0017
Revises: 20260520_0016
Create Date: 2026-05-21 00:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260521_0017"
down_revision: Union[str, None] = "20260520_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


agent_run_status = postgresql.ENUM("running", "succeeded", "failed", "partial", name="agent_run_status", create_type=False)
public_job_status = postgresql.ENUM(
    "OPEN",
    "CLOSED",
    "REMOVED",
    "REDIRECTED",
    "NO_LONGER_ACCEPTING_APPLICATIONS",
    "LOGIN_REQUIRED",
    "UNKNOWN",
    name="public_job_status",
    create_type=False,
)
portal_check_confidence = postgresql.ENUM(
    "low",
    "medium",
    "high",
    name="portal_check_confidence",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    agent_run_status.create(bind, checkfirst=True)
    public_job_status.create(bind, checkfirst=True)
    portal_check_confidence.create(bind, checkfirst=True)

    op.add_column("applications", sa.Column("latest_portal_status", sa.String(length=80), nullable=True))
    op.add_column("applications", sa.Column("latest_portal_confidence", sa.String(length=30), nullable=True))
    op.add_column("applications", sa.Column("latest_portal_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "applications",
        sa.Column("portal_login_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "applications",
        sa.Column("portal_user_action_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_type", sa.String(length=100), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("status", agent_run_status, nullable=False, server_default="running"),
        sa.Column("applications_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changes_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_agent_type"), "agent_runs", ["agent_type"], unique=False)

    op.create_table(
        "portal_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("portal_name", sa.String(length=255), nullable=False),
        sa.Column("portal_url", sa.String(length=1000), nullable=False),
        sa.Column("username", sa.String(length=320), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=255), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("daily_check_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "portal_url", "username", name="uq_portal_credentials_app_url_username"),
    )
    op.create_index(op.f("ix_portal_credentials_application_id"), "portal_credentials", ["application_id"], unique=False)
    op.create_index(op.f("ix_portal_credentials_company_id"), "portal_credentials", ["company_id"], unique=False)

    op.create_table(
        "application_status_check_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("previous_status", sa.String(length=80), nullable=True),
        sa.Column("new_status", sa.String(length=80), nullable=False, server_default="UNKNOWN"),
        sa.Column("public_job_status", public_job_status, nullable=False, server_default="UNKNOWN"),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("confidence", portal_check_confidence, nullable=False, server_default="low"),
        sa.Column("login_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("credentials_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_action_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_status_check_events_agent_run_id"),
        "application_status_check_events",
        ["agent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_status_check_events_application_id"),
        "application_status_check_events",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_status_check_events_checked_at"),
        "application_status_check_events",
        ["checked_at"],
        unique=False,
    )

    op.create_table(
        "model_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_usage_logs_agent_run_id"), "model_usage_logs", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_model_usage_logs_task_type"), "model_usage_logs", ["task_type"], unique=False)

    op.alter_column("applications", "portal_login_required", server_default=None)
    op.alter_column("applications", "portal_user_action_required", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_model_usage_logs_task_type"), table_name="model_usage_logs")
    op.drop_index(op.f("ix_model_usage_logs_agent_run_id"), table_name="model_usage_logs")
    op.drop_table("model_usage_logs")

    op.drop_index(op.f("ix_application_status_check_events_checked_at"), table_name="application_status_check_events")
    op.drop_index(op.f("ix_application_status_check_events_application_id"), table_name="application_status_check_events")
    op.drop_index(op.f("ix_application_status_check_events_agent_run_id"), table_name="application_status_check_events")
    op.drop_table("application_status_check_events")

    op.drop_index(op.f("ix_portal_credentials_company_id"), table_name="portal_credentials")
    op.drop_index(op.f("ix_portal_credentials_application_id"), table_name="portal_credentials")
    op.drop_table("portal_credentials")

    op.drop_index(op.f("ix_agent_runs_agent_type"), table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_column("applications", "portal_user_action_required")
    op.drop_column("applications", "portal_login_required")
    op.drop_column("applications", "latest_portal_checked_at")
    op.drop_column("applications", "latest_portal_confidence")
    op.drop_column("applications", "latest_portal_status")

    bind = op.get_bind()
    portal_check_confidence.drop(bind, checkfirst=True)
    public_job_status.drop(bind, checkfirst=True)
    agent_run_status.drop(bind, checkfirst=True)
