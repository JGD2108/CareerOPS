from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import crud
from app.auth import auth_status, require_app_auth
from app.config import get_settings
from app.application_tracker import (
    build_application_summary,
    get_application,
    list_application_artifact_state,
    mark_application_applied,
    sync_application_status,
)
from app.cv_tailoring import (
    create_tailoring_plan,
    generate_final_latex_from_plan,
    generate_latex_preview,
    get_cv_artifact_path,
    list_tailoring_plans,
    review_cv_version,
)
from app.discovery_scheduler import scheduler_status
from app.documents import list_documents as list_stored_documents
from app.documents import store_local_document, store_uploaded_document
from app.db import get_db
from app.gmail_integration import (
    authenticate_gmail,
    complete_gmail_web_oauth,
    create_reply_draft,
    gmail_status,
    link_email_to_application,
    list_emails,
    list_raw_emails,
    mock_ingest_email,
    reclassify_stored_emails,
    sync_linkedin_activity,
    sync_gmail_messages,
    start_gmail_web_oauth,
)
from app.next_action_agent import list_actions, list_application_actions, sync_next_actions, update_action_status
from app.notification_agent import generate_daily_summary, list_notification_summaries
from app.semantic_embeddings import ensure_job_embedding, rebuild_semantic_embeddings, semantic_matches_for_job
from app.job_discovery import (
    create_discovery_source,
    discover_jobs,
    list_discovery_runs,
    list_discovery_sources,
    list_raw_jobs,
    run_saved_discovery_sources,
    update_discovery_source,
)
from app.job_fit import list_job_scores, score_job_fit
from app.job_fit_service import analyze_manual_job
from app.knowledge_base import find_evidence_for_claim, list_skill_aliases, rebuild_skill_aliases
from app.langgraph_agents import run_email_triage_agent, run_profile_ingestion_agent, run_recent_unlinked_email_triage_agent
from app.message_agent import generate_message_drafts, list_message_drafts, review_message_draft
from app.models import SourceType
from app.models import ActionStatus
from app.profile_ingestion import extract_profile_from_latest_cv, get_profile
from app.schemas import (
    ApplicationCreate,
    ApplicationMarkAppliedRequest,
    ApplicationRead,
    ApplicationTrackerRead,
    ApplicationUpdate,
    ActionRead,
    ActionUpdateRequest,
    CandidateProfileRead,
    CVTailoringPlanRead,
    CVVersionReviewRequest,
    DiscoveryRunRead,
    DiscoverySourceCreate,
    DiscoverySourceRead,
    DiscoverySourceUpdate,
    DocumentRead,
    EmailAgentBatchRequest,
    EmailDraftCreateRequest,
    EmailLinkRequest,
    EmbeddingRebuildRequest,
    EmbeddingRebuildResponse,
    EmailRead,
    EvidenceLookupRequest,
    EvidenceLookupResponse,
    GmailStatusRead,
    GmailSyncRequest,
    JobCreate,
    JobFitAnalyzeRequest,
    JobFitAnalyzeResponse,
    JobDiscoveryRequest,
    JobDiscoveryResponse,
    JobRead,
    JobScoreRead,
    LinkedInSyncRequest,
    LinkedInSyncResponse,
    LocalDocumentImportRequest,
    MessageDraftGenerateRequest,
    MessageDraftRead,
    MessageDraftReviewRequest,
    MockEmailIngestRequest,
    NextActionSyncResponse,
    NotificationSummaryRead,
    ProfileAgentRunRequest,
    ProfileSkillAliasRead,
    RawEmailRead,
    RawJobRead,
    SchedulerStatusRead,
    SemanticMatchRead,
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_app_auth)])


@router.get("/auth/status")
def read_auth_status() -> dict[str, bool]:
    return auth_status()


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobRead:
    return crud.create_job(db, payload)


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(db: Session = Depends(get_db)) -> list[JobRead]:
    return crud.list_jobs(db)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: UUID, db: Session = Depends(get_db)) -> JobRead:
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> ApplicationRead:
    application = crud.create_application(db, payload)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return application


@router.get("/applications", response_model=list[ApplicationRead])
def list_applications(db: Session = Depends(get_db)) -> list[ApplicationRead]:
    return crud.list_applications(db)


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: UUID,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
) -> ApplicationRead:
    application = crud.update_application(db, application_id, payload)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.get("/applications/{application_id}", response_model=ApplicationTrackerRead)
