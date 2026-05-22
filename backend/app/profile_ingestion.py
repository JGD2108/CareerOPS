import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.audit import write_audit_log
from app.documents import is_evaluation_artifact_document
from app.models import (
    CandidateProfile,
    Document,
    EvidenceLevel,
    ProfileCertification,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSource,
    ProfileSkill,
    SourceType,
)
from app.text_normalization import normalize_bullet_text
from app.text_normalization import normalize_display_list
from app.text_normalization import normalize_display_text
from app.text_normalization import normalize_text_block


@dataclass(frozen=True)
class Section:
    name: str
    text: str


@dataclass(frozen=True)
class CommandMatch:
    args: list[str]
    start: int
    end: int


def _read_braced_argument(text: str, start: int) -> tuple[str, int] | None:
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] != "{":
        return None

    depth = 0
    content_start = start + 1
    index = start
    while index < len(text):
        char = text[index]
        previous = text[index - 1] if index > 0 else ""
        if char == "{" and previous != "\\":
            depth += 1
        elif char == "}" and previous != "\\":
            depth -= 1
            if depth == 0:
                return text[content_start:index], index + 1
        index += 1
    return None


def _iter_command_matches(text: str, command: str, arg_count: int) -> list[CommandMatch]:
    token = "\\" + command
    matches: list[CommandMatch] = []
    index = 0
    while True:
        start = text.find(token, index)
        if start == -1:
            break
        cursor = start + len(token)
        args: list[str] = []
        for _ in range(arg_count):
            parsed = _read_braced_argument(text, cursor)
            if not parsed:
                break
            arg, cursor = parsed
            args.append(arg.strip())
        if len(args) == arg_count:
            matches.append(CommandMatch(args=args, start=start, end=cursor))
            index = cursor
        else:
            index = start + len(token)
    return matches


def _clean_latex(text: str) -> str:
    cleaned = text
    cleaned = cleaned.replace("\\&", "&")
    cleaned = cleaned.replace("\\%", "%")
    cleaned = cleaned.replace("\\,", ",")
    cleaned = cleaned.replace("{,}", ",")
    cleaned = cleaned.replace("\\'", "")
    cleaned = re.sub(r"\\href\{([^}]*)\}\{([^}]*)\}", r"\2", cleaned)
    cleaned = re.sub(r"\\textbf\{([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\textit\{\\small\s*([^}]*)\}", r"\1", cleaned)
    cleaned = re.sub(r"\\small\s*", "", cleaned)
    cleaned = re.sub(r"[{}]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return normalize_text_block(cleaned) or ""


def _extract_sections(text: str) -> dict[str, Section]:
    matches = list(re.finditer(r"\\section\{([^}]*)\}", text))
    sections: dict[str, Section] = {}
    for index, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = Section(name=name, text=text[start:end].strip())
    return sections


def _extract_command_pairs(section_text: str, command: str) -> list[tuple[str, str]]:
    return [(match.args[0], match.args[1]) for match in _iter_command_matches(section_text, command, 2)]


def _extract_subheadings(section_text: str) -> list[tuple[str, str, str, str, str]]:
    results = []
    for match in _iter_command_matches(section_text, "resumeSubheading", 4):
        evidence = section_text[match.start : match.end]
        results.append((*match.args, evidence))
    return results


def _extract_projects(section_text: str) -> list[dict]:
    matches = _iter_command_matches(section_text, "resumeProjectHeading", 4)
    projects = []
    for index, match in enumerate(matches):
        start = match.start
        end = matches[index + 1].start if index + 1 < len(matches) else len(section_text)
        block = section_text[start:end]
        bullets = [value for _, value in _extract_command_pairs(block, "resumeItem")]
        tech = [item.strip() for item in match.args[3].split(",") if item.strip()]
        projects.append(
            {
                "name": _clean_latex(match.args[0]),
                "description": _clean_latex(match.args[2]),
                "technologies": [_clean_latex(item) for item in tech],
                "impact": _clean_latex(" ".join(bullets)) if bullets else None,
                "evidence_text": _clean_latex(block),
            }
        )
    return projects


def _get_or_create_profile(db: Session) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.created_at.asc()))
    if profile:
        return profile
    profile = CandidateProfile()
    db.add(profile)
    db.flush()
    return profile


def _latest_cv_document(db: Session) -> Document | None:
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.source_type == SourceType.CV, Document.extracted_text.is_not(None))
            .order_by(Document.created_at.desc())
        )
    )
    for document in documents:
        if not is_evaluation_artifact_document(document):
            return document
    return None


def _clear_profile_details(db: Session, profile_id) -> None:
    for model in [ProfileSource, ProfileSkill, ProfileProject, ProfileExperience, ProfileEducation, ProfileCertification]:
        db.execute(delete(model).where(model.candidate_profile_id == profile_id))


