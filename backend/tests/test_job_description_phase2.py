from types import SimpleNamespace
from uuid import uuid4

from app import job_description_resolution
from app.job_description_resolution import resolve_job_description, resolve_pending_descriptions
from app.job_discovery import JobDiscoverySourceConfig, NormalizedDiscoveredJob
from app.job_fit import score_job_fit
from app.models import Company, DiscoverySource, Job, JobDescriptionResolutionAttempt
from app.schemas import JobDescriptionResolveResponse


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

    def get(self, *_args, **_kwargs):
        return self.job

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
        "description": "LinkedIn email alert partial metadata only.",
        "description_status": "partial_from_email",
        "description_quality": "low",
        "description_source": "linkedin_email",
        "fetch_status": "pending",
        "resolved_description": None,
        "resolution_confidence": 0.0,
        "company": Company(id=uuid4(), name="Acme"),
    }
    values.update(overrides)
    return Job(**values)


def make_source(source="greenhouse", company_key="acme"):
    return DiscoverySource(
        id=uuid4(),
        source=source,
        company_key=company_key,
        company_name_override="Acme",
        include_description=True,
        create_applications=False,
        is_active=True,
    )


def make_posting(source="greenhouse", title="Data Engineer", company="Acme", location=None):
    return NormalizedDiscoveredJob(
        source=source,
        source_company_key="acme",
        external_job_id=f"{source}-1",
        company_name=company,
        title=title,
        description="Build production data pipelines with Python, SQL, Airflow, cloud warehouses, testing, and stakeholder collaboration. " * 5,
        location=location,
        work_mode=None,
        seniority=None,
        job_url=f"https://jobs.example.com/{source}/1",
        posted_at=None,
        application_deadline=None,
        availability_status="open",
        availability_reason=None,
        raw_payload={"id": f"{source}-1"},
    )


def test_greenhouse_job_resolves_full_description(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[make_source("greenhouse")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [make_posting("greenhouse")])

    result = resolve_job_description(db, job.id)

    assert result["status"] == "success"
    assert job.description_status == "resolved_from_ats"
    assert job.description_source == "greenhouse"
    assert job.description_quality == "high"
    assert job.fetch_status == "success"
    assert job.resolution_confidence >= 0.90
    assert job.resolved_description_url == "https://jobs.example.com/greenhouse/1"


def test_lever_job_resolves_full_description(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[make_source("lever")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [make_posting("lever")])

    resolve_job_description(db, job.id)

    assert job.description_status == "resolved_from_ats"
    assert job.description_source == "lever"


def test_ashby_job_resolves_full_description(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[make_source("ashby")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [make_posting("ashby")])

    resolve_job_description(db, job.id)

    assert job.description_status == "resolved_from_ats"
    assert job.description_source == "ashby"


def test_linkedin_alert_can_be_enriched_from_matching_ats_posting(monkeypatch):
    job = make_job(source="linkedin_email_alert")
    db = FakeSession(job=job, sources=[make_source("greenhouse")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [make_posting("greenhouse")])

    result = resolve_job_description(db, job.id)

    assert result["status"] == "success"
    assert job.description_source == "greenhouse"
    assert "description_resolution" in job.raw_payload


def test_low_confidence_match_is_not_auto_attached(monkeypatch):
    job = make_job(title="Data Engineer")
    db = FakeSession(job=job, sources=[make_source("greenhouse")])
    monkeypatch.setattr(
        job_description_resolution,
        "_fetch_jobs",
        lambda *_args, **_kwargs: [make_posting("greenhouse", title="Product Marketing Manager", company="Other Co")],
    )

    result = resolve_job_description(db, job.id)

    assert result["status"] == "not_found"
    assert job.description_status == "partial_from_email"
    assert job.resolved_description is None


def test_unmatched_job_becomes_not_found(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[make_source("greenhouse")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [])

    result = resolve_job_description(db, job.id)

    assert result["status"] == "not_found"
    assert job.fetch_status == "not_found"


def test_resolver_writes_resolution_attempt(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[make_source("greenhouse")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [make_posting("greenhouse")])

    result = resolve_job_description(db, job.id)

    assert result["attempts"]
    assert any(isinstance(item, JobDescriptionResolutionAttempt) for item in db.added)


def test_resolve_description_output_validates(monkeypatch):
    job = make_job()
    db = FakeSession(job=job, sources=[make_source("greenhouse")])
    monkeypatch.setattr(job_description_resolution, "_fetch_jobs", lambda *_args, **_kwargs: [make_posting("greenhouse")])

    result = resolve_job_description(db, job.id)
    response = JobDescriptionResolveResponse.model_validate(result)

    assert str(response.job_id) == str(job.id)
    assert response.status == "success"
    assert response.description_source == "greenhouse"


def test_resolve_pending_processes_only_eligible_jobs(monkeypatch):
    eligible = make_job()
    already_complete = make_job(
        description_status="manually_provided",
        description_quality="high",
        fetch_status="success",
        resolved_description="Complete description " * 30,
    )
    db = FakeSession(jobs=[eligible])
    seen = []

    def fake_resolve(_db, job_id):
        seen.append(job_id)
        return {"job_id": str(job_id), "status": "success", "notes": "ok"}

    monkeypatch.setattr(job_description_resolution, "resolve_job_description", fake_resolve)

    summary = resolve_pending_descriptions(db, limit=10)

    assert seen == [eligible.id]
    assert already_complete.id not in seen
    assert summary["resolved_count"] == 1
    assert summary["processed_count"] == 1


def test_final_scoring_allowed_after_successful_resolution(monkeypatch):
    job = make_job(
        description_status="resolved_from_ats",
        description_quality="high",
        description_source="greenhouse",
        fetch_status="success",
        resolved_description="Python SQL Airflow FastAPI data pipelines analytics cloud. " * 8,
    )
    db = FakeSession(job=job)
    monkeypatch.setattr(
        "app.job_fit.get_profile",
        lambda _db: SimpleNamespace(
            id=uuid4(),
            skills=[
                SimpleNamespace(
                    name="Python",
                    aliases=[],
                    evidence_level="strong",
                    evidence_text="Profile evidence for Python.",
                )
            ],
        ),
    )

    score = score_job_fit(db, job.id)

    assert score is not None
    assert score.extracted_requirements["description_status"] == "resolved_from_ats"
    assert not score.extracted_requirements["preliminary"]