def get_application_tracker(application_id: UUID, db: Session = Depends(get_db)) -> ApplicationTrackerRead:
    application = get_application(db, application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    artifact_state = list_application_artifact_state(db, application.job_id)
    return build_application_summary(application, artifact_state)


@router.post("/applications/{application_id}/sync", response_model=ApplicationTrackerRead)
def sync_application(application_id: UUID, db: Session = Depends(get_db)) -> ApplicationTrackerRead:
    application = sync_application_status(db, application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    artifact_state = list_application_artifact_state(db, application.job_id)
    return build_application_summary(application, artifact_state)


@router.patch("/applications/{application_id}/mark-applied", response_model=ApplicationTrackerRead)
def mark_applied(
    application_id: UUID,
    payload: ApplicationMarkAppliedRequest,
    db: Session = Depends(get_db),
) -> ApplicationTrackerRead:
    application = mark_application_applied(db, application_id, notes=payload.notes)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    artifact_state = list_application_artifact_state(db, application.job_id)
    return build_application_summary(application, artifact_state)


@router.post("/documents/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    source_type: SourceType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentRead:
    return await store_uploaded_document(db, file=file, source_type=source_type)


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentRead]:
    return list_stored_documents(db)


@router.post("/documents/import-local", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def import_local_document(payload: LocalDocumentImportRequest, db: Session = Depends(get_db)) -> DocumentRead:
    try:
        return store_local_document(db, source_type=payload.source_type, local_path=payload.local_path)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/profile/extract", response_model=CandidateProfileRead)
def extract_profile(db: Session = Depends(get_db)) -> CandidateProfileRead:
    try:
        profile = extract_profile_from_latest_cv(db)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return profile


@router.post("/agents/profile/run", response_model=CandidateProfileRead)
def run_profile_agent(payload: ProfileAgentRunRequest, db: Session = Depends(get_db)) -> CandidateProfileRead:
    try:
        return run_profile_ingestion_agent(db, document_id=payload.document_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/profile", response_model=CandidateProfileRead | None)
def read_profile(db: Session = Depends(get_db)) -> CandidateProfileRead | None:
    profile = get_profile(db)
    if not profile:
        return None
    return profile


@router.post("/jobs/{job_id}/score", response_model=JobScoreRead)
def score_job(job_id: UUID, db: Session = Depends(get_db)) -> JobScoreRead:
    job_score = score_job_fit(db, job_id)
    if not job_score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job or candidate profile not found. Create a job and extract the profile first.",
        )
    return job_score


@router.get("/jobs/{job_id}/scores", response_model=list[JobScoreRead])
def read_job_scores(job_id: UUID, db: Session = Depends(get_db)) -> list[JobScoreRead]:
    return list_job_scores(db, job_id)


@router.post("/job-fit/analyze", response_model=JobFitAnalyzeResponse, status_code=status.HTTP_201_CREATED)
def analyze_job_fit(payload: JobFitAnalyzeRequest, db: Session = Depends(get_db)) -> JobFitAnalyzeResponse:
    result = analyze_manual_job(db, payload)
    if not result["score"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found. Extract the profile before analyzing jobs.",
        )
    return result


@router.post("/job-discovery/discover", response_model=JobDiscoveryResponse, status_code=status.HTTP_201_CREATED)
def run_job_discovery(payload: JobDiscoveryRequest, db: Session = Depends(get_db)) -> JobDiscoveryResponse:
    try:
        return discover_jobs(
            db,
            sources=payload.sources,
            filters=payload.filters,
            include_description=payload.include_description,
            create_applications=payload.create_applications,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Job discovery failed: {error}") from error


@router.get("/raw-jobs", response_model=list[RawJobRead])
def read_raw_jobs(db: Session = Depends(get_db)) -> list[RawJobRead]:
    return list_raw_jobs(db)


@router.post("/discovery-sources", response_model=DiscoverySourceRead, status_code=status.HTTP_201_CREATED)
def create_saved_discovery_source(payload: DiscoverySourceCreate, db: Session = Depends(get_db)) -> DiscoverySourceRead:
    try:
        return create_discovery_source(db, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/discovery-sources", response_model=list[DiscoverySourceRead])
def read_discovery_sources(db: Session = Depends(get_db)) -> list[DiscoverySourceRead]:
    return list_discovery_sources(db)


@router.patch("/discovery-sources/{source_id}", response_model=DiscoverySourceRead)
def patch_discovery_source(
    source_id: UUID,
    payload: DiscoverySourceUpdate,
    db: Session = Depends(get_db),
) -> DiscoverySourceRead:
    source = update_discovery_source(db, source_id, payload)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery source not found")
    return source


@router.post("/job-discovery/run-saved", response_model=JobDiscoveryResponse, status_code=status.HTTP_201_CREATED)
def run_saved_job_discovery(db: Session = Depends(get_db)) -> JobDiscoveryResponse:
    try:
        return run_saved_discovery_sources(db, trigger_type="manual")
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Saved discovery run failed: {error}") from error


@router.get("/job-discovery/runs", response_model=list[DiscoveryRunRead])
def read_discovery_runs(db: Session = Depends(get_db)) -> list[DiscoveryRunRead]:
    return list_discovery_runs(db)


@router.get("/job-discovery/scheduler", response_model=SchedulerStatusRead)
def read_scheduler_status() -> SchedulerStatusRead:
    return scheduler_status()


@router.get("/gmail/status", response_model=GmailStatusRead)
def read_gmail_status() -> GmailStatusRead:
    return gmail_status()


@router.post("/gmail/auth", response_model=GmailStatusRead)
def run_gmail_auth() -> GmailStatusRead:
    try:
        return authenticate_gmail()
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/gmail/oauth/start")
def start_gmail_oauth() -> dict[str, str]:
    try:
        return start_gmail_web_oauth()
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/gmail/oauth/callback", response_model=None)
def finish_gmail_oauth(code: str, state: str | None = None):
    try:
        gmail_auth_status = complete_gmail_web_oauth(code=code, state=state)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    frontend_url = get_settings().frontend_app_url
    if frontend_url:
        separator = "&" if "?" in frontend_url else "?"
        return RedirectResponse(f"{frontend_url}{separator}gmail=connected")
    return gmail_auth_status


@router.post("/gmail/sync", response_model=list[EmailRead], status_code=status.HTTP_201_CREATED)
def sync_gmail(payload: GmailSyncRequest, db: Session = Depends(get_db)) -> list[EmailRead]:
    try:
        return sync_gmail_messages(
            db,
            query=payload.query,
            max_results=payload.max_results,
            skip_existing=payload.skip_existing,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Gmail sync failed: {error}") from error


@router.post("/linkedin/sync", response_model=LinkedInSyncResponse)
def sync_linkedin(payload: LinkedInSyncRequest, db: Session = Depends(get_db)) -> LinkedInSyncResponse:
    try:
        return sync_linkedin_activity(
            db,
            newer_than_days=payload.newer_than_days,
            max_results=payload.max_results,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LinkedIn sync failed: {error}") from error


@router.get("/emails", response_model=list[EmailRead])
def read_emails(db: Session = Depends(get_db)) -> list[EmailRead]:
    return list_emails(db)


@router.post("/emails/reclassify", response_model=list[EmailRead])
def reclassify_emails(db: Session = Depends(get_db)) -> list[EmailRead]:
    return reclassify_stored_emails(db)


@router.get("/raw-emails", response_model=list[RawEmailRead])
def read_raw_emails(db: Session = Depends(get_db)) -> list[RawEmailRead]:
    return list_raw_emails(db)


@router.post("/emails/mock-ingest", response_model=EmailRead, status_code=status.HTTP_201_CREATED)
def ingest_mock_email(payload: MockEmailIngestRequest, db: Session = Depends(get_db)) -> EmailRead:
    return mock_ingest_email(
        db,
        from_header=payload.from_header,
        subject=payload.subject,
        body_text=payload.body_text,
        snippet=payload.snippet,
    )


@router.post("/emails/{email_id}/draft-reply", response_model=MessageDraftRead, status_code=status.HTTP_201_CREATED)
def create_email_reply_draft(
    email_id: UUID,
    payload: EmailDraftCreateRequest,
    db: Session = Depends(get_db),
) -> MessageDraftRead:
    try:
        draft = create_reply_draft(db, email_id, create_gmail_draft=payload.create_gmail_draft)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    return draft


@router.patch("/emails/{email_id}/link", response_model=EmailRead)
def patch_email_link(
    email_id: UUID,
    payload: EmailLinkRequest,
    db: Session = Depends(get_db),
) -> EmailRead:
    try:
        email_record = link_email_to_application(
            db,
            email_id,
            application_id=payload.application_id,
            sync_actions=payload.sync_next_actions,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if not email_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    return email_record


@router.post("/agents/emails/{email_id}/triage", response_model=EmailRead)
def triage_email_with_ai(email_id: UUID, db: Session = Depends(get_db)) -> EmailRead:
    try:
        return run_email_triage_agent(db, email_id=email_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/agents/emails/triage-unlinked", response_model=list[EmailRead])
def triage_unlinked_emails(payload: EmailAgentBatchRequest, db: Session = Depends(get_db)) -> list[EmailRead]:
    try:
        return run_recent_unlinked_email_triage_agent(db, limit=payload.limit)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/applications/{application_id}/next-actions/sync", response_model=NextActionSyncResponse, status_code=status.HTTP_201_CREATED)
def sync_application_next_actions(application_id: UUID, db: Session = Depends(get_db)) -> NextActionSyncResponse:
    result = sync_next_actions(db, application_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return result


@router.get("/applications/{application_id}/actions", response_model=list[ActionRead])
def read_application_actions(application_id: UUID, db: Session = Depends(get_db)) -> list[ActionRead]:
    return list_application_actions(db, application_id)


@router.get("/actions", response_model=list[ActionRead])
def read_actions(action_status: str | None = None, db: Session = Depends(get_db)) -> list[ActionRead]:
    parsed_status = None
    if action_status:
        try:
            parsed_status = ActionStatus(action_status)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action status: {action_status}",
            ) from error
    return list_actions(db, status=parsed_status)


@router.patch("/actions/{action_id}", response_model=ActionRead)
def patch_action(action_id: UUID, payload: ActionUpdateRequest, db: Session = Depends(get_db)) -> ActionRead:
    action = update_action_status(db, action_id, status=payload.status, notes=payload.notes)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")
    return action


@router.post("/notifications/daily-summary", response_model=NotificationSummaryRead, status_code=status.HTTP_201_CREATED)
def create_daily_summary(db: Session = Depends(get_db)) -> NotificationSummaryRead:
    return generate_daily_summary(db)


@router.get("/notifications/daily-summary", response_model=list[NotificationSummaryRead])
def read_daily_summaries(db: Session = Depends(get_db)) -> list[NotificationSummaryRead]:
    return list_notification_summaries(db)


@router.post("/knowledge-base/aliases/rebuild", response_model=list[ProfileSkillAliasRead])
def rebuild_aliases(db: Session = Depends(get_db)) -> list[ProfileSkillAliasRead]:
    try:
        aliases = rebuild_skill_aliases(db)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [
        ProfileSkillAliasRead(
            id=alias.id,
            alias=alias.alias,
            rationale=alias.rationale,
            skill_name=alias.skill.name,
        )
        for alias in aliases
    ]


@router.get("/knowledge-base/aliases", response_model=list[ProfileSkillAliasRead])
def read_aliases(db: Session = Depends(get_db)) -> list[ProfileSkillAliasRead]:
    return [
        ProfileSkillAliasRead(
            id=alias.id,
            alias=alias.alias,
            rationale=alias.rationale,
            skill_name=alias.skill.name,
        )
        for alias in list_skill_aliases(db)
    ]


@router.post("/knowledge-base/evidence", response_model=EvidenceLookupResponse)
def lookup_evidence(payload: EvidenceLookupRequest, db: Session = Depends(get_db)) -> EvidenceLookupResponse:
    try:
        return find_evidence_for_claim(db, payload.claim)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/knowledge-base/embeddings/rebuild", response_model=EmbeddingRebuildResponse)
def rebuild_embeddings(payload: EmbeddingRebuildRequest, db: Session = Depends(get_db)) -> EmbeddingRebuildResponse:
    try:
        return rebuild_semantic_embeddings(db, include_jobs=payload.include_jobs, job_limit=payload.job_limit)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/jobs/{job_id}/embeddings", response_model=dict)
def create_job_embedding(job_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        changed = ensure_job_embedding(db, job_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return {"job_id": str(job_id), "created_or_updated": changed}


@router.get("/jobs/{job_id}/semantic-matches", response_model=list[SemanticMatchRead])
def read_job_semantic_matches(job_id: UUID, db: Session = Depends(get_db)) -> list[SemanticMatchRead]:
    return semantic_matches_for_job(db, job_id)


@router.post("/jobs/{job_id}/cv-tailoring-plan", response_model=CVTailoringPlanRead, status_code=status.HTTP_201_CREATED)
def generate_cv_tailoring_plan(job_id: UUID, db: Session = Depends(get_db)) -> CVTailoringPlanRead:
    plan = create_tailoring_plan(db, job_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job, job score, or candidate profile not found. Score the job before creating a CV tailoring plan.",
        )
    return plan


@router.get("/jobs/{job_id}/cv-tailoring-plans", response_model=list[CVTailoringPlanRead])
def read_cv_tailoring_plans(job_id: UUID, db: Session = Depends(get_db)) -> list[CVTailoringPlanRead]:
    return list_tailoring_plans(db, job_id)


@router.post("/cv-versions/{cv_version_id}/latex-preview", response_model=CVTailoringPlanRead)
def generate_cv_latex_preview(cv_version_id: UUID, db: Session = Depends(get_db)) -> CVTailoringPlanRead:
    cv_version = generate_latex_preview(db, cv_version_id)
    if not cv_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV version not found")
    return cv_version


@router.post("/cv-versions/{cv_version_id}/final-latex", response_model=CVTailoringPlanRead)
def generate_cv_final_latex(cv_version_id: UUID, db: Session = Depends(get_db)) -> CVTailoringPlanRead:
    try:
        cv_version = generate_final_latex_from_plan(db, cv_version_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if not cv_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV version not found")
    return cv_version


@router.get("/cv-versions/{cv_version_id}/download")
def download_cv_artifact(
    cv_version_id: UUID,
    artifact_format: str = Query(default="pdf", pattern="^(pdf|tex)$"),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        artifact_path = get_cv_artifact_path(db, cv_version_id, artifact_format)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    if not artifact_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generated {artifact_format.upper()} artifact not found for this CV version.",
        )

    media_type = "application/pdf" if artifact_format == "pdf" else "application/x-tex"
    return FileResponse(
        artifact_path,
        media_type=media_type,
        filename=artifact_path.name,
    )


@router.patch("/cv-versions/{cv_version_id}/review", response_model=CVTailoringPlanRead)
def review_cv(cv_version_id: UUID, payload: CVVersionReviewRequest, db: Session = Depends(get_db)) -> CVTailoringPlanRead:
    try:
        cv_version = review_cv_version(
            db,
            cv_version_id,
            status=payload.status,
            review_notes=payload.review_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if not cv_version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV version not found")
    return cv_version


@router.post("/jobs/{job_id}/message-drafts", response_model=list[MessageDraftRead], status_code=status.HTTP_201_CREATED)
def generate_messages(
    job_id: UUID,
    payload: MessageDraftGenerateRequest,
    db: Session = Depends(get_db),
) -> list[MessageDraftRead]:
    try:
        drafts = generate_message_drafts(
            db,
            job_id,
            draft_types=payload.draft_types,
            tone=payload.tone,
            language=payload.language,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if drafts is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job, profile, or score not found. Analyze the job and approve a CV first.",
        )
    return drafts


@router.get("/jobs/{job_id}/message-drafts", response_model=list[MessageDraftRead])
def read_message_drafts(job_id: UUID, db: Session = Depends(get_db)) -> list[MessageDraftRead]:
    return list_message_drafts(db, job_id)


@router.patch("/message-drafts/{message_draft_id}/review", response_model=MessageDraftRead)
def review_message(
    message_draft_id: UUID,
    payload: MessageDraftReviewRequest,
    db: Session = Depends(get_db),
) -> MessageDraftRead:
    try:
        draft = review_message_draft(
            db,
            message_draft_id,
            status=payload.status,
            review_notes=payload.review_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message draft not found")
    return draft