def _record_profile_source(
    db: Session,
    *,
    profile_id,
    document: Document,
    field_name: str,
    extracted_value: dict,
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


def extract_profile_from_latest_cv(db: Session) -> CandidateProfile:
    document = _latest_cv_document(db)
    if not document or not document.extracted_text:
        raise ValueError("No CV document with extracted text found.")

    profile = _get_or_create_profile(db)
    _clear_profile_details(db, profile.id)

    text = document.extracted_text
    sections = _extract_sections(text)

    name_token = r"\def\myname"
    name_start = text.find(name_token)
    name_match = _read_braced_argument(text, name_start + len(name_token)) if name_start != -1 else None
    profile.display_name = _clean_latex(name_match[0]) if name_match else profile.display_name
    profile.headline = "Backend Engineer | Python, APIs, AI Workflows, Automation"
    profile.location = "Barranquilla, Colombia" if "Barranquilla, Colombia" in text else profile.location
    if "Summary" in sections:
        profile.summary = _clean_latex(sections["Summary"].text)
    profile.preferences = {
        **(profile.preferences or {}),
        "source_document_id": str(document.id),
        "profile_origin": "deterministic_cv_parser",
    }
    if profile.display_name:
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="candidate_profile.display_name",
            extracted_value={"value": profile.display_name},
            evidence_text=_clean_latex(name_match[0]) if name_match else profile.display_name,
            confidence=100,
        )
    if profile.headline:
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="candidate_profile.headline",
            extracted_value={"value": profile.headline},
            evidence_text=profile.headline,
            confidence=75,
        )
    if profile.location:
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="candidate_profile.location",
            extracted_value={"value": profile.location},
            evidence_text=profile.location,
            confidence=80,
        )
    if profile.summary:
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="candidate_profile.summary",
            extracted_value={"value": profile.summary},
            evidence_text=profile.summary,
            confidence=90,
        )

    for category, values in _extract_command_pairs(sections.get("Technical Skills", Section("", "")).text, "resumeSubItem"):
        evidence = _clean_latex(f"{category}: {values}")
        for skill in [item.strip() for item in _clean_latex(values).split(",") if item.strip()]:
            cleaned_category = _clean_latex(category)
            db.add(
                ProfileSkill(
                    candidate_profile_id=profile.id,
                    source_document_id=document.id,
                    name=skill,
                    category=cleaned_category,
                    evidence_level=EvidenceLevel.STRONG,
                    evidence_text=evidence,
                )
            )
            _record_profile_source(
                db,
                profile_id=profile.id,
                document=document,
                field_name="profile_skills",
                extracted_value={"name": skill, "category": cleaned_category},
                evidence_text=evidence,
                confidence=90,
            )

    for company, location, title, dates, evidence in _extract_subheadings(
        sections.get("Experience", Section("", "")).text
    ):
        experience_section = sections.get("Experience", Section("", "")).text
        bullets = [value for _, value in _extract_command_pairs(experience_section, "resumeItem")]
        start_date, end_date = None, None
        if "--" in dates:
            start_date, end_date = [part.strip() for part in dates.split("--", 1)]
        cleaned_company = _clean_latex(company)
        cleaned_title = _clean_latex(title)
        cleaned_location = _clean_latex(location)
        cleaned_start_date = _clean_latex(start_date) if start_date else None
        cleaned_end_date = _clean_latex(end_date) if end_date else None
        cleaned_bullets = [_clean_latex(item) for item in bullets]
        cleaned_evidence = _clean_latex(evidence)
        db.add(
            ProfileExperience(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                company=cleaned_company,
                title=cleaned_title,
                location=cleaned_location,
                start_date=cleaned_start_date,
                end_date=cleaned_end_date,
                bullets=cleaned_bullets,
                evidence_text=cleaned_evidence,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_experience",
            extracted_value={
                "company": cleaned_company,
                "title": cleaned_title,
                "location": cleaned_location,
                "start_date": cleaned_start_date,
                "end_date": cleaned_end_date,
                "bullets": cleaned_bullets,
            },
            evidence_text=cleaned_evidence,
            confidence=95,
        )

    for project in _extract_projects(sections.get("Selected Projects", Section("", "")).text):
        db.add(
            ProfileProject(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                **project,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_projects",
            extracted_value={
                "name": project["name"],
                "description": project["description"],
                "technologies": project["technologies"],
                "impact": project["impact"],
            },
            evidence_text=project["evidence_text"],
            confidence=90,
        )

    for institution, location, degree, dates, evidence in _extract_subheadings(
        sections.get("Education", Section("", "")).text
    ):
        cleaned_institution = _clean_latex(institution)
        cleaned_degree = _clean_latex(degree)
        cleaned_location = _clean_latex(location)
        cleaned_dates = _clean_latex(dates)
        cleaned_evidence = _clean_latex(evidence)
        db.add(
            ProfileEducation(
                candidate_profile_id=profile.id,
                source_document_id=document.id,
                institution=cleaned_institution,
                degree=cleaned_degree,
                location=cleaned_location,
                dates=cleaned_dates,
                evidence_text=cleaned_evidence,
            )
        )
        _record_profile_source(
            db,
            profile_id=profile.id,
            document=document,
            field_name="profile_education",
            extracted_value={
                "institution": cleaned_institution,
                "degree": cleaned_degree,
                "location": cleaned_location,
                "dates": cleaned_dates,
            },
            evidence_text=cleaned_evidence,
            confidence=90,
        )

    additional = sections.get("Additional", Section("", "")).text
    for label, values in _extract_command_pairs(additional, "resumeSubItem"):
        evidence = _clean_latex(f"{label}: {values}")
        cleaned_label = _clean_latex(label)
        for certification in [item.strip() for item in _clean_latex(values).split(",") if item.strip()]:
            db.add(
                ProfileCertification(
                    candidate_profile_id=profile.id,
                    source_document_id=document.id,
                    name=certification,
                    issuer=None,
                    evidence_text=evidence,
                )
            )
            _record_profile_source(
                db,
                profile_id=profile.id,
                document=document,
                field_name="profile_certifications",
                extracted_value={"name": certification, "label": cleaned_label},
                evidence_text=evidence,
                confidence=80,
            )

    write_audit_log(
        db,
        event_type="profile.extracted",
        entity_type="candidate_profile",
        entity_id=profile.id,
        details={"source_document_id": str(document.id), "source_filename": document.original_filename},
    )
    db.commit()
    return get_profile(db)


def get_profile(db: Session) -> CandidateProfile | None:
    profile = db.scalar(
        select(CandidateProfile)
        .options(
            selectinload(CandidateProfile.sources).selectinload(ProfileSource.document),
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.skills).selectinload(ProfileSkill.aliases),
            selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.experiences),
            selectinload(CandidateProfile.education),
            selectinload(CandidateProfile.certifications),
        )
        .order_by(CandidateProfile.created_at.asc())
    )
    if not profile:
        return None

    source_document_ids = [
        source.document_id
        for source in profile.sources
        if source.document_id is not None
    ]
    if source_document_ids:
        source_documents = [source.document for source in profile.sources if source.document is not None]
        if source_documents and all(is_evaluation_artifact_document(document) for document in source_documents):
            return None

    source_document_id = None
    if isinstance(profile.preferences, dict):
        raw_source_document_id = profile.preferences.get("source_document_id")
        if isinstance(raw_source_document_id, str):
            source_document_id = raw_source_document_id
    if source_document_id:
        try:
            document = db.get(Document, UUID(source_document_id))
        except ValueError:
            document = None
        if document and is_evaluation_artifact_document(document):
            return None

    profile.display_name = normalize_display_text(profile.display_name)
    profile.headline = normalize_display_text(profile.headline)
    profile.location = normalize_display_text(profile.location)
    profile.summary = normalize_display_text(profile.summary)

    for skill in profile.skills:
        skill.name = normalize_display_text(skill.name, fallback=skill.name) or skill.name
        skill.category = normalize_display_text(skill.category)
        skill.evidence_text = normalize_display_text(skill.evidence_text, fallback=skill.evidence_text) or skill.evidence_text

    for project in profile.projects:
        project.name = normalize_display_text(project.name, fallback=project.name) or project.name
        project.description = normalize_display_text(project.description)
        project.technologies = normalize_display_list(project.technologies)
        project.impact = normalize_display_text(project.impact)
        project.evidence_text = normalize_display_text(project.evidence_text, fallback=project.evidence_text) or project.evidence_text

    for experience in profile.experiences:
        experience.company = normalize_display_text(experience.company, fallback=experience.company) or experience.company
        experience.title = normalize_display_text(experience.title, fallback=experience.title) or experience.title
        experience.location = normalize_display_text(experience.location)
        experience.start_date = normalize_display_text(experience.start_date)
        experience.end_date = normalize_display_text(experience.end_date)
        experience.bullets = [
            bullet
            for bullet in (normalize_bullet_text(item) for item in experience.bullets or [])
            if bullet
        ]
        experience.evidence_text = normalize_display_text(experience.evidence_text, fallback=experience.evidence_text) or experience.evidence_text

    for education in profile.education:
        education.institution = normalize_display_text(education.institution, fallback=education.institution) or education.institution
        education.degree = normalize_display_text(education.degree, fallback=education.degree) or education.degree
        education.location = normalize_display_text(education.location)
        education.dates = normalize_display_text(education.dates)
        education.evidence_text = normalize_display_text(education.evidence_text, fallback=education.evidence_text) or education.evidence_text

    for certification in profile.certifications:
        certification.name = normalize_display_text(certification.name, fallback=certification.name) or certification.name
        certification.issuer = normalize_display_text(certification.issuer)
        certification.evidence_text = normalize_display_text(certification.evidence_text, fallback=certification.evidence_text) or certification.evidence_text

    return profile
