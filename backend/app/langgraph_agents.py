from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai_client import generate_structured_output, require_ai_agents_enabled
from app.ai_schemas import AIEmailTriage, AIProfileExtraction
from app.audit import write_audit_log
from app.config import get_settings
from app.gmail_integration import _classify_email, _match_application_by_email_content, apply_email_effects
from app.models import (
    CandidateProfile,
    Document,
    Email,
    EmailCategory,
    EvidenceLevel,
    ProfileCertification,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSource,
    ProfileSkill,
    SourceType,
)
from app.next_action_agent import sync_next_actions
from app.profile_ingestion import get_profile


settings = get_settings()


class ProfileAgentState(TypedDict, total=False):
    document_id: str
    document_text: str
    document: Document
    extracted_profile: AIProfileExtraction


class EmailAgentState(TypedDict, total=False):
    email_id: str
    email: Email
    triage: AIEmailTriage


def _truncate_for_model(text: str) -> str:
    return text[: settings.ai_agent_max_input_chars]


def _clean_extracted_display_name(value: str | None) -> str | None:
    if not value:
        return value

    accent_map = {
        "a": "á",
        "e": "é",
        "i": "í",
        "o": "ó",
        "u": "ú",
        "A": "Á",
        "E": "É",
        "I": "Í",
        "O": "Ó",
        "U": "Ú",
    }

    cleaned = value
    for marker in ["´", "`", "'"]:
        for vowel, accented in accent_map.items():
            cleaned = cleaned.replace(f"{marker} {vowel}", accented).replace(
                f"{marker}{vowel}", accented
            )
    return " ".join(cleaned.split())


def _looks_career_related(email: Email) -> bool:
    category, _, _, _ = _classify_email(
        email.subject,
        email.body_text or email.snippet,
        email.from_email,
    )
    if category != EmailCategory.OTHER:
        return True

    haystack = " ".join(
        item for item in [email.from_email, email.subject or "", email.snippet or "", email.body_text or ""] if item
    ).lower()
    return any(
        term in haystack
        for term in [
            "linkedin",
            "job alert",
            "application",
            "recruiter",
            "interview",
            "assessment",
            "talent",
            "career",
            "hiring",
            "greenhouse",
            "lever",
            "ashby",
        ]
    )


def _get_or_create_profile(db: Session) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.created_at.asc()))
    if profile:
        return profile
    profile = CandidateProfile()
    db.add(profile)
    db.flush()
    return profile


def _clear_profile_details(db: Session, profile_id: UUID) -> None:
    for model in [ProfileSource, ProfileSkill, ProfileProject, ProfileExperience, ProfileEducation, ProfileCertification]:
        db.execute(delete(model).where(model.candidate_profile_id == profile_id))


def _record_profile_source(
    db: Session,
    *,
    profile_id: UUID,
    document: Document,
    field_name: str,
    extracted_value: dict[str, Any],
    evidence_text: str,
    confidence: int,
) -> None:
    db.add(
        ProfileSource(
            candidate_profile_id=profile_id,
            document_id=document.id,
            source_type=document.source_type,
            field_name=field_name,
            extracted_value=extracted_value,
            evidence_text=evidence_text,
            confidence=confidence,
        )
    )


def _load_profile_document(state: ProfileAgentState, db: Session) -> ProfileAgentState:
    document = db.get(Document, UUID(state["document_id"]))
    if not document or not document.extracted_text:
        raise ValueError("Document not found or has no extracted text.")
    return {
        "document_id": state["document_id"],
        "document": document,
        "document_text": _truncate_for_model(document.extracted_text),
    }


def _extract_profile_with_ai(state: ProfileAgentState, _: Session) -> ProfileAgentState:
    require_ai_agents_enabled()
    system_prompt = (
        "You are the Profile Ingestion Agent for CareerOps. "
        "You must extract only information that is explicitly supported by the provided candidate document. "
        "Do not invent experience, technologies, companies, metrics, dates, titles, achievements, education, certifications, or preferences. "
        "If information is missing or uncertain, return null or an empty list. "
        "For every skill, project, experience, education, and certification, include evidence_text copied or tightly paraphrased from the source text. "
        "Preserve honesty and traceability."
    )
    user_prompt = (
        "Extract the candidate profile from this document.\n\n"
        "Required output:\n"
        "- display_name\n- headline\n- location\n- summary\n- communication_style\n- work_preferences\n"
        "- skills\n- projects\n- experiences\n- education\n- certifications\n\n"
        f"Document text:\n{state['document_text']}"
    )
    extracted_profile = generate_structured_output(
        schema_model=AIProfileExtraction,
        schema_name="careerops_profile_extraction",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=settings.openai_profile_model,
    )
    return {"extracted_profile": extracted_profile}


