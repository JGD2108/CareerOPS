from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import gmail_integration
from app.gmail_integration import _create_or_get_linkedin_job
from app.job_description_resolution import save_manual_job_description
from app.job_fit import score_job_fit
from app.models import Email, Job, JobDescriptionResolutionAttempt, RawEmail


class FakeSession:
    def __init__(self, scalar_result=None, get_result=None):
        self.scalar_result = scalar_result
        self.get_result = get_result
        self.added = []
        self.committed = False

    def scalar(self, *_args, **_kwargs):
        return self.scalar_result

    def get(self, *_args, **_kwargs):
        return self.get_result

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def refresh(self, _item):
        return None


def _job(**overrides):
    values = {
        "id": uuid4(),
        "title": "Data Engineer",
        "source": "manual",
        "description": "Build data pipelines with Python, SQL, Airflow, and cloud services. " * 8,
        "description_status": "manually_provided",
        "description_quality": "high",
        "description_source": "manual_paste",
        "fetch_status": "success",
        "resolved_description": "Build data pipelines with Python, SQL, Airflow, and cloud services. " * 8,
    }
    values.update(overrides)
    return Job(**values)


def _linkedin_email():
    raw_email = RawEmail(
        id=uuid4(),
        gmail_message_id="msg-1",
        gmail_thread_id="thread-1",
        history_id="history-1",
        label_ids=[],
        raw_payload={},
    )
    return Email(
        id=uuid4(),
        raw_email_id=raw_email.id,
        raw_email=raw_email,
        from_email="jobalerts-noreply@linkedin.com",
        subject="LinkedIn Job Alert",
        snippet="Data Engineer at Acme",
        body_text="Data Engineer at Acme",
    )


def test_linkedin_gmail_alert_job_becomes_partial_from_email(monkeypatch):
    created_job = _job(
        source="linkedin_email_alert",
        description_status="missing",
        description_quality="unknown",
        description_source=None,
        fetch_status="pending",
        resolved_description=None,
    )

    monkeypatch.setattr(gmail_integration.crud, "create_job", lambda *_args, **_kwargs: created_job)
    monkeypatch.setattr(gmail_integration, "scrape_job_page_with_selenium", lambda _url: pytest.fail("LinkedIn should not be scraped"))

    job, job_created, _, _ = _create_or_get_linkedin_job(
        FakeSession(),
        title="Data Engineer",
        company="Acme",
        source_url="https://www.linkedin.com/comm/jobs/view/123/",
        source="linkedin_email_alert",
        email_record=_linkedin_email(),
        application_status=None,
    )

    assert job_created is True
    assert job.description_status == "partial_from_email"
    assert job.description_quality == "low"
    assert job.description_source == "linkedin_email"
    assert job.fetch_status == "pending"
    assert job.resolution_confidence == 0.0
    assert job.resolved_description is None
    assert job.raw_payload["email_snippet"] == "Data Engineer at Acme"


def test_manual_pasted_description_updates_status_and_writes_attempt():
    job = _job(
        description_status="partial_from_email",
        description_quality="low",
        description_source="linkedin_email",
        fetch_status="pending",
        resolved_description=None,
    )
    db = FakeSession(scalar_result=job)
    description = "Official role description with Python, SQL, Airflow, cloud data pipelines, ownership, and stakeholder collaboration. " * 5

    result = save_manual_job_description(db, job.id, description=description, source_url="https://example.com/job")

    assert result is not None
    updated_job, attempt = result
    assert updated_job.description_status == "manually_provided"
    assert updated_job.description_quality == "high"
    assert updated_job.description_source == "manual_paste"
    assert updated_job.fetch_status == "success"
    assert updated_job.resolved_description == description.strip()
    assert isinstance(attempt, JobDescriptionResolutionAttempt)
    assert attempt.attempted_source == "manual_paste"
    assert attempt.status == "success"
    assert any(isinstance(item, JobDescriptionResolutionAttempt) for item in db.added)
    assert db.committed is True


def test_final_scoring_refuses_incomplete_description(monkeypatch):
    incomplete_job = _job(
        description_status="partial_from_email",
        description_quality="low",
        description_source="linkedin_email",
        fetch_status="pending",
        resolved_description=None,
    )
    db = FakeSession(get_result=incomplete_job)
    monkeypatch.setattr("app.job_fit.get_profile", lambda _db: SimpleNamespace(id=uuid4(), skills=[]))

    with pytest.raises(ValueError, match="partial metadata"):
        score_job_fit(db, incomplete_job.id)
