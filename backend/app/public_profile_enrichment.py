from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.models import CandidateProfile, ProfileProject, ProfileSource, SourceType
from app.profile_ingestion import get_profile
from app.text_normalization import normalize_display_list, normalize_display_text, normalize_text_block


@dataclass(frozen=True)
class PublicProjectEvidence:
    name: str
    description: str | None
    impact: str | None
    technologies: list[str]
    evidence_text: str
    source_type: SourceType
    project_url: str | None = None
    repo_url: str | None = None
    metric_bullets: list[str] | None = None


@dataclass(frozen=True)
class SourceIngestionFailure:
    source_type: str
    source_url: str
    reason: str


@dataclass(frozen=True)
class PublicSourceEnrichmentResult:
    projects_added: int
    projects_updated: int
    failures: list[SourceIngestionFailure]


def _normalize(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _repo_fingerprint(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().replace("www.", "")
    path = parsed.path.strip("/").lower()
    return f"{host}/{path}"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)

    def as_text(self) -> str:
        return normalize_text_block(" ".join(self.text_parts)) or ""


_TECH_TOKENS = {
    "python", "fastapi", "flask", "django", "react", "typescript", "javascript", "node", "postgres",
    "redis", "docker", "kubernetes", "aws", "gcp", "azure", "sql", "pandas", "numpy", "langchain", "openai",
}
_METRIC_PATTERN = re.compile(
    r"(?i)(\b\d+(?:\.\d+)?\s?(?:%|ms|s|sec|seconds|minutes|hrs|hours|x|k|m)\b|\b\d{1,3}(?:,\d{3})+\b|\b\d+\s?(?:users?|requests?|rps|qps|ops|throughput|latency|revenue)\b)"
)


def _extract_metric_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        clean = normalize_text_block(sentence) or ""
        if not clean:
            continue
        if _METRIC_PATTERN.search(clean):
            bullets.append(clean)
    return bullets[:6]


def _extract_technologies(*texts: str) -> list[str]:
    joined = " ".join(texts).lower()
    found = [token for token in sorted(_TECH_TOKENS) if re.search(rf"\b{re.escape(token)}\b", joined)]
    return found


def _fetch_github_projects(github_profile_url: str) -> tuple[list[PublicProjectEvidence], list[SourceIngestionFailure]]:
    failures: list[SourceIngestionFailure] = []
    parsed = urlparse(github_profile_url)
    username = parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else ""
    if parsed.netloc.lower() not in {"github.com", "www.github.com"} or not username:
        return [], [SourceIngestionFailure(source_type="github", source_url=github_profile_url, reason="Invalid GitHub profile URL")]

    headers = {"User-Agent": "CareerOpsAgent/0.1 public-profile-enrichment"}
    projects: list[PublicProjectEvidence] = []
    with httpx.Client(timeout=15.0, headers=headers) as client:
        repos_res = client.get(f"https://api.github.com/users/{username}/repos", params={"type": "owner", "per_page": 100, "sort": "updated"})
        if repos_res.status_code >= 400:
            return [], [SourceIngestionFailure(source_type="github", source_url=github_profile_url, reason=f"GitHub repos request failed ({repos_res.status_code})")]
        repos = repos_res.json()
        for repo in repos:
            if repo.get("fork") or repo.get("private"):
                continue
            repo_url = repo.get("html_url")
            readme_text = ""
            readme_res = client.get(
                f"https://api.github.com/repos/{username}/{repo.get('name')}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw"},
            )
            if readme_res.status_code < 400:
                readme_text = normalize_text_block(readme_res.text) or ""
            combined_evidence = " ".join([repo.get("description") or "", readme_text]).strip()
            if not combined_evidence:
                continue
            metrics = _extract_metric_bullets(combined_evidence)
            projects.append(
                PublicProjectEvidence(
                    name=normalize_display_text(repo.get("name"), fallback=repo.get("name")) or repo.get("name"),
                    description=normalize_display_text(repo.get("description")),
                    impact=normalize_display_text(readme_text[:400]) if readme_text else None,
                    technologies=_extract_technologies(repo.get("language") or "", repo.get("topics") and " ".join(repo["topics"]) or "", combined_evidence),
                    evidence_text=combined_evidence[:2000],
                    source_type=SourceType.GITHUB,
                    project_url=repo_url,
                    repo_url=repo_url,
                    metric_bullets=metrics or None,
                )
            )
    return projects, failures


