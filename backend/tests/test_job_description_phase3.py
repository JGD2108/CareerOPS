from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import job_description_resolution
from app.job_description_resolution import (
    accept_resolution_candidate,
    reject_resolution_candidate,
    resolve_job_description,
    resolve_manual_job_url,
)
from app.job_description_state import description_is_complete, incomplete_description_reason
from app.job_fit import score_job_fit
from app.models import Company, Job, JobDescriptionResolutionAttempt
from app.schemas import ManualJobDescriptionRequest


class FakeScalarResult:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        return iter(self.items)


class FakeSession:
    def __init__(self, *, job=None, sources=None, jobs=None):
        self.job = job
        self.sources = sources or []
        self.jobs = jobs or []
        self.added = []
        self.committed = False

    def scalar(self, *_args, **_kwargs):
        return self.job

    def scalars(self, *_args, **_kwargs):
        return FakeScalarResult(self.jobs or self.sources)

    def get(self, _model, item_id):
        for item in self.added:
            if getattr(item, "id", None) == item_id:
                return item
        return self.job if getattr(self.job, "id", None) == item_id else None

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def refresh(self, _item):
        return None


def make_job(**overrides):
    values = {
        "id": uuid4(),
        "title": "Data Engineer",
        "source": "linkedin_email_alert",
        "source_url": "https://www.linkedin.com/jobs/view/123/",
        "description": "LinkedIn email alert partial metadata only.",
        "description_status": "partial_from_email",
        "description_quality": "low",
        "description_source": "linkedin_email",
        "fetch_status": "pending",
        "resolved_description": None,
        "resolution_confidence": 0.0,
        "company": Company(id=uuid4(), name="Acme", website_url="https://acme.example"),
    }
    values.update(overrides)
    return Job(**values)


def fetched_success(url="https://acme.example/careers/data-engineer", confidence=0.91):
    return {
        "status": "success",
        "reason": "Public page contains a plausible target job description.",
        "description": "Data Engineer role at Acme. Responsibilities include Python, SQL, Airflow, cloud data pipelines, testing, analytics, and stakeholder collaboration. Requirements include production data engineering experience. " * 5,
        "description_html": "<html><body>Data Engineer role at Acme</body></html>",
        "final_url": url,
        "quality": "high",
        "confidence": confidence,
        "metadata": {"description_length": 900, "title_token_hits": 2},
    }


def test_manual_official_url_resolves_public_job_page(monkeypatch):
    job = make_job()
    db = FakeSession(job=job)
    monkeypatch.setattr(job_description_resolution, "_fetch_public_job_page", lambda *_args, **_kwargs: fetched_success())

    result = resolve_manual_job_url(db, job.id, url="https://acme.example/careers/data-engineer")

    assert result is not None
    assert job.description_status == "manually_provided_url"
    assert job.description_source == "manual_url"
    assert job.fetch_status == "success"
    assert job.resolved_description_url == "https://acme.example/careers/data-engineer"
    assert any(item.attempted_source == "manual_url" and item.status == "success" for item in db.added)


def test_manual_url_rejects_linkedin_url():
    job = make_job()
    db = FakeSession(job=job)

    resolve_manual_job_url(db, job.id, url="https://www.linkedin.com/jobs/view/123/")

    attempt = db.added[-1]
    assert attempt.status == "rejected"
    assert "LinkedIn" in attempt.reason
    assert job.description_status == "partial_from_email"


def test_manual_url_rejects_login_blocked_captcha_like_page(monkeypatch):
    job = make_job()
    db = FakeSession(job=job)
    monkeypatch.setattr(
        job_description_resolution,
        "_fetch_public_job_page",
        lambda *_args, **_kwargs: {
            "status": "rejected",
            "reason": "Page appears to contain a CAPTCHA or bot challenge.",
            "confidence": 0.0,
        },
    )

    resolve_manual_job_url(db, job.id, url="https://acme.example/careers/data-engineer")

    assert db.added[-1].status == "rejected"
    assert "CAPTCHA" in db.added[-1].reason


def test_manual_url_rejects_low_quality_generic_page(monkeypatch):
    job = make_job()
    db = FakeSession(job=job)
    monkeypatch.setattr(
        job_description_resolution,
        "_fetch_public_job_page",
        lambda *_args, **_kwargs: {
            "status": "rejected",
            "reason": "Page looks like a generic or low-detail careers page.",
            "confidence": 0.42,
            "metadata": {"description_length": 120},
        },
    )

    resolve_manual_job_url(db, job.id, url="https://acme.example/careers")

    assert db.added[-1].status == "rejected"
    assert "generic" in db.added[-1].reason