def _persist_profile_from_ai(state: ProfileAgentState, db: Session) -> ProfileAgentState:
    document = state["document"]
    extracted = state["extracted_profile"]
    profile = _get_or_create_profile(db)
    _clear_profile_details(db, profile.id)

    profile.display_name = _clean_extracted_display_name(extracted.display_name)
    profile.headline = extracted.headline
    profile.location = extracted.location
    profile.summary = extracted.summary
    profile.preferences = {
        "communication_style": extracted.communication_style,
        "work_preferences": extracted.work_preferences,
        "source_document_id": str(document.id),
    }

    scalar_fields = [
        ("candidate_profile.display_name", extracted.display_name),
        ("candidate_profile.headline", extracted.headline),
        ("candidate_profile.location", extracted.location),
        ("candidate_profile.summary", extracted.summary),
    ]
    for field_name, value in scalar_fields:
        if value:
            _record_profile_source(
                db,
                profile_id=profile.id,
                document=document,
                field_name=field_name,
                extracted_value={"value": value},
                evidence_text=value,
                confidence=90,
            )

    seen_skills: set[tuple[str, str | None]] = set()
    for skill in extracted.skills:
        key = (skill.name.lower(), skill.category.lower() if skill.category else None)
        if key in seen_skills:
            continue
        seen_skills.add(key)
        db.add(
            ProfileSkill(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                name=skill.name,
                category=skill.category,
                evidence_level=skill.evidence_level,
                evidence_text=skill.evidence_text,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_skills",
            extracted_value={"name": skill.name, "category": skill.category, "evidence_level": skill.evidence_level},
            evidence_text=skill.evidence_text,
            confidence=90 if skill.evidence_level == EvidenceLevel.STRONG else 75,
        )

    for experience in extracted.experiences:
        db.add(
            ProfileExperience(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                company=experience.company,
                title=experience.title,
                location=experience.location,
                start_date=experience.start_date,
                end_date=experience.end_date,
                bullets=experience.bullets,
                evidence_text=experience.evidence_text,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_experience",
            extracted_value=experience.model_dump(),
            evidence_text=experience.evidence_text,
            confidence=90,
        )

    for project in extracted.projects:
        db.add(
            ProfileProject(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                name=project.name,
                description=project.description,
                technologies=project.technologies,
                impact=project.impact,
                evidence_text=project.evidence_text,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_projects",
            extracted_value=project.model_dump(),
            evidence_text=project.evidence_text,
            confidence=90,
        )

    for education in extracted.education:
        db.add(
            ProfileEducation(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                institution=education.institution,
                degree=education.degree,
                location=education.location,
                dates=education.dates,
                evidence_text=education.evidence_text,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_education",
            extracted_value=education.model_dump(),
            evidence_text=education.evidence_text,
            confidence=90,
        )

    for certification in extracted.certifications:
        db.add(
            ProfileCertification(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                name=certification.name,
                issuer=certification.issuer,
                evidence_text=certification.evidence_text,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_certifications",
            extracted_value=certification.model_dump(),
            evidence_text=certification.evidence_text,
            confidence=85,
        )

    write_audit_log(
        db,
        event_type="profile.extracted_by_ai_agent",
        entity_type="candidate_profile",
        entity_id=profile.id,
        details={"document_id": str(document.id), "document_filename": document.original_filename},
    )
    db.commit()
    return {"document_id": str(document.id)}


def _load_email_for_agent(state: EmailAgentState, db: Session) -> EmailAgentState:
    email = db.get(Email, UUID(state["email_id"]))
    if not email:
        raise ValueError("Email not found.")
    return {"email_id": state["email_id"], "email": email}


def _triage_email_with_ai(state: EmailAgentState, _: Session) -> EmailAgentState:
    require_ai_agents_enabled()
    email = state["email"]
    system_prompt = (
        "You are the Email Monitoring Agent for CareerOps. "
        "Read one email at a time and classify only its relevance for the candidate's job search. "
        "Do not invent company names, roles, or statuses. "
        "If the email is marketing, security, newsletters, or unrelated account activity, mark it as not relevant_to_careerops and category other. "
        "If the email clearly refers to a job application, recruiter follow-up, interview, assessment, rejection, offer, documents requested, or form pending, classify it accordingly."
    )
    user_prompt = (
        f"From: {email.from_email}\n"
        f"From name: {email.from_name or ''}\n"
        f"Subject: {email.subject or ''}\n"
        f"Snippet: {email.snippet or ''}\n"
        f"Body: {_truncate_for_model(email.body_text or '')}\n"
    )
    triage = generate_structured_output(
        schema_model=AIEmailTriage,
        schema_name="careerops_email_triage",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=settings.openai_email_model,
    )
    return {"triage": triage}


def _persist_email_triage(state: EmailAgentState, db: Session) -> EmailAgentState:
    email = state["email"]
    triage = state["triage"]
    original_category = email.category
    locked_categories = {
        EmailCategory.JOB_ALERT,
        EmailCategory.APPLICATION_CONFIRMATION,
        EmailCategory.INTERVIEW_INVITATION,
        EmailCategory.CODING_ASSESSMENT,
        EmailCategory.REJECTION,
        EmailCategory.OFFER,
    }
    if original_category in locked_categories:
        email.category = original_category
    else:
        email.category = triage.category if triage.relevant_to_careerops else EmailCategory.OTHER
    email.company_name = triage.company_name or email.company_name
    email.urgency = triage.urgency
    email.requires_reply = triage.requires_reply
    email.suggested_action = triage.suggested_action

    matched_application = _match_application_by_email_content(
        db,
        company_name=email.company_name,
        subject=email.subject,
        snippet=email.snippet,
        body_text=" ".join(item for item in [email.body_text or "", triage.role_hint or ""] if item),
        received_at=email.received_at,
        category=email.category,
    )
    if matched_application:
        email.application_id = matched_application.id

    write_audit_log(
        db,
        event_type="email.triaged_by_ai_agent",
        entity_type="email",
        entity_id=email.id,
        details={
            "category": email.category,
            "company_name": email.company_name,
            "application_id": str(email.application_id) if email.application_id else None,
            "reasoning": triage.reasoning,
        },
    )
    db.flush()
    apply_email_effects(db, email)
    if email.application_id:
        sync_next_actions(db, email.application_id)
    db.commit()
    return {"email_id": str(email.id)}


def _profile_graph(db: Session):
    graph = StateGraph(ProfileAgentState)
    graph.add_node("load_document", lambda state: _load_profile_document(state, db))
    graph.add_node("extract_profile", lambda state: _extract_profile_with_ai(state, db))
    graph.add_node("persist_profile", lambda state: _persist_profile_from_ai(state, db))
    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "extract_profile")
    graph.add_edge("extract_profile", "persist_profile")
    graph.add_edge("persist_profile", END)
    return graph.compile()


def _email_graph(db: Session):
    graph = StateGraph(EmailAgentState)
    graph.add_node("load_email", lambda state: _load_email_for_agent(state, db))
    graph.add_node("triage_email", lambda state: _triage_email_with_ai(state, db))
    graph.add_node("persist_email", lambda state: _persist_email_triage(state, db))
    graph.add_edge(START, "load_email")
    graph.add_edge("load_email", "triage_email")
    graph.add_edge("triage_email", "persist_email")
    graph.add_edge("persist_email", END)
    return graph.compile()


def run_profile_ingestion_agent(db: Session, *, document_id: UUID) -> CandidateProfile:
    _profile_graph(db).invoke({"document_id": str(document_id)})
    profile = get_profile(db)
    if not profile:
        raise ValueError("Candidate profile was not created by the AI agent.")
    return profile


def run_email_triage_agent(db: Session, *, email_id: UUID) -> Email:
    _email_graph(db).invoke({"email_id": str(email_id)})
    email = db.get(Email, email_id)
    if not email:
        raise ValueError("Email not found after AI triage.")
    return email


def run_recent_unlinked_email_triage_agent(db: Session, *, limit: int = 15) -> list[Email]:
    require_ai_agents_enabled()
    candidates = list(
        db.scalars(
            select(Email)
            .where(Email.application_id.is_(None))
            .order_by(Email.received_at.desc().nullslast(), Email.created_at.desc())
            .limit(limit * 5)
        )
    )
    emails = [email for email in candidates if _looks_career_related(email)][:limit]
    triaged: list[Email] = []
    for email in emails:
        triaged.append(run_email_triage_agent(db, email_id=email.id))
    return triaged