def _fetch_portfolio_projects(url: str) -> tuple[list[PublicProjectEvidence], list[SourceIngestionFailure]]:
    try:
        response = httpx.get(url, timeout=15.0, follow_redirects=True, headers={"User-Agent": "CareerOpsAgent/0.1 public-profile-enrichment"})
    except Exception as exc:  # pragma: no cover - network failure branch
        return [], [SourceIngestionFailure(source_type="portfolio", source_url=url, reason=str(exc))]
    if response.status_code >= 400:
        return [], [SourceIngestionFailure(source_type="portfolio", source_url=url, reason=f"HTTP {response.status_code}")]

    parser = _TextExtractor()
    parser.feed(response.text)
    text = parser.as_text()
    if not text:
        return [], [SourceIngestionFailure(source_type="portfolio", source_url=url, reason="No extractable text")]

    segments = re.split(r"(?i)\bproject\b", text)
    if len(segments) <= 1:
        segments = [text]
    projects: list[PublicProjectEvidence] = []
    domain = urlparse(url).netloc.lower().replace("www.", "")
    for segment in segments[:8]:
        clean = normalize_text_block(segment) or ""
        if len(clean) < 50:
            continue
        name_match = re.match(r"^([A-Za-z0-9][A-Za-z0-9 .:_-]{2,80})", clean)
        name = name_match.group(1).strip() if name_match else f"Portfolio project ({domain})"
        metrics = _extract_metric_bullets(clean)
        projects.append(
            PublicProjectEvidence(
                name=name,
                description=clean[:220],
                impact=clean[:420],
                technologies=_extract_technologies(clean),
                evidence_text=clean[:2000],
                source_type=SourceType.PORTFOLIO,
                project_url=url,
                metric_bullets=metrics or None,
            )
        )
    return projects, []


def _project_keys(project: ProfileProject) -> tuple[str, str]:
    project_name = _normalize(project.name)
    fingerprint = _repo_fingerprint(project.repo_url or project.project_url)
    return project_name, fingerprint


def _evidence_project_keys(project: PublicProjectEvidence) -> tuple[str, str]:
    return _normalize(project.name), _repo_fingerprint(project.repo_url or project.project_url)


def _record_source(db: Session, profile_id, project: ProfileProject, evidence: PublicProjectEvidence, confidence: int) -> None:
    db.add(
        ProfileSource(
            candidate_profile_id=profile_id,
            document_id=None,
            source_type=evidence.source_type,
            field_name="profile_projects",
            extracted_value={
                "name": project.name,
                "description": project.description,
                "impact": project.impact,
                "technologies": project.technologies,
                "project_url": project.project_url,
                "repo_url": project.repo_url,
                "metric_bullets": project.metric_bullets,
            },
            evidence_text=evidence.evidence_text,
            confidence=confidence,
        )
    )


def save_public_source_preferences(
    db: Session, *, github_profile_url: str | None, portfolio_urls: list[str]
) -> CandidateProfile:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.created_at.asc()))
    if not profile:
        profile = CandidateProfile()
        db.add(profile)
        db.flush()
    profile.preferences = {
        **(profile.preferences or {}),
        "github_profile_url": github_profile_url,
        "portfolio_urls": portfolio_urls,
    }
    db.commit()
    return get_profile(db) or profile