def test_safe_company_careers_resolver_stores_successful_description(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[])
    monkeypatch.setattr(job_description_resolution, "_fetch_public_job_page", lambda *_args, **_kwargs: fetched_success())

    result = resolve_job_description(db, job.id)

    assert result["status"] == "success"
    assert job.description_status == "resolved_from_company_site"
    assert job.description_source == "company_careers"
    assert job.fetch_status == "success"


def test_company_careers_resolver_marks_needs_manual_review_when_uncertain(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[])
    monkeypatch.setattr(
        job_description_resolution,
        "_fetch_public_job_page",
        lambda *_args, **_kwargs: {"status": "rejected", "reason": "No specific target role found.", "confidence": 0.2},
    )

    result = resolve_job_description(db, job.id)

    assert result["status"] == "needs_manual_review"
    assert job.fetch_status == "needs_manual_review"
    assert job.resolved_description is None


def test_medium_confidence_candidate_is_not_auto_attached(monkeypatch):
    from app.job_discovery import JobDiscoverySourceConfig, NormalizedDiscoveredJob

    job = make_job(title="Data Engineer")
    db = FakeSession(job=job, sources=[SimpleNamespace(source="greenhouse", company_key="acme", company_name_override="Acme")])
    posting = NormalizedDiscoveredJob(
        source="greenhouse",
        source_company_key="acme",
        external_job_id="gh-1",
        company_name="Acme",
        title="Senior Data Engineer",
        description=fetched_success()["description"],
        location=None,
        work_mode=None,
        seniority=None,
        job_url="https://boards.greenhouse.io/acme/jobs/1",
        posted_at=None,
        application_deadline=None,
        availability_status="open",
        availability_reason=None,
        raw_payload={"id": "gh-1"},
    )
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [posting])
    monkeypatch.setattr(job_description_resolution, "_fetch_public_job_page", lambda *_args, **_kwargs: {"status": "rejected", "reason": "skip", "confidence": 0.0})

    result = resolve_job_description(db, job.id)

    assert result["status"] == "needs_manual_review"
    assert job.description_status == "partial_from_email"
    assert any(item.status == "needs_manual_review" for item in db.added)


def test_user_can_accept_candidate_description(monkeypatch):
    job = make_job()
    attempt = JobDescriptionResolutionAttempt(
        id=uuid4(),
        job_id=job.id,
        attempted_source="greenhouse",
        attempted_url="https://boards.greenhouse.io/acme/jobs/1",
        status="needs_manual_review",
        confidence=0.82,
        reason="Medium confidence candidate.",
        attempt_metadata={
            "candidate_source": "greenhouse",
            "company_key": "acme",
            "posting_title": "Senior Data Engineer",
            "posting_company": "Acme",
            "posting_location": "Remote",
            "candidate_description": fetched_success()["description"],
            "evidence": {"title_similarity": 0.8},
        },
    )
    db = FakeSession(job=job)
    db.added.append(attempt)

    result = accept_resolution_candidate(db, job.id, attempt.id)

    assert result is not None
    assert job.description_status == "resolved_from_ats"
    assert job.resolved_description
    assert job.fetch_status == "success"


def test_resolution_attempt_history_is_returned():
    job = make_job()
    attempt = JobDescriptionResolutionAttempt(
        id=uuid4(),
        job_id=job.id,
        attempted_source="manual_url",
        attempted_url="https://acme.example/careers/data-engineer",
        status="success",
        confidence=0.91,
        reason="Resolved.",
    )
    db = FakeSession(jobs=[attempt])

    history = job_description_resolution.list_resolution_attempts(db, job.id)

    assert history == [attempt]
    assert history[0].attempted_url == "https://acme.example/careers/data-engineer"


def test_final_scoring_allowed_after_manual_url_success(monkeypatch):
    job = make_job(
        description_status="manually_provided_url",
        description_quality="high",
        description_source="manual_url",
        fetch_status="success",
        resolved_description=fetched_success()["description"],
    )
    db = FakeSession(job=job)
    monkeypatch.setattr(
        "app.job_fit.get_profile",
        lambda _db: SimpleNamespace(
            id=uuid4(),
            skills=[SimpleNamespace(name="Python", aliases=[], evidence_level="strong", evidence_text="Python evidence.")],
        ),
    )

    score = score_job_fit(db, job.id)

    assert score is not None
    assert not score.extracted_requirements["preliminary"]


