"""profile structured tables

Revision ID: 20260516_0002
Revises: 20260516_0001
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260516_0002"
down_revision: Union[str, None] = "20260516_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    evidence_level = postgresql.ENUM("STRONG", "MEDIUM", "WEAK", name="evidence_level", create_type=False)
    postgresql.ENUM("STRONG", "MEDIUM", "WEAK", name="evidence_level").create(op.get_bind(), checkfirst=True)

    op.create_table(
        "profile_skills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=True),
        sa.Column("evidence_level", evidence_level, nullable=False),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_profile_id", "name", "category", name="uq_profile_skill_name_category"),
    )
    op.create_index(op.f("ix_profile_skills_name"), "profile_skills", ["name"], unique=False)

    op.create_table(
        "profile_projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_projects_name"), "profile_projects", ["name"], unique=False)

    op.create_table(
        "profile_experience",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.String(length=100), nullable=True),
        sa.Column("end_date", sa.String(length=100), nullable=True),
        sa.Column("bullets", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_experience_company"), "profile_experience", ["company"], unique=False)

    op.create_table(
        "profile_education",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("degree", sa.String(length=500), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("dates", sa.String(length=255), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_education_institution"), "profile_education", ["institution"], unique=False)

    op.create_table(
        "profile_certifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_certifications_name"), "profile_certifications", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_profile_certifications_name"), table_name="profile_certifications")
    op.drop_table("profile_certifications")
    op.drop_index(op.f("ix_profile_education_institution"), table_name="profile_education")
    op.drop_table("profile_education")
    op.drop_index(op.f("ix_profile_experience_company"), table_name="profile_experience")
    op.drop_table("profile_experience")
    op.drop_index(op.f("ix_profile_projects_name"), table_name="profile_projects")
    op.drop_table("profile_projects")
    op.drop_index(op.f("ix_profile_skills_name"), table_name="profile_skills")
    op.drop_table("profile_skills")
    postgresql.ENUM(name="evidence_level").drop(op.get_bind(), checkfirst=True)