def enrich_profile_from_public_sources(db: Session) -> tuple[CandidateProfile, PublicSourceEnrichmentResult]:
    profile = db.scalar(select(CandidateProfile).order_by(CandidateProfile.created_at.asc()))
    if not profile:
        raise ValueError("Candidate profile not found. Build or extract your profile first.")

    preferences = profile.preferences or {}
    github_profile_url = preferences.get("github_profile_url")
    portfolio_urls = preferences.get("portfolio_urls")
    portfolio_urls = [item for item in portfolio_urls if isinstance(item, str)] if isinstance(portfolio_urls, list) else []
    has_github = isinstance(github_profile_url, str) and github_profile_url.strip()
    if not has_github and not portfolio_urls:
        raise ValueError("No public sources configured. Save GitHub/portfolio URLs in profile preferences first.")

    evidences: list[PublicProjectEvidence] = []
    failures: list[SourceIngestionFailure] = []
    if has_github:
        gh_projects, gh_failures = _fetch_github_projects(github_profile_url.strip())
        evidences.extend(gh_projects)
        failures.extend(gh_failures)
    for url in portfolio_urls:
        projects, url_failures = _fetch_portfolio_projects(url)
        evidences.extend(projects)
        failures.extend(url_failures)

    existing_projects = list(
        db.scalars(select(ProfileProject).where(ProfileProject.candidate_profile_id == profile.id))
    )
    key_to_project = {_project_keys(item): item for item in existing_projects}
    added = 0
    updated = 0
    for evidence in evidences:
        key = _evidence_project_keys(evidence)
        current = key_to_project.get(key)
        if current is None and key[1]:
            current = next((p for p in existing_projects if _project_keys(p)[1] == key[1]), None)
        if current is None and key[0]:
            current = next((p for p in existing_projects if _project_keys(p)[0] == key[0]), None)

        if current is None:
            current = ProfileProject(
                candidate_profile_id=profile.id,
                source_document_id=None,
                source_type=evidence.source_type,
                name=evidence.name,
                description=evidence.description,
                technologies=evidence.technologies,
                impact=evidence.impact,
                evidence_text=evidence.evidence_text,
                project_url=evidence.project_url,
                repo_url=evidence.repo_url,
                metric_bullets=evidence.metric_bullets,
            )
            db.add(current)
            db.flush()
            existing_projects.append(current)
            key_to_project[_project_keys(current)] = current
            _record_source(db, profile.id, current, evidence, 85)
            added += 1
            continue

        changed = False
        if not current.description and evidence.description:
            current.description = evidence.description
            changed = True
        if not current.impact and evidence.impact:
            current.impact = evidence.impact
            changed = True
        if not current.project_url and evidence.project_url:
            current.project_url = evidence.project_url
            changed = True
        if not current.repo_url and evidence.repo_url:
            current.repo_url = evidence.repo_url
            changed = True
        merged_tech = sorted(set(normalize_display_list(current.technologies) or []).union(evidence.technologies))
        if merged_tech and merged_tech != (normalize_display_list(current.technologies) or []):
            current.technologies = merged_tech
            changed = True
        if evidence.metric_bullets:
            existing_metrics = normalize_display_list(current.metric_bullets) or []
            merged_metrics = list(dict.fromkeys(existing_metrics + evidence.metric_bullets))
            if merged_metrics != existing_metrics:
                current.metric_bullets = merged_metrics
                changed = True
        if changed:
            updated += 1
        _record_source(db, profile.id, current, evidence, 70 if changed else 60)

    write_audit_log(
        db,
        event_type="profile.public_sources.enriched",
        entity_type="candidate_profile",
        entity_id=profile.id,
        details={
            "projects_added": added,
            "projects_updated": updated,
            "failures": [failure.__dict__ for failure in failures],
        },
    )
    db.commit()
    refreshed = get_profile(db)
    if not refreshed:
        raise ValueError("Candidate profile not found after enrichment.")
    return refreshed, PublicSourceEnrichmentResult(projects_added=added, projects_updated=updated, failures=failures)
