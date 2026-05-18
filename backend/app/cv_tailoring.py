from pathlib import Path
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai_client import ai_agents_enabled, generate_structured_output
from app.ai_schemas import AICVTailoringPlan
from app.audit import write_audit_log
from app.config import get_settings
from app.models import (
    CVVersion,
    CVVersionStatus,
    CandidateProfile,
    Document,
    Job,
    JobScore,
    ProfileSkill,
    SourceType,
)


def _latest_cv_document(db: Session) -> Document | None:
    return db.scalar(
        select(Document)
        .where(Document.source_type == SourceType.CV, Document.extracted_text.is_not(None))
        .order_by(Document.created_at.desc())
    )


def _latest_cv_template_document(db: Session) -> Document | None:
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.source_type == SourceType.CV, Document.extracted_text.is_not(None))
            .order_by(Document.created_at.desc())
        )
    )
    for document in documents:
        filename = (document.original_filename or "").lower()
        if filename.endswith(".tex"):
            return document
    return documents[0] if documents else None


def _latest_job_score(db: Session, job_id: UUID) -> JobScore | None:
    return db.scalar(select(JobScore).where(JobScore.job_id == job_id).order_by(JobScore.created_at.desc()))


def _load_profile(db: Session, profile_id: UUID) -> CandidateProfile | None:
    return db.scalar(
        select(CandidateProfile)
        .where(CandidateProfile.id == profile_id)
        .options(
            selectinload(CandidateProfile.skills).selectinload(ProfileSkill.aliases),
            selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.experiences),
            selectinload(CandidateProfile.education),
            selectinload(CandidateProfile.certifications),
        )
    )


def _normalize(value: str) -> str:
    return value.lower().replace(".", "").replace("-", " ")