def test_no_linkedin_credentials_cookies_selenium_or_auth_scraping_introduced():
    source = job_description_resolution.__loader__.get_source(job_description_resolution.__name__)

    assert "selenium" not in source.lower()
    assert "linkedin.com/login" not in source.lower()
    assert "cookie" not in source.lower()
    assert "captcha bypass" not in source.lower()


@pytest.mark.parametrize(
    ("description_status", "fetch_status", "quality", "complete"),
    [
        ("missing", "pending", "unknown", False),
        ("partial_from_email", "pending", "low", False),
        ("resolved_from_ats", "success", "high", True),
        ("resolved_from_company_site", "success", "medium", True),
        ("manually_provided", "success", "high", True),
        ("manually_provided_url", "success", "high", True),
        ("failed", "error", "unknown", False),
    ],
)
def test_description_status_gate_matrix(description_status, fetch_status, quality, complete):
    job = make_job(
        description_status=description_status,
        fetch_status=fetch_status,
        description_quality=quality,
        resolved_description=fetched_success()["description"] if complete else None,
        description=fetched_success()["description"] if complete else "Partial metadata only.",
    )

    assert description_is_complete(job) is complete


def test_needs_manual_review_has_actionable_blocking_reason():
    job = make_job(fetch_status="needs_manual_review")

    assert "Accept a resolver candidate" in incomplete_description_reason(job)
    assert "official public job URL" in incomplete_description_reason(job)


def test_accepting_attempt_from_wrong_job_fails():
    job = make_job()
    other_job_id = uuid4()
    attempt = JobDescriptionResolutionAttempt(
        id=uuid4(),
        job_id=other_job_id,
        attempted_source="greenhouse",
        attempted_url="https://boards.greenhouse.io/acme/jobs/1",
        status="needs_manual_review",
        confidence=0.82,
        reason="Medium confidence candidate.",
        attempt_metadata={"candidate_description": fetched_success()["description"]},
    )
    db = FakeSession(job=job)
    db.added.append(attempt)

    assert accept_resolution_candidate(db, job.id, attempt.id) is None


def test_rejecting_attempt_from_wrong_job_fails():
    job = make_job()
    attempt = JobDescriptionResolutionAttempt(
        id=uuid4(),
        job_id=uuid4(),
        attempted_source="greenhouse",
        status="needs_manual_review",
        confidence=0.82,
    )
    db = FakeSession(job=job)
    db.added.append(attempt)

    assert reject_resolution_candidate(db, job.id, attempt.id) is None


def test_manual_url_does_not_overwrite_high_quality_resolved_description(monkeypatch):
    original_description = "Resolved public ATS description with Python, SQL, Airflow, cloud pipelines, and requirements. " * 5
    job = make_job(
        description_status="resolved_from_ats",
        description_quality="high",
        description_source="greenhouse",
        fetch_status="success",
        resolved_description=original_description,
        description=original_description,
        resolution_confidence=0.96,
    )
    db = FakeSession(job=job)
    monkeypatch.setattr(job_description_resolution, "_fetch_public_job_page", lambda *_args, **_kwargs: fetched_success())

    resolve_manual_job_url(db, job.id, url="https://acme.example/careers/other")

    assert job.resolved_description == original_description
    assert db.added[-1].status == "rejected"
    assert "already has a high-quality resolved description" in db.added[-1].reason


def test_manual_paste_schema_rejects_extremely_short_description():
    with pytest.raises(ValidationError):
        ManualJobDescriptionRequest(description="Too short")


def test_scoring_remains_blocked_for_partial_from_email(monkeypatch):
    job = make_job(description_status="partial_from_email", description_quality="low", resolved_description=None)
    db = FakeSession(job=job)
    monkeypatch.setattr("app.job_fit.get_profile", lambda _db: SimpleNamespace(id=uuid4(), skills=[]))

    with pytest.raises(ValueError, match="partial metadata"):
        score_job_fit(db, job.id)


def test_scoring_allowed_after_high_quality_resolved_description(monkeypatch):
    job = make_job(
        description_status="resolved_from_company_site",
        description_quality="high",
        description_source="company_careers",
        fetch_status="success",
        resolved_description=fetched_success()["description"],
        description=fetched_success()["description"],
    )
    db = FakeSession(job=job)
    monkeypatch.setattr(
        "app.job_fit.get_profile",
        lambda _db: SimpleNamespace(
            id=uuid4(),
            skills=[SimpleNamespace(name="Python", aliases=[], evidence_level="strong", evidence_text="Python evidence.")],
        ),
    )

    assert score_job_fit(db, job.id) is not None
