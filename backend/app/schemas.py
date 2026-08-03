from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models import ApplicationStatus
from app.models import ActionStatus
from app.models import ActionType
from app.models import CVVersionStatus
from app.models import EmailCategory
from app.models import MessageDraftStatus
from app.models import MessageDraftType
from app.models import SourceType
from app.models import JobRecommendation
from app.models import NotificationChannel
from app.models import AgentRunStatus
from app.models import PortalCheckConfidence
from app.models import PublicJobStatus


class CompanyRead(BaseModel):
    id: UUID
    name: str
    website_url: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    company_name: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=20)
    source_url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=255)
    work_mode: str | None = Field(default=None, max_length=100)
    seniority: str | None = Field(default=None, max_length=100)
    source: str = Field(default="manual", max_length=100)
    posted_at: datetime | None = None
    application_deadline: datetime | None = None
    availability_status: str = Field(default="unknown", max_length=50)
    availability_reason: str | None = None


class JobRead(BaseModel):
    id: UUID
    title: str
    source: str
    source_url: str | None
    location: str | None
    work_mode: str | None
    seniority: str | None
    description: str
    posted_at: datetime | None
    application_deadline: datetime | None
    availability_status: str
    availability_reason: str | None
    availability_checked_at: datetime | None
    description_status: str
    description_quality: str
    description_source: str | None
    fetch_status: str
    resolved_description: str | None
    resolved_description_html: str | None
    resolved_description_url: str | None
    resolved_at: datetime | None
    resolution_confidence: float | None
    resolution_notes: str | None
    raw_payload: dict | None
    source_trace: dict | None
    company: CompanyRead | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationCreate(BaseModel):
    job_id: UUID
    status: ApplicationStatus = ApplicationStatus.FOUND
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None


class ApplicationMarkAppliedRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class ApplicationRead(BaseModel):
    id: UUID
    job_id: UUID
    status: ApplicationStatus
    job_title: str | None = None
    company_name: str | None = None
    job_source: str | None = None
    notes: str | None
    applied_at: datetime | None
    latest_portal_status: str | None = None
    latest_portal_confidence: str | None = None
    latest_portal_checked_at: datetime | None = None
    portal_login_required: bool = False
    portal_user_action_required: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthStatusRead(BaseModel):
    enabled: bool
    configured: bool
    authenticated: bool
    mode: str


class AuthLoginRequest(BaseModel):
    app_key: str


class PortalCredentialCreate(BaseModel):
    portal_name: str = Field(min_length=2, max_length=255)
    portal_url: HttpUrl
    username: str = Field(min_length=2, max_length=320)
    password: str = Field(min_length=1, max_length=500)
    mfa_enabled: bool = False
    daily_check_allowed: bool = False


class PortalCredentialUpdate(BaseModel):
    portal_name: str | None = Field(default=None, min_length=2, max_length=255)
    portal_url: HttpUrl | None = None
    username: str | None = Field(default=None, min_length=2, max_length=320)
    password: str | None = Field(default=None, min_length=1, max_length=500)
    mfa_enabled: bool | None = None
    daily_check_allowed: bool | None = None


class PortalCredentialRead(BaseModel):
    id: UUID
    application_id: UUID
    company_id: UUID | None
    portal_name: str
    portal_url: str
    username: str
    mfa_enabled: bool
    daily_check_allowed: bool
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(BaseModel):
    id: UUID
    agent_type: str
    trigger_type: str
    status: AgentRunStatus
    applications_checked: int
    changes_detected: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ApplicationStatusCheckEventRead(BaseModel):
    id: UUID
    application_id: UUID
    agent_run_id: UUID | None
    source_url: str | None
    previous_status: str | None
    new_status: str
    public_job_status: PublicJobStatus
    evidence_summary: str | None
    confidence: PortalCheckConfidence
    login_required: bool
    credentials_used: bool
    user_action_required: bool
    event_metadata: dict | None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelUsageLogRead(BaseModel):
    id: UUID
    agent_run_id: UUID | None
    task_type: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    id: UUID
    source_type: SourceType
    original_filename: str
    storage_path: str
    content_type: str | None
    checksum: str | None
    extracted_text: str | None
    document_metadata: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocalDocumentImportRequest(BaseModel):
    source_type: SourceType
    local_path: str = Field(min_length=3, max_length=2000)


class ProfileSkillRead(BaseModel):
    id: UUID
    name: str
    category: str | None
    evidence_level: str
    evidence_text: str

    model_config = ConfigDict(from_attributes=True)