def _storage_root() -> Path:
    settings = get_settings()
    root = Path(settings.local_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _escape_latex(value: str | None) -> str:
    if not value:
        return ""
    value = _clean_render_text(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _legacy_clean_render_text(value: str) -> str:
    return (
        value.replace("Ã¡", "á")
        .replace("Ã©", "é")
        .replace("Ã­", "í")
        .replace("Ã³", "ó")
        .replace("Ãº", "ú")
        .replace("Ã±", "ñ")
        .replace("Ã", "Á")
        .replace("Ã‰", "É")
        .replace("Ã", "Í")
        .replace("Ã“", "Ó")
        .replace("Ãš", "Ú")
        .replace("Ã‘", "Ñ")
        .replace("â", "--")
        .replace("â", "---")
        .replace("â", "'")
        .replace("â", '"')
        .replace("â", '"')
        .replace("\u0091", "")
        .replace("\u0098", "")
        .replace("\u0099", "")
    )


def _clean_render_text(value: str) -> str:
    cleaned = value
    markers = ("Ã", "Â", "â", "\u0091", "\u0098", "\u0099", "\ufffd")

    for _ in range(2):
        try:
            decoded = cleaned.encode("cp1252").decode("utf-8")
        except UnicodeError:
            break
        if sum(decoded.count(marker) for marker in markers) >= sum(
            cleaned.count(marker) for marker in markers
        ):
            break
        cleaned = decoded

    return (
        cleaned.replace("–", "--")
        .replace("—", "---")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("\u0091", "")
        .replace("\u0098", "")
        .replace("\u0099", "")
    )


def _itemize(items: list[str]) -> str:
    if not items:
        return "\\item No supported items selected."
    return "\n".join(f"\\item {_escape_latex(item)}" for item in items)


def _clean_display_term(value: str) -> str:
    return _clean_render_text(value).strip().rstrip(".;:,")


def _clean_display_sentence(value: str) -> str:
    return _clean_render_text(value).replace("..", ".").strip()


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    normalized = _normalize(value)
    return any(term in normalized for term in terms)


def _unique_clean_terms(values: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for value in values:
        term = _clean_display_term(value)
        key = _normalize(term)
        if not term or key in seen:
            continue
        seen.add(key)
        terms.append(term)
        if limit and len(terms) >= limit:
            break
    return terms


def _group_skills(skills: list[str]) -> dict[str, list[str]]:
    groups = {
        "Data, AI, and automation": (
            "gemini",
            "llm",
            "prompt",
            "pgvector",
            "semantic",
            "bigquery",
            "data",
            "pipeline",
            "workflow",
            "automation",
            "audit",
        ),
        "Cloud, deployment, and tools": (
            "docker",
            "nginx",
            "aws",
            "lambda",
            "s3",
            "eventbridge",
            "boto3",
            "gcp",
            "github",
            "git",
            "swagger",
            "openapi",
        ),
        "Full-stack and backend": (
            "python",
            "node",
            "nestjs",
            "typescript",
            "javascript",
            "react",
            "api",
            "rest",
            "jwt",
            "prisma",
            "sql",
            "postgres",
            "mysql",
        ),
    }
    remaining = _unique_clean_terms(skills)
    assigned: dict[str, list[str]] = {label: [] for label in groups}
    used: set[str] = set()

    for label, terms in groups.items():
        matched = [skill for skill in remaining if _contains_any(skill, terms)]
        matched = [skill for skill in matched if _normalize(skill) not in used][:10]
        if matched:
            assigned[label] = matched
            used.update(_normalize(skill) for skill in matched)

    output = {
        label: assigned[label]
        for label in ["Full-stack and backend", "Data, AI, and automation", "Cloud, deployment, and tools"]
        if assigned[label]
    }
    extra = [skill for skill in remaining if _normalize(skill) not in used]
    if extra:
        output["Additional verified tools"] = extra[:8]
    return output


def _metric_rich_fragments(cv_version: CVVersion, limit: int = 3) -> list[str]:
    fragments: list[str] = []
    plan = cv_version.tailoring_plan
    for item in plan.get("experience_bullets_to_reuse", []):
        bullet = _clean_display_sentence(item.get("bullet", ""))
        if any(char.isdigit() for char in bullet):
            fragments.append(bullet)
    for item in plan.get("projects_to_prioritize", []):
        existing = item.get("existing_content", {})
        for value in [existing.get("impact"), existing.get("description"), item.get("why")]:
            text = _clean_display_sentence(value or "")
            if text and any(char.isdigit() for char in text):
                fragments.append(text)
    return fragments[:limit]


def _compact_metric_phrase(value: str, max_words: int = 22) -> str:
    words = value.split()
    if len(words) <= max_words:
        return value.rstrip(".")
    return " ".join(words[:max_words]).rstrip(".,;:") + "..."


def _replace_section(latex: str, section_name: str, new_content: str) -> str:
    pattern = re.compile(rf"(\\section\{{{re.escape(section_name)}\}})(.*?)(?=\\section\{{|\\end\{{document\}})", re.DOTALL)
    match = pattern.search(latex)
    if not match:
        raise ValueError(f"Section not found in template: {section_name}")
    return latex[: match.start()] + new_content.rstrip() + "\n\n" + latex[match.end() :]


def _extract_original_section(latex: str, section_name: str) -> str | None:
    pattern = re.compile(rf"(\\section\{{{re.escape(section_name)}\}}.*?)(?=\\section\{{|\\end\{{document\}})", re.DOTALL)
    match = pattern.search(latex)
    if not match:
        return None
    return match.group(1).rstrip()


def _replace_def(latex: str, name: str, value: str) -> str:
    return re.sub(rf"\\def\\{name}\{{.*?\}}", rf"\\def\\{name}{{{_escape_latex(value)}}}", latex, count=1)


def _select_project_highlights(profile: CandidateProfile, matched_terms: list[str]) -> list[dict]:
    highlights = []
    for project in profile.projects:
        searchable = _normalize(
            " ".join(
                [
                    project.name,
                    project.description or "",
                    " ".join(project.technologies or []),
                    project.impact or "",
                ]
            )
        )
        matched = [term for term in matched_terms if _normalize(term) in searchable]
        if matched:
            highlights.append(
                {
                    "project": project.name,
                    "why": f"Matches job terms: {', '.join(sorted(set(matched)))}.",
                    "existing_content": {
                        "description": project.description,
                        "technologies": project.technologies,
                        "impact": project.impact,
                    },
                    "evidence_text": project.evidence_text,
                }
            )
    return highlights[:3]


def _select_experience_bullets(profile: CandidateProfile, matched_terms: list[str]) -> list[dict]:
    selected = []
    for experience in profile.experiences:
        for bullet in experience.bullets or []:
            normalized_bullet = _normalize(bullet)
            matched = [term for term in matched_terms if _normalize(term) in normalized_bullet]
            if matched:
                selected.append(
                    {
                        "company": experience.company,
                        "title": experience.title,
                        "location": experience.location,
                        "start_date": experience.start_date,
                        "end_date": experience.end_date,
                        "bullet": bullet,
                        "why": f"Matches job terms: {', '.join(sorted(set(matched)))}.",
                        "evidence_text": experience.evidence_text,
                    }
                )
    return selected[:5]


def _all_project_candidates(profile: CandidateProfile) -> list[dict]:
    return [
        {
            "project": project.name,
            "why": "Verified project available for tailoring.",
            "existing_content": {
                "description": project.description,
                "technologies": project.technologies,
                "impact": project.impact,
            },
            "evidence_text": project.evidence_text,
        }
        for project in profile.projects
    ][:8]


def _all_experience_candidates(profile: CandidateProfile) -> list[dict]:
    candidates: list[dict] = []
    for experience in profile.experiences:
        for bullet in experience.bullets or []:
            candidates.append(
                {
                    "company": experience.company,
                    "title": experience.title,
                    "location": experience.location,
                    "start_date": experience.start_date,
                    "end_date": experience.end_date,
                    "bullet": bullet,
                    "why": "Verified experience bullet available for reuse.",
                    "evidence_text": experience.evidence_text,
                }
            )
    return candidates[:20]


def _build_rule_based_plan_data(
    db: Session,
    *,
    job: Job,
    score: JobScore,
    profile: CandidateProfile,
    source_document: Document | None,
) -> tuple[dict, list]:
    matched_terms = sorted(
        {item.get("profile_skill") for item in score.matched_skills if item.get("profile_skill")}
    )
    missing_terms = [item.get("required_skill") for item in score.missing_or_weak_skills if item.get("required_skill")]
    project_highlights = _select_project_highlights(profile, matched_terms)
    experience_bullets = _select_experience_bullets(profile, matched_terms)

    summary_focus = [
        "Keep the current backend/AI workflow positioning.",
    ]
    if matched_terms:
        summary_focus.append(f"Emphasize matched evidence: {', '.join(matched_terms[:10])}.")
    else:
        summary_focus.append("Use only verified backend, data, and AI workflow evidence already present in the profile.")
    if missing_terms:
        summary_focus.append(
            "Do not claim direct experience with missing requirements: " + ", ".join(missing_terms) + "."
        )

    changes = [
        {
            "section": "Summary",
            "action": "adapt_focus",
            "reason": "Align summary emphasis with matched job requirements without adding new claims.",
            "evidence": score.evidence[:5],
        },
        {
            "section": "Technical Skills",
            "action": "prioritize_existing_skills",
            "skills_to_prioritize": matched_terms,
            "reason": "These skills were matched from the structured profile and have evidence.",
        },
        {
            "section": "Experience",
            "action": "select_existing_bullets",
            "bullets": experience_bullets,
            "reason": "Use only existing bullets extracted from verified profile sources.",
        },
        {
            "section": "Selected Projects",
            "action": "prioritize_existing_projects",
            "projects": project_highlights,
            "reason": "Prioritize projects whose existing content overlaps with the job requirements.",
        },
    ]
    if missing_terms:
        changes.append(
            {
                "section": "Honesty Guardrails",
                "action": "avoid_unbacked_claims",
                "missing_or_weak_requirements": missing_terms,
                "reason": "No direct evidence was found in the provided CV/profile sources for these requirements.",
            }
        )

    tailoring_plan = {
        "planner": "rules_fallback",
        "job": {
            "id": str(job.id),
            "title": job.title,
            "company": job.company.name if job.company else None,
        },
        "score": {
            "id": str(score.id),
            "score": score.score,
            "recommendation": score.recommendation,
            "reasons": score.reasons,
            "risks": score.risks,
        },
        "summary_focus": summary_focus,
        "skills_to_prioritize": matched_terms,
        "experience_bullets_to_reuse": experience_bullets,
        "original_experience_section": _extract_original_section(source_document.extracted_text, "Experience")
        if source_document and source_document.extracted_text
        else None,
        "projects_to_prioritize": project_highlights,
        "do_not_claim": missing_terms,
        "approval_required": True,
        "template_document_id": str(source_document.id) if source_document else None,
        "template_filename": source_document.original_filename if source_document else None,
    }
    return tailoring_plan, changes


def _build_profile_context(profile: CandidateProfile) -> dict:
    return {
        "display_name": profile.display_name,
        "headline": profile.headline,
        "location": profile.location,
        "summary": profile.summary,
        "preferences": profile.preferences,
        "skills": [
            {
                "name": skill.name,
                "category": skill.category,
                "evidence_level": skill.evidence_level,
                "evidence_text": skill.evidence_text,
            }
            for skill in profile.skills
        ],
        "projects": [
            {
                "name": project.name,
                "description": project.description,
                "technologies": project.technologies,
                "impact": project.impact,
                "evidence_text": project.evidence_text,
            }
            for project in profile.projects
        ],
        "experiences": [
            {
                "company": experience.company,
                "title": experience.title,
                "location": experience.location,
                "start_date": experience.start_date,
                "end_date": experience.end_date,
                "bullets": experience.bullets,
                "evidence_text": experience.evidence_text,
            }
            for experience in profile.experiences
        ],
    }


def _build_template_context(source_document: Document | None) -> dict:
    latex = source_document.extracted_text if source_document else None
    if not latex:
        return {}
    return {
        "filename": source_document.original_filename,
        "summary_section": _extract_original_section(latex, "Summary"),
        "technical_skills_section": _extract_original_section(latex, "Technical Skills"),
        "experience_section": _extract_original_section(latex, "Experience"),
        "projects_section": _extract_original_section(latex, "Selected Projects"),
    }


def _generate_ai_tailoring_plan_data(
    *,
    job: Job,
    score: JobScore,
    profile: CandidateProfile,
    source_document: Document | None,
) -> tuple[dict, list]:
    profile_context = _build_profile_context(profile)
    template_context = _build_template_context(source_document)
    experience_candidates = _all_experience_candidates(profile)
    project_candidates = _all_project_candidates(profile)
    missing_terms = [item.get("required_skill") for item in score.missing_or_weak_skills if item.get("required_skill")]

    system_prompt = (
        "You are the CV Tailoring Agent for CareerOps. "
        "Use only the verified profile evidence, selected job, score evidence, and LaTeX template context provided. "
        "Do not invent any experience, technologies, metrics, responsibilities, projects, dates, or claims. "
        "Select only exact skills from the provided profile skill list, only exact bullets from the provided experience candidates, "
        "and only exact project names from the provided project candidates. "
        "If something is missing or unsupported, omit it and add it to do_not_claim."
    )
    user_prompt = (
        "Create a tailoring plan for the target job using the candidate's verified profile and template style.\n\n"
        f"Job context:\n{json.dumps({'title': job.title, 'company': job.company.name if job.company else None, 'description': job.description, 'location': job.location, 'work_mode': job.work_mode, 'seniority': job.seniority}, ensure_ascii=False)}\n\n"
        f"Score context:\n{json.dumps({'score': score.score, 'recommendation': str(score.recommendation), 'reasons': score.reasons, 'risks': score.risks, 'matched_skills': score.matched_skills, 'missing_or_weak_skills': score.missing_or_weak_skills, 'evidence': score.evidence[:10]}, ensure_ascii=False)}\n\n"
        f"Profile context:\n{json.dumps(profile_context, ensure_ascii=False)}\n\n"
        f"Template context:\n{json.dumps(template_context, ensure_ascii=False)}\n\n"
        f"Experience candidates:\n{json.dumps(experience_candidates, ensure_ascii=False)}\n\n"
        f"Project candidates:\n{json.dumps(project_candidates, ensure_ascii=False)}\n\n"
        f"Unsupported or weak requirements to avoid claiming:\n{json.dumps(missing_terms, ensure_ascii=False)}"
    )
    ai_plan = generate_structured_output(
        schema_model=AICVTailoringPlan,
        schema_name="careerops_cv_tailoring_plan",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=get_settings().openai_cv_model,
    )

    skill_lookup = { _normalize(skill.name): skill.name for skill in profile.skills }
    bullet_lookup = { _normalize(item["bullet"]): item for item in experience_candidates }
    project_lookup = { _normalize(item["project"]): item for item in project_candidates }

    selected_skills: list[str] = []
    for skill in ai_plan.skills_to_prioritize:
        canonical = skill_lookup.get(_normalize(skill))
        if canonical and canonical not in selected_skills:
            selected_skills.append(canonical)

    selected_bullets: list[dict] = []
    for item in ai_plan.experience_bullets_to_reuse:
        canonical = bullet_lookup.get(_normalize(item.bullet))
        if canonical and canonical not in selected_bullets:
            selected_bullets.append(
                {
                    **canonical,
                    "why": item.why,
                    "evidence_text": canonical["evidence_text"],
                }
            )

    selected_projects: list[dict] = []
    for item in ai_plan.projects_to_prioritize:
        canonical = project_lookup.get(_normalize(item.project))
        if canonical and canonical not in selected_projects:
            selected_projects.append(
                {
                    **canonical,
                    "why": item.why,
                    "evidence_text": canonical["evidence_text"],
                }
            )

    changes = [
        {
            "section": change.section,
            "action": change.action,
            "reason": change.reason,
        }
        for change in ai_plan.changes
    ]

    tailoring_plan = {
        "planner": "ai_langgraph_cv_agent",
        "job": {
            "id": str(job.id),
            "title": job.title,
            "company": job.company.name if job.company else None,
        },
        "score": {
            "id": str(score.id),
            "score": score.score,
            "recommendation": score.recommendation,
            "reasons": score.reasons,
            "risks": score.risks,
        },
        "summary_focus": [item.strip() for item in ai_plan.summary_focus if item.strip()],
        "skills_to_prioritize": selected_skills,
        "experience_bullets_to_reuse": selected_bullets,
        "original_experience_section": _extract_original_section(source_document.extracted_text, "Experience")
        if source_document and source_document.extracted_text
        else None,
        "projects_to_prioritize": selected_projects,
        "do_not_claim": [item.strip() for item in ai_plan.do_not_claim if item.strip()],
        "approval_required": True,
        "template_document_id": str(source_document.id) if source_document else None,
        "template_filename": source_document.original_filename if source_document else None,
    }

    if not tailoring_plan["summary_focus"] and score.reasons:
        tailoring_plan["summary_focus"] = score.reasons[:3]

    return tailoring_plan, changes


def create_tailoring_plan(db: Session, job_id: UUID) -> CVVersion | None:
    job = db.get(Job, job_id)
    score = _latest_job_score(db, job_id)
    if not job or not score:
        return None

    profile = _load_profile(db, score.candidate_profile_id)
    if not profile:
        return None

    source_document = _latest_cv_template_document(db)
    try:
        if ai_agents_enabled():
            tailoring_plan, changes = _generate_ai_tailoring_plan_data(
                job=job,
                score=score,
                profile=profile,
                source_document=source_document,
            )
        else:
            tailoring_plan, changes = _build_rule_based_plan_data(
                db,
                job=job,
                score=score,
                profile=profile,
                source_document=source_document,
            )
    except Exception as error:
        tailoring_plan, changes = _build_rule_based_plan_data(
            db,
            job=job,
            score=score,
            profile=profile,
            source_document=source_document,
        )
        tailoring_plan["planner_fallback_reason"] = str(error)

    cv_version = CVVersion(
        job_id=job.id,
        candidate_profile_id=profile.id,
        source_document_id=source_document.id if source_document else None,
        status=CVVersionStatus.PLAN_DRAFT,
        tailoring_plan=tailoring_plan,
        changes=changes,
        generated_file_path=None,
    )
    db.add(cv_version)
    db.flush()
    write_audit_log(
        db,
        event_type="cv.tailoring_plan_created",
        entity_type="cv_version",
        entity_id=cv_version.id,
        details={
            "job_id": str(job.id),
            "score_id": str(score.id),
            "status": cv_version.status,
            "planner": tailoring_plan.get("planner"),
            "planner_fallback_reason": tailoring_plan.get("planner_fallback_reason"),
        },
    )
    db.commit()
    db.refresh(cv_version)
    return cv_version


def list_tailoring_plans(db: Session, job_id: UUID) -> list[CVVersion]:
    return list(db.scalars(select(CVVersion).where(CVVersion.job_id == job_id).order_by(CVVersion.created_at.desc())))


def _render_preview_latex(cv_version: CVVersion) -> str:
    plan = cv_version.tailoring_plan
    job = plan["job"]
    score = plan["score"]
    skills = [_clean_display_term(skill) for skill in plan.get("skills_to_prioritize", [])]
    bullets = plan.get("experience_bullets_to_reuse", [])
    projects = plan.get("projects_to_prioritize", [])
    do_not_claim = plan.get("do_not_claim", [])

    bullet_items = [
        f"{bullet['company']} - {bullet['bullet']} Evidence: {_clean_display_sentence(bullet['why'])}"
        for bullet in bullets
    ]
    project_items = [
        f"{project['project']} - {_clean_display_sentence(project['why'])}"
        for project in projects
    ]
    summary_focus = [_clean_display_sentence(item) for item in plan.get("summary_focus", [])]

    return f"""% CareerOps Agent CV tailoring preview
% This is not a final application CV.
% Human approval is required before generating or sending any tailored CV.
\\documentclass[letterpaper]{{article}}
\\usepackage[margin=0.7in]{{geometry}}
\\usepackage[hidelinks]{{hyperref}}
\\usepackage{{enumitem}}
\\setlist[itemize]{{leftmargin=*, itemsep=2pt, topsep=2pt}}

\\begin{{document}}

\\begin{{center}}
{{\\Large CV Tailoring Preview}}\\\\
{_escape_latex(job.get("title"))} at {_escape_latex(job.get("company"))}\\\\
Score: {_escape_latex(str(score.get("score")))} / 100 \\quad Recommendation: {_escape_latex(str(score.get("recommendation")))}
\\end{{center}}

\\section*{{Human-in-the-loop notice}}
This preview is generated from verified profile sources and must be reviewed before any final CV is produced. It does not add unsupported experience.

\\section*{{Summary focus}}
\\begin{{itemize}}
{_itemize(summary_focus)}
\\end{{itemize}}

\\section*{{Skills to prioritize}}
\\begin{{itemize}}
{_itemize(skills)}
\\end{{itemize}}

\\section*{{Existing experience bullets to reuse}}
\\begin{{itemize}}
{_itemize(bullet_items)}
\\end{{itemize}}

\\section*{{Existing projects to prioritize}}
\\begin{{itemize}}
{_itemize(project_items)}
\\end{{itemize}}

\\section*{{Do not claim without new evidence}}
\\begin{{itemize}}
{_itemize(do_not_claim)}
\\end{{itemize}}

\\end{{document}}
"""


def _latest_generated_plan(db: Session, job_id: UUID) -> CVVersion | None:
    return db.scalar(
        select(CVVersion)
        .where(CVVersion.job_id == job_id)
        .order_by(CVVersion.created_at.desc())
    )


def _load_source_template(db: Session, cv_version: CVVersion) -> str:
    document = (
        db.get(Document, cv_version.source_document_id)
        if cv_version.source_document_id
        else _latest_cv_template_document(db)
    )
    if not document or not document.extracted_text:
        raise ValueError("No source CV template document found.")
    return document.extracted_text


def _render_summary_section(cv_version: CVVersion) -> str:
    plan = cv_version.tailoring_plan
    skills = _unique_clean_terms(plan.get("skills_to_prioritize", []), limit=8)
    job = plan.get("job", {})
    title = str(job.get("title") or "the target role")
    skill_phrase = ", ".join(skills[:6]) if skills else "backend, data, and AI workflow systems"
    metric_fragments = [_compact_metric_phrase(item) for item in _metric_rich_fragments(cv_version, limit=2)]
    metric_sentence = ""
    if metric_fragments:
        metric_sentence = " Evidence: " + "; ".join(metric_fragments) + "."
    sentence = (
        f"Backend-leaning software engineer focused on {skill_phrase} for {title}. "
        "Builds ATS-relevant, production-oriented systems across APIs, data workflows, automation, and traceable AI-enabled product features."
        f"{metric_sentence}"
    )
    return "\\section{Summary}\n" + _escape_latex(sentence)


def _render_skills_section(cv_version: CVVersion) -> str:
    skills = _unique_clean_terms(cv_version.tailoring_plan.get("skills_to_prioritize", []))
    grouped = _group_skills(skills)
    if not grouped:
        grouped = {"Verified skills from source CV": ["Human review required before approval"]}
    items = "\n".join(
        f"""      \\resumeSubItem{{{_escape_latex(label)}}}
        {{{_escape_latex(", ".join(values))}.}}"""
        for label, values in grouped.items()
    )
    return f"""\\section{{Technical Skills}}
  \\resumeSubHeadingListStart
{items}
  \\resumeSubHeadingListEnd"""


def _bullet_label(value: str) -> str:
    normalized = _normalize(value)
    if "13 backend modules" in normalized or "16 prisma" in normalized or "97 route" in normalized:
        return "Scaled backend platform"
    if "react" in normalized or "views" in normalized or "jwt" in normalized or "tanstack" in normalized:
        return "Shipped full-stack workflow UI"
    if "csv" in normalized or "reports" in normalized or "workflow" in normalized or "sla" in normalized:
        return "Automated operational reporting"
    if "swagger" in normalized or "test" in normalized or "debug" in normalized or "throttling" in normalized:
        return "Improved reliability and docs"
    if "postgresql" in normalized or "nestjs" in normalized or "backend" in normalized:
        return "Built backend systems"
    return "Delivered verified impact"


def _render_experience_section(cv_version: CVVersion) -> str:
    bullets = cv_version.tailoring_plan.get("experience_bullets_to_reuse", [])
    if not bullets:
        original_section = cv_version.tailoring_plan.get("original_experience_section")
        if original_section:
            return original_section
        return """\\section{Experience}
  \\resumeSubHeadingListStart
    \\resumeSubheading
      {Verified experience from provided sources}{Human review required}
      {Original experience section retained in source CV}{Review source CV before approval}
      \\resumeItemListStart
        \\resumeItem{No automatic selection}
          {No tailored experience bullets were selected automatically, so this section must be reviewed against the source CV before approval.}
      \\resumeItemListEnd
  \\resumeSubHeadingListEnd"""

    rendered_bullets = "\n".join(
        f"""        \\resumeItem{{{_escape_latex(_bullet_label(item["bullet"]))}}}
          {{{_escape_latex(item["bullet"])}}}"""
        for item in bullets[:4]
    )
    first = bullets[0]
    company = re.sub(r"\s*(--|-|–)\s*(Repository|Project)\s*$", "", first.get("company") or "", flags=re.IGNORECASE)
    location = first.get("location") or "Location from verified source"
    dates = " -- ".join(part for part in [first.get("start_date"), first.get("end_date")] if part) or "Dates from verified source"
    return f"""\\section{{Experience}}
  \\resumeSubHeadingListStart
    \\resumeSubheading
      {{{_escape_latex(company or first.get("company"))}}}{{{_escape_latex(location)}}}
      {{{_escape_latex(first.get("title"))}}}{{{_escape_latex(dates)}}}
      \\resumeItemListStart
{rendered_bullets}
      \\resumeItemListEnd
  \\resumeSubHeadingListEnd"""


def _render_projects_section(cv_version: CVVersion) -> str:
    projects = cv_version.tailoring_plan.get("projects_to_prioritize", [])
    if not projects:
        return "\\section{Selected Projects}\n  \\resumeSubHeadingListStart\n  \\resumeSubHeadingListEnd"

    chunks = []
    for item in projects[:3]:
        existing = item.get("existing_content", {})
        project_name = re.sub(r"\s+Project\s*$", "", item.get("project") or "", flags=re.IGNORECASE)
        technologies = ", ".join(existing.get("technologies") or [])
        description = existing.get("description") or "Verified project from candidate profile."
        impact = existing.get("impact") or item.get("why") or ""
        chunks.append(
            f"""    \\resumeProjectHeading
      {{{_escape_latex(project_name or item.get("project"))}}}{{Project}}
      {{{_escape_latex(description)}}}{{{_escape_latex(technologies)}}}
      \\resumeItemListStart
        \\resumeItem{{Selected impact}}
          {{{_escape_latex(_clean_display_sentence(impact))}}}
      \\resumeItemListEnd"""
        )
    return "\\section{Selected Projects}\n  \\resumeSubHeadingListStart\n" + "\n\n".join(chunks) + "\n  \\resumeSubHeadingListEnd"


def _render_guardrail_comment(cv_version: CVVersion) -> str:
    do_not_claim = cv_version.tailoring_plan.get("do_not_claim", [])
    if not do_not_claim:
        return "% CareerOps honesty guardrail: no unsupported requirements were selected for exclusion in this plan.\n"
    return "% CareerOps honesty guardrail - do not claim without new evidence: " + _clean_render_text(", ".join(do_not_claim)) + "\n"


def _compile_latex_to_pdf(tex_path: Path) -> tuple[Path | None, str | None]:
    compiler = shutil.which("pdflatex") or shutil.which("xelatex")
    if not compiler:
        return None, "No LaTeX compiler found. Install MiKTeX or TeX Live to generate PDFs."

    command = [
        compiler,
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={tex_path.parent}",
        str(tex_path),
    ]
    for _ in range(2):
        result = subprocess.run(
            command,
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            log_path = tex_path.with_suffix(".compile.log")
            log_path.write_text((result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")
            return None, f"LaTeX compilation failed. See {log_path}."

    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        return None, "LaTeX compiler finished but no PDF file was produced."
    return pdf_path, None


def generate_final_latex_from_plan(db: Session, cv_version_id: UUID) -> CVVersion | None:
    cv_version = db.get(CVVersion, cv_version_id)
    if not cv_version:
        return None

    template = _load_source_template(db, cv_version)
    generated = template
    job = cv_version.tailoring_plan.get("job", {})
    if job.get("company"):
        generated = _replace_def(generated, "targetcompany", str(job["company"]))
    if job.get("title"):
        generated = _replace_def(generated, "atsrole", str(job["title"]))
    generated = _replace_section(generated, "Summary", _render_summary_section(cv_version))
    generated = _replace_section(generated, "Technical Skills", _render_skills_section(cv_version))
    generated = _replace_section(generated, "Experience", _render_experience_section(cv_version))
    generated = _replace_section(generated, "Selected Projects", _render_projects_section(cv_version))
    generated = generated.replace("\\begin{document}", "\\begin{document}\n" + _render_guardrail_comment(cv_version), 1)

    output_dir = _storage_root() / "generated" / "cv_final_tex"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{cv_version.id}.tex"
    output_path.write_text(generated, encoding="utf-8")
    pdf_path, pdf_error = _compile_latex_to_pdf(output_path)

    cv_version.status = CVVersionStatus.GENERATED
    cv_version.generated_file_path = str(output_path)
    cv_version.tailoring_plan = {
        **cv_version.tailoring_plan,
        "generated_tex_path": str(output_path),
        "generated_pdf_path": str(pdf_path) if pdf_path else None,
        "pdf_generation_error": pdf_error,
    }
    write_audit_log(
        db,
        event_type="cv.final_latex_generated",
        entity_type="cv_version",
        entity_id=cv_version.id,
        details={
            "generated_file_path": str(output_path),
            "generated_pdf_path": str(pdf_path) if pdf_path else None,
            "pdf_generation_error": pdf_error,
        },
    )
    db.commit()
    db.refresh(cv_version)
    return cv_version


def generate_latex_preview(db: Session, cv_version_id: UUID) -> CVVersion | None:
    cv_version = db.get(CVVersion, cv_version_id)
    if not cv_version:
        return None

    output_dir = _storage_root() / "generated" / "cv_previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{cv_version.id}.tex"
    output_path.write_text(_render_preview_latex(cv_version), encoding="utf-8")

    cv_version.status = CVVersionStatus.GENERATED
    cv_version.generated_file_path = str(output_path)
    write_audit_log(
        db,
        event_type="cv.latex_preview_generated",
        entity_type="cv_version",
        entity_id=cv_version.id,
        details={"generated_file_path": str(output_path)},
    )
    db.commit()
    db.refresh(cv_version)
    return cv_version


def get_cv_artifact_path(db: Session, cv_version_id: UUID, artifact_format: str) -> Path | None:
    cv_version = db.get(CVVersion, cv_version_id)
    if not cv_version:
        return None

    if artifact_format == "tex":
        raw_path = cv_version.generated_file_path or cv_version.tailoring_plan.get("generated_tex_path")
    elif artifact_format == "pdf":
        raw_path = cv_version.tailoring_plan.get("generated_pdf_path")
    else:
        raise ValueError("CV artifact format must be 'tex' or 'pdf'.")

    if not raw_path:
        return None
    path = Path(raw_path).resolve()
    if not path.exists() or not path.is_file():
        return None
    return path


def review_cv_version(
    db: Session,
    cv_version_id: UUID,
    *,
    status: CVVersionStatus,
    review_notes: str | None = None,
) -> CVVersion | None:
    cv_version = db.get(CVVersion, cv_version_id)
    if not cv_version:
        return None
    if status not in {CVVersionStatus.APPROVED, CVVersionStatus.REJECTED}:
        raise ValueError("CV review status must be approved or rejected.")
    if status == CVVersionStatus.APPROVED and not cv_version.generated_file_path:
        raise ValueError("Cannot approve a CV version before generating a file.")

    cv_version.status = status
    cv_version.review_notes = review_notes
    cv_version.reviewed_at = datetime.now(timezone.utc)
    write_audit_log(
        db,
        event_type="cv.reviewed",
        entity_type="cv_version",
        entity_id=cv_version.id,
        details={"status": status, "review_notes": review_notes},
    )
    db.commit()
    db.refresh(cv_version)
    return cv_version
