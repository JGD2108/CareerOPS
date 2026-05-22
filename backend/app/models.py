from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ApplicationStatus(StrEnum):
    FOUND = "Found"
    REVIEWED = "Reviewed"
    CV_GENERATED = "CV Generated"
    APPLIED = "Applied"
    RECRUITER_REPLIED = "Recruiter Replied"
    INTERVIEW = "Interview"
    ASSESSMENT = "Assessment"
    REJECTED = "Rejected"
    OFFER = "Offer"


class SourceType(StrEnum):
    CV = "cv"
    LINKEDIN = "linkedin"
    PORTFOLIO = "portfolio"
    GITHUB = "github"
    MANUAL = "manual"
    JOB_DESCRIPTION = "job_description"
    EMAIL = "email"
    OTHER = "other"


class EvidenceLevel(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class JobRecommendation(StrEnum):
    APPLY_NOW = "apply_now"
    REVIEW = "review"
    IGNORE = "ignore"


class CVVersionStatus(StrEnum):
    PLAN_DRAFT = "plan_draft"
    GENERATED = "generated"
    APPROVED = "approved"
    REJECTED = "rejected"


class MessageDraftType(StrEnum):
    LINKEDIN = "linkedin"
    APPLICATION_EMAIL = "application_email"
    SHORT_COVER_LETTER = "short_cover_letter"
    FOLLOW_UP = "follow_up"
    RECRUITER_REPLY = "recruiter_reply"


class MessageDraftStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class EmailCategory(StrEnum):
    JOB_ALERT = "job_alert"
    APPLICATION_CONFIRMATION = "application_confirmation"
    INTERVIEW_INVITATION = "interview_invitation"
    CODING_ASSESSMENT = "coding_assessment"
    RECRUITER_FOLLOW_UP = "recruiter_follow_up"
    REJECTION = "rejection"
    OFFER = "offer"
    DOCUMENTS_REQUESTED = "documents_requested"
    FORM_PENDING = "form_pending"
    OTHER = "other"


class ActionStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class ActionType(StrEnum):
    SUBMIT_APPLICATION = "submit_application"
    SEND_FOLLOW_UP = "send_follow_up"
    RESPOND_TO_RECRUITER = "respond_to_recruiter"
    SCHEDULE_INTERVIEW = "schedule_interview"
    PREPARE_INTERVIEW = "prepare_interview"
    COMPLETE_ASSESSMENT = "complete_assessment"
    SEND_DOCUMENTS = "send_documents"
    COMPLETE_FORM = "complete_form"
    REVIEW_OFFER = "review_offer"
    ARCHIVE_REJECTION = "archive_rejection"


class NotificationChannel(StrEnum):
    CONSOLE = "console"
    API = "api"
    EMAIL = "email"


class PublicJobStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REMOVED = "REMOVED"
    REDIRECTED = "REDIRECTED"
    NO_LONGER_ACCEPTING_APPLICATIONS = "NO_LONGER_ACCEPTING_APPLICATIONS"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    UNKNOWN = "UNKNOWN"


class PortalCheckConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    website_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")
    portal_credentials: Mapped[list["PortalCredential"]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(255))
    work_mode: Mapped[str | None] = mapped_column(String(100))
    seniority: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    availability_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    availability_reason: Mapped[str | None] = mapped_column(Text)
    availability_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description_status: Mapped[str] = mapped_column(String(50), nullable=False, default="missing")
    description_quality: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    description_source: Mapped[str | None] = mapped_column(String(100))
    fetch_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    resolved_description: Mapped[str | None] = mapped_column(Text)
    resolved_description_html: Mapped[str | None] = mapped_column(Text)
    resolved_description_url: Mapped[str | None] = mapped_column(String(1000))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_confidence: Mapped[float | None] = mapped_column(Float)
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company | None] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(back_populates="job")
    scores: Mapped[list["JobScore"]] = relationship(back_populates="job")
    cv_versions: Mapped[list["CVVersion"]] = relationship(back_populates="job")
    message_drafts: Mapped[list["MessageDraft"]] = relationship(back_populates="job")
    raw_jobs: Mapped[list["RawJob"]] = relationship(back_populates="normalized_job")
    description_resolution_attempts: Mapped[list["JobDescriptionResolutionAttempt"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )

    @property
    def source_trace(self) -> dict:
        trace = dict(self.raw_payload or {})
        if self.raw_jobs:
            raw_job = sorted(self.raw_jobs, key=lambda item: item.created_at, reverse=True)[0]
            raw_job_payload = raw_job.raw_payload or {}
            trace.update(raw_job_payload)
            trace.update(
                {
                    "raw_job_id": str(raw_job.id),
                    "raw_job_source": raw_job.source,
                    "raw_job_external_id": raw_job.external_job_id,
                    "raw_job_discovered_at": raw_job.discovered_at.isoformat() if raw_job.discovered_at else None,
                    "raw_job_payload": raw_job_payload,
                }
            )
        return trace


class RawJob(Base):
    __tablename__ = "raw_jobs"
    __table_args__ = (
        UniqueConstraint("source", "source_company_key", "external_job_id", name="uq_raw_jobs_source_company_external"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_company_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    job_url: Mapped[str | None] = mapped_column(String(1000))
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    normalized_job: Mapped[Job | None] = relationship(back_populates="raw_jobs")


class JobDescriptionResolutionAttempt(Base):
    __tablename__ = "job_description_resolution_attempts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    attempted_source: Mapped[str] = mapped_column(String(100), nullable=False)
    attempted_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    raw_response_ref: Mapped[str | None] = mapped_column(String(1000))
    error_message: Mapped[str | None] = mapped_column(Text)
    attempt_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="description_resolution_attempts")


class DismissedJob(Base):
    __tablename__ = "dismissed_jobs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_company_key: Mapped[str | None] = mapped_column(String(255))
    external_job_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    company_name: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscoverySource(Base):
    __tablename__ = "job_discovery_sources"
    __table_args__ = (
        UniqueConstraint("source", "company_key", name="uq_job_discovery_source_company_key"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    company_key: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name_override: Mapped[str | None] = mapped_column(String(255))
    role_keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    locations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    seniority_terms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    work_modes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    include_description: Mapped[bool] = mapped_column(nullable=False, default=True)
    create_applications: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DiscoveryRun(Base):
    __tablename__ = "job_discovery_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_jobs_saved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized_jobs_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applications_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deduplicated_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RawEmail(Base):
    __tablename__ = "raw_emails"
    __table_args__ = (
        UniqueConstraint("gmail_message_id", name="uq_raw_emails_gmail_message_id"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gmail_thread_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    history_id: Mapped[str | None] = mapped_column(String(255))
    label_ids: Mapped[list | None] = mapped_column(JSONB)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    normalized_email: Mapped["Email"] = relationship(back_populates="raw_email", uselist=False)


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("raw_email_id", name="uq_emails_raw_email_id"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    raw_email_id: Mapped[UUID] = mapped_column(ForeignKey("raw_emails.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"))
    company_name: Mapped[str | None] = mapped_column(String(255), index=True)
    from_name: Mapped[str | None] = mapped_column(String(255))
    from_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(500))
    snippet: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)
    category: Mapped[EmailCategory] = mapped_column(
        Enum(
            EmailCategory,
            name="email_category",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=EmailCategory.OTHER,
    )
    urgency: Mapped[str] = mapped_column(String(50), nullable=False, default="normal")
    requires_reply: Mapped[bool] = mapped_column(nullable=False, default=False)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    gmail_draft_id: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    raw_email: Mapped[RawEmail] = relationship(back_populates="normalized_email")
    application: Mapped[Application | None] = relationship(back_populates="emails")

    @property
    def gmail_message_id(self) -> str | None:
        return self.raw_email.gmail_message_id if self.raw_email else None

    @property
    def gmail_thread_id(self) -> str | None:
        return self.raw_email.gmail_thread_id if self.raw_email else None

    @property
    def gmail_history_id(self) -> str | None:
        return self.raw_email.history_id if self.raw_email else None

    @property
    def gmail_label_ids(self) -> list | None:
        return self.raw_email.label_ids if self.raw_email else None


class CandidateProfile(Base):
    __tablename__ = "candidate_profile"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    display_name: Mapped[str | None] = mapped_column(String(255))
    headline: Mapped[str | None] = mapped_column(String(500))
    location: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    preferences: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sources: Mapped[list["ProfileSource"]] = relationship(back_populates="candidate_profile")
    skills: Mapped[list["ProfileSkill"]] = relationship(back_populates="candidate_profile")
    projects: Mapped[list["ProfileProject"]] = relationship(back_populates="candidate_profile")
    experiences: Mapped[list["ProfileExperience"]] = relationship(back_populates="candidate_profile")
    education: Mapped[list["ProfileEducation"]] = relationship(back_populates="candidate_profile")
    certifications: Mapped[list["ProfileCertification"]] = relationship(back_populates="candidate_profile")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(128), index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    document_metadata: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile_sources: Mapped[list["ProfileSource"]] = relationship(back_populates="document")


class ProfileSource(Base):
    __tablename__ = "profile_sources"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="sources")
    document: Mapped[Document | None] = relationship(back_populates="profile_sources")


class ProfileSkill(Base):
    __tablename__ = "profile_skills"
    __table_args__ = (
        UniqueConstraint("candidate_profile_id", "name", "category", name="uq_profile_skill_name_category"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(255))
    evidence_level: Mapped[EvidenceLevel] = mapped_column(
        Enum(EvidenceLevel, name="evidence_level"), nullable=False
    )
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="skills")
    aliases: Mapped[list["ProfileSkillAlias"]] = relationship(back_populates="skill")


class ProfileSkillAlias(Base):
    __tablename__ = "profile_skill_aliases"
    __table_args__ = (UniqueConstraint("alias", name="uq_profile_skill_alias"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_skill_id: Mapped[UUID] = mapped_column(
        ForeignKey("profile_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped[ProfileSkill] = relationship(back_populates="aliases")


class ProfileProject(Base):
    __tablename__ = "profile_projects"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list | None] = mapped_column(JSONB)
    impact: Mapped[str | None] = mapped_column(Text)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="projects")


class ProfileExperience(Base):
    __tablename__ = "profile_experience"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[str | None] = mapped_column(String(100))
    end_date: Mapped[str | None] = mapped_column(String(100))
    bullets: Mapped[list | None] = mapped_column(JSONB)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="experiences")


class ProfileEducation(Base):
    __tablename__ = "profile_education"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    institution: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    degree: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    dates: Mapped[str | None] = mapped_column(String(255))
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="education")


class ProfileCertification(Base):
    __tablename__ = "profile_certifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    issuer: Mapped[str | None] = mapped_column(String(255))
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="certifications")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        nullable=False,
        default=ApplicationStatus.FOUND,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latest_portal_status: Mapped[str | None] = mapped_column(String(80))
    latest_portal_confidence: Mapped[str | None] = mapped_column(String(30))
    latest_portal_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portal_login_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    portal_user_action_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped[Job] = relationship(back_populates="applications")
    emails: Mapped[list[Email]] = relationship(back_populates="application")
    actions: Mapped[list["Action"]] = relationship(back_populates="application")
    portal_credentials: Mapped[list["PortalCredential"]] = relationship(back_populates="application")
    status_check_events: Mapped[list["ApplicationStatusCheckEvent"]] = relationship(back_populates="application")

    @property
    def job_title(self) -> str | None:
        return self.job.title if self.job else None

    @property
    def company_name(self) -> str | None:
        if not self.job or not self.job.company:
            return None
        return self.job.company.name

    @property
    def job_source(self) -> str | None:
        return self.job.source if self.job else None


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[JobRecommendation] = mapped_column(
        Enum(JobRecommendation, name="job_recommendation"), nullable=False
    )
    extracted_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False)
    matched_skills: Mapped[list] = mapped_column(JSONB, nullable=False)
    missing_or_weak_skills: Mapped[list] = mapped_column(JSONB, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    risks: Mapped[list] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="scores")
    candidate_profile: Mapped[CandidateProfile] = relationship()


class CVVersion(Base):
    __tablename__ = "cv_versions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    status: Mapped[CVVersionStatus] = mapped_column(Enum(CVVersionStatus, name="cv_version_status"), nullable=False)
    tailoring_plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changes: Mapped[list] = mapped_column(JSONB, nullable=False)
    generated_file_path: Mapped[str | None] = mapped_column(String(1000))
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="cv_versions")


class MessageDraft(Base):
    __tablename__ = "message_drafts"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_profile.id", ondelete="CASCADE"), nullable=False
    )
    cv_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("cv_versions.id", ondelete="SET NULL"))
    draft_type: Mapped[MessageDraftType] = mapped_column(
        Enum(MessageDraftType, name="message_draft_type"), nullable=False
    )
    status: Mapped[MessageDraftStatus] = mapped_column(
        Enum(MessageDraftStatus, name="message_draft_status"), nullable=False, default=MessageDraftStatus.DRAFT
    )
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(100), nullable=False, default="natural-professional")
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="english")
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)
    approval_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job: Mapped[Job] = relationship(back_populates="message_drafts")


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (UniqueConstraint("action_key", name="uq_actions_action_key"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    email_id: Mapped[UUID | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"))
    action_key: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[ActionType] = mapped_column(
        Enum(
            ActionType,
            name="action_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[ActionStatus] = mapped_column(
        Enum(
            ActionStatus,
            name="action_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ActionStatus.OPEN,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="normal")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="actions")
    email: Mapped[Email | None] = relationship()


class NotificationSummary(Base):
    __tablename__ = "notification_summaries"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    summary_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            name="notification_channel",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=NotificationChannel.API,
    )
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rendered_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            name="agent_run_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AgentRunStatus.RUNNING,
    )
    applications_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changes_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status_check_events: Mapped[list["ApplicationStatusCheckEvent"]] = relationship(back_populates="agent_run")
    model_usage_logs: Mapped[list["ModelUsageLog"]] = relationship(back_populates="agent_run")


class PortalCredential(Base):
    __tablename__ = "portal_credentials"
    __table_args__ = (
        UniqueConstraint("application_id", "portal_url", "username", name="uq_portal_credentials_app_url_username"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    portal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    portal_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    username: Mapped[str] = mapped_column(String(320), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_id: Mapped[str | None] = mapped_column(String(255))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_check_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="portal_credentials")
    company: Mapped[Company | None] = relationship(back_populates="portal_credentials")


class ApplicationStatusCheckEvent(Base):
    __tablename__ = "application_status_check_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    previous_status: Mapped[str | None] = mapped_column(String(80))
    new_status: Mapped[str] = mapped_column(String(80), nullable=False, default=PublicJobStatus.UNKNOWN.value)
    public_job_status: Mapped[PublicJobStatus] = mapped_column(
        Enum(
            PublicJobStatus,
            name="public_job_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PublicJobStatus.UNKNOWN,
    )
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[PortalCheckConfidence] = mapped_column(
        Enum(
            PortalCheckConfidence,
            name="portal_check_confidence",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PortalCheckConfidence.LOW,
    )
    login_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    credentials_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_action_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    application: Mapped[Application] = relationship(back_populates="status_check_events")
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="status_check_events")


class ModelUsageLog(Base):
    __tablename__ = "model_usage_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run: Mapped[AgentRun | None] = relationship(back_populates="model_usage_logs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    event_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