class ProfileSkillAliasRead(BaseModel):
    id: UUID
    alias: str
    rationale: str
    skill_name: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceLookupRequest(BaseModel):
    claim: str = Field(min_length=2, max_length=500)


class EvidenceLookupResponse(BaseModel):
    claim: str
    is_supported: bool
    matches: list


class ProfileProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    technologies: list | None
    impact: str | None
    project_url: str | None = None
    repo_url: str | None = None
    metric_bullets: list[str] | None = None
    source_type: str | None = None
    source_document_id: UUID | None = None
    evidence_text: str

    model_config = ConfigDict(from_attributes=True)


class ProfileProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    technologies: list[str] = []
    impact: str | None = Field(default=None, max_length=2000)
    project_url: str | None = Field(default=None, max_length=1000)
    repo_url: str | None = Field(default=None, max_length=1000)
    metric_bullets: list[str] = []
    evidence_text: str | None = Field(default=None, max_length=4000)


class ProfileProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    technologies: list[str] | None = None
    impact: str | None = Field(default=None, max_length=2000)
    project_url: str | None = Field(default=None, max_length=1000)
    repo_url: str | None = Field(default=None, max_length=1000)
    metric_bullets: list[str] | None = None
    evidence_text: str | None = Field(default=None, max_length=4000)


class ProfileExperienceRead(BaseModel):
    id: UUID
    company: str
    title: str
    location: str | None
    start_date: str | None
    end_date: str | None
    bullets: list | None
    evidence_text: str

    model_config = ConfigDict(from_attributes=True)


class ProfileEducationRead(BaseModel):
    id: UUID
    institution: str
    degree: str
    location: str | None
    dates: str | None
    evidence_text: str

    model_config = ConfigDict(from_attributes=True)


class ProfileCertificationRead(BaseModel):
    id: UUID
    name: str
    issuer: str | None
    evidence_text: str

    model_config = ConfigDict(from_attributes=True)


class CandidateProfileRead(BaseModel):
    id: UUID
    display_name: str | None
    headline: str | None
    location: str | None
    summary: str | None
    preferences: dict | None
    skills: list[ProfileSkillRead] = []
    projects: list[ProfileProjectRead] = []
    experiences: list[ProfileExperienceRead] = []
    education: list[ProfileEducationRead] = []
    certifications: list[ProfileCertificationRead] = []

    model_config = ConfigDict(from_attributes=True)


class ProfileAgentRunRequest(BaseModel):
    document_id: UUID


class PublicSourcePreferencesPatchRequest(BaseModel):
    github_profile_url: str | None = None
    portfolio_urls: list[str] = []


class PublicSourcePreferencesRead(BaseModel):
    github_profile_url: str | None = None
    portfolio_urls: list[str] = []


class SourceIngestionFailureRead(BaseModel):
    source_type: str
    source_url: str
    reason: str


class PublicSourceEnrichmentResponse(BaseModel):
    profile: CandidateProfileRead
    projects_added: int
    projects_updated: int
    failures: list[SourceIngestionFailureRead] = []


class EmailAgentBatchRequest(BaseModel):
    limit: int = Field(default=15, ge=1, le=100)


class JobScoreRead(BaseModel):
    id: UUID
    job_id: UUID
    candidate_profile_id: UUID
    score: int
    recommendation: JobRecommendation
    extracted_requirements: dict
    matched_skills: list
    missing_or_weak_skills: list
    reasons: list
    risks: list
    evidence: list
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobFitAnalyzeRequest(JobCreate):
    create_application: bool = False


class JobFitAnalyzeResponse(BaseModel):
    job: JobRead
    score: JobScoreRead
    application: ApplicationRead | None = None

    model_config = ConfigDict(from_attributes=True)


class JobScoreRequest(BaseModel):
    preliminary: bool = False


class JobDescriptionIngestRequest(BaseModel):
    description: str = Field(min_length=20)
    title: str | None = Field(default=None, min_length=2, max_length=255)
    company_name: str | None = Field(default=None, min_length=2, max_length=255)
    source_url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=255)
    work_mode: str | None = Field(default=None, max_length=100)
    seniority: str | None = Field(default=None, max_length=100)
    create_application: bool = True


class JobDescriptionUpdateRequest(BaseModel):
    description: str = Field(min_length=20)
    title: str | None = Field(default=None, min_length=2, max_length=255)
    company_name: str | None = Field(default=None, min_length=2, max_length=255)
    source_url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=255)
    work_mode: str | None = Field(default=None, max_length=100)
    seniority: str | None = Field(default=None, max_length=100)
    rescore: bool = True


