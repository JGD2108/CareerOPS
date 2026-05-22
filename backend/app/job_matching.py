from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from app.job_discovery import NormalizedDiscoveredJob
from app.models import Job


_NOISE = {
    "inc",
    "llc",
    "ltd",
    "corp",
    "corporation",
    "company",
    "co",
    "sa",
    "sas",
    "s.a",
    "s.a.s",
}


@dataclass
class JobMatchResult:
    confidence: float
    accepted: bool
    needs_review: bool
    reason: str
    evidence: dict


def _normalize(value: str | None) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _without_noise(value: str | None) -> str:
    return " ".join(token for token in _normalize(value).split() if token not in _NOISE)


def _similarity(left: str | None, right: str | None) -> float:
    left_norm = _normalize(left)
    right_norm = _normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _company_similarity(left: str | None, right: str | None) -> float:
    return _similarity(_without_noise(left), _without_noise(right))


def _location_compatibility(left: str | None, right: str | None) -> float:
    left_norm = _normalize(left)
    right_norm = _normalize(right)
    if not left_norm or not right_norm:
        return 0.65
    if left_norm == right_norm:
        return 1.0
    if "remote" in left_norm and "remote" in right_norm:
        return 0.95
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    if left_tokens & right_tokens:
        return 0.82
    return 0.35


def _work_mode_compatibility(left: str | None, right: str | None) -> float:
    left_norm = _normalize(left)
    right_norm = _normalize(right)
    if not left_norm or not right_norm:
        return 0.75
    if left_norm == right_norm:
        return 1.0
    if "remote" in left_norm and "remote" in right_norm:
        return 1.0
    if "hybrid" in left_norm and "hybrid" in right_norm:
        return 1.0
    return 0.55


def match_job_to_posting(job: Job, posting: NormalizedDiscoveredJob) -> JobMatchResult:
    company_name = job.company.name if job.company else None
    title_score = _similarity(job.title, posting.title)
    company_score = _company_similarity(company_name, posting.company_name)
    location_score = _location_compatibility(job.location, posting.location)
    work_mode_score = _work_mode_compatibility(job.work_mode, posting.work_mode)
    active_score = 1.0 if posting.availability_status in {"open", "unknown", None} else 0.35
    source_score = 1.0 if posting.source in {"greenhouse", "lever", "ashby"} else 0.7

    confidence = round(
        title_score * 0.42
        + company_score * 0.24
        + location_score * 0.15
        + work_mode_score * 0.08
        + active_score * 0.06
        + source_score * 0.05,
        3,
    )
    exact_or_strong = title_score >= 0.94 and company_score >= 0.92 and location_score >= 0.82
    accepted = confidence >= 0.90 or (0.70 <= confidence < 0.90 and exact_or_strong)
    needs_review = not accepted and confidence >= 0.70
    reason = (
        f"title={title_score:.2f}, company={company_score:.2f}, "
        f"location={location_score:.2f}, work_mode={work_mode_score:.2f}"
    )
    return JobMatchResult(
        confidence=confidence,
        accepted=accepted,
        needs_review=needs_review,
        reason=reason,
        evidence={
            "title_similarity": title_score,
            "company_similarity": company_score,
            "location_compatibility": location_score,
            "work_mode_compatibility": work_mode_score,
            "active_status": posting.availability_status,
            "source_reliability": source_score,
            "exact_or_strong_match": exact_or_strong,
        },
    )