class ManualJobDescriptionRequest(BaseModel):
    description: str = Field(min_length=20)
    source_url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ManualJobUrlRequest(BaseModel):
    url: HttpUrl


class JobDescriptionResolutionAttemptRead(BaseModel):
    id: UUID
    job_id: UUID
    attempted_source: str
    attempted_url: str | None
    status: str
    confidence: float | None
    reason: str | None
    raw_response_ref: str | None
    error_message: str | None
    metadata: dict | None = Field(default=None, validation_alias="attempt_metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManualJobDescriptionResponse(BaseModel):
    job: JobRead
    attempt: JobDescriptionResolutionAttemptRead

    model_config = ConfigDict(from_attributes=True)


class JobDescriptionResolveResponse(BaseModel):
    job_id: UUID
    status: str
    description_status: str
    description_source: str | None
    description_quality: str
    resolved_description_url: str | None
    confidence: float | None
    notes: str
    attempts: list[JobDescriptionResolutionAttemptRead] = []

    model_config = ConfigDict(from_attributes=True)


class ResolvePendingDescriptionsResponse(BaseModel):
    processed_count: int
    resolved_count: int
    needs_manual_review_count: int
    not_found_count: int
    error_count: int
    results: list[dict] = []


class JobDescriptionIngestResponse(BaseModel):
    job: JobRead
    score: JobScoreRead | None = None
    application: ApplicationRead | None = None
    reply_info: str

    model_config = ConfigDict(from_attributes=True)


class CVTailoringPlanRead(BaseModel):
    id: UUID
    job_id: UUID
    candidate_profile_id: UUID
    source_document_id: UUID | None
    status: CVVersionStatus
    tailoring_plan: dict
    changes: list
    generated_file_path: str | None
    review_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CVVersionReviewRequest(BaseModel):
    status: CVVersionStatus
    review_notes: str | None = Field(default=None, max_length=2000)


class MessageDraftGenerateRequest(BaseModel):
    draft_types: list[MessageDraftType] = [
        MessageDraftType.LINKEDIN,
        MessageDraftType.APPLICATION_EMAIL,
        MessageDraftType.SHORT_COVER_LETTER,
    ]
    tone: str = Field(default="natural-professional", max_length=100)
    language: str = Field(default="english", max_length=50)


class MessageDraftRead(BaseModel):
    id: UUID
    job_id: UUID
    candidate_profile_id: UUID
    cv_version_id: UUID | None
    draft_type: MessageDraftType
    status: MessageDraftStatus
    subject: str | None
    body: str
    tone: str
    language: str
    evidence: list
    approval_required: bool
    review_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageDraftReviewRequest(BaseModel):
    status: MessageDraftStatus
    review_notes: str | None = Field(default=None, max_length=2000)


class ApplicationTrackerRead(BaseModel):
    application_id: UUID
    job_id: UUID
    status: ApplicationStatus
    job_title: str | None
    company_name: str | None
    artifact_state: dict
    ready_to_apply: bool
    current_action: str
    next_steps: list[str]
    notes: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RawJobRead(BaseModel):
    id: UUID
    source: str
    source_company_key: str
    external_job_id: str
    company_name: str
    title: str
    location: str | None
    job_url: str | None
    raw_payload: dict
    normalized_job_id: UUID | None
    discovered_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobDiscoverySourceConfig(BaseModel):
    source: str = Field(min_length=2, max_length=50)
    company_key: str = Field(min_length=2, max_length=255)
    company_name_override: str | None = Field(default=None, max_length=255)


class JobDiscoveryFilters(BaseModel):
    role_keywords: list[str] = []
    locations: list[str] = []
    seniority_terms: list[str] = []
    work_modes: list[str] = []


class JobDiscoveryRequest(BaseModel):
    sources: list[JobDiscoverySourceConfig]
    filters: JobDiscoveryFilters = JobDiscoveryFilters()
    include_description: bool = True
    create_applications: bool = False


class JobDiscoveryResponse(BaseModel):
    raw_jobs_saved: int
    normalized_jobs_created: int
    applications_created: int
    deduplicated_jobs: int
    auto_scored_jobs: int = 0
    matched_jobs: list[JobRead]


class DiscoverySourceCreate(BaseModel):
    source: str = Field(min_length=2, max_length=50)
    company_key: str = Field(min_length=2, max_length=255)
    company_name_override: str | None = Field(default=None, max_length=255)
    role_keywords: list[str] = []
    locations: list[str] = []
    seniority_terms: list[str] = []
    work_modes: list[str] = []
    include_description: bool = True
    create_applications: bool = False
    is_active: bool = True


class DiscoverySourceUpdate(BaseModel):
    company_name_override: str | None = Field(default=None, max_length=255)
    role_keywords: list[str] | None = None
    locations: list[str] | None = None
    seniority_terms: list[str] | None = None
    work_modes: list[str] | None = None
    include_description: bool | None = None
    create_applications: bool | None = None
    is_active: bool | None = None


class DiscoverySourceRead(BaseModel):
    id: UUID
    source: str
    company_key: str
    company_name_override: str | None
    role_keywords: list[str]
    locations: list[str]
    seniority_terms: list[str]
    work_modes: list[str]
    include_description: bool
    create_applications: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscoveryRunRead(BaseModel):
    id: UUID
    trigger_type: str
    status: str
    source_count: int
    raw_jobs_saved: int
    normalized_jobs_created: int
    applications_created: int
    deduplicated_jobs: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SchedulerStatusRead(BaseModel):
    enabled: bool
    running: bool
    timezone: str
    schedule_hour: int
    schedule_minute: int
    active_source_count: int


class EmbeddingRebuildRequest(BaseModel):
    include_jobs: bool = False
    job_limit: int = Field(default=100, ge=1, le=500)


class EmbeddingRebuildResponse(BaseModel):
    created_or_updated: int
    skipped: int
    total_sources: int


class SemanticMatchRead(BaseModel):
    source_table: str
    source_id: UUID
    content: str
    metadata: dict
    similarity: float


class GmailStatusRead(BaseModel):
    oauth_configured: bool
    credentials_file_exists: bool
    token_file_exists: bool
    authenticated: bool
    scopes: list[str]
    credentials_path: str
    token_path: str


class GmailSyncRequest(BaseModel):
    query: str = Field(default="category:primary newer_than:30d", max_length=500)
    max_results: int = Field(default=25, ge=1, le=100)
    skip_existing: bool = True


class LinkedInSyncRequest(BaseModel):
    newer_than_days: int = Field(default=90, ge=1, le=365)
    max_results: int = Field(default=50, ge=1, le=200)


class LinkedInSyncResponse(BaseModel):
    emails_synced: int
    emails_reclassified: int
    job_alerts: int
    application_confirmations: int
    jobs_imported: int
    applications_created: int
    applications_marked_applied: int
    jobs_auto_scored: int = 0


class MockEmailIngestRequest(BaseModel):
    from_header: str = Field(min_length=3, max_length=500)
    subject: str = Field(min_length=1, max_length=500)
    body_text: str = Field(min_length=1)
    snippet: str | None = Field(default=None, max_length=1000)


class EmailDraftCreateRequest(BaseModel):
    create_gmail_draft: bool = False


class EmailLinkRequest(BaseModel):
    application_id: UUID | None = None
    sync_next_actions: bool = True


class RawEmailRead(BaseModel):
    id: UUID
    gmail_message_id: str
    gmail_thread_id: str
    history_id: str | None
    label_ids: list | None
    raw_payload: dict
    synced_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailRead(BaseModel):
    id: UUID
    raw_email_id: UUID
    gmail_message_id: str | None
    gmail_thread_id: str | None
    gmail_history_id: str | None
    gmail_label_ids: list | None
    application_id: UUID | None
    company_name: str | None
    from_name: str | None
    from_email: str
    subject: str | None
    snippet: str | None
    body_text: str | None
    category: EmailCategory
    urgency: str
    requires_reply: bool
    suggested_action: str | None
    gmail_draft_id: str | None
    received_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionRead(BaseModel):
    id: UUID
    application_id: UUID
    email_id: UUID | None
    action_key: str
    action_type: ActionType
    status: ActionStatus
    title: str
    details: str | None
    priority: str
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionCreateRequest(BaseModel):
    action_type: ActionType = ActionType.SEND_FOLLOW_UP
    title: str = Field(min_length=2, max_length=255)
    details: str | None = Field(default=None, max_length=2000)
    priority: str = Field(default="normal", max_length=50)
    due_at: datetime | None = None


class ActionUpdateRequest(BaseModel):
    status: ActionStatus
    notes: str | None = Field(default=None, max_length=2000)


class NextActionSyncResponse(BaseModel):
    application_id: UUID
    status: ApplicationStatus
    actions: list[ActionRead]


class NotificationSummaryRead(BaseModel):
    id: UUID
    summary_date: datetime
    channel: NotificationChannel
    content: dict
    rendered_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
