from types import SimpleNamespace
from uuid import uuid4

from app import job_availability
from app.job_availability import classify_availability_from_response
from app.job_controls import build_job_fingerprints, is_excluded_company_name
from app.models import Job


class FakeDb:
    def __init__(self, job):
        self.job = job
        self.commits = 0

    def get(self, _model, _id):
        return self.job

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


def test_build_job_fingerprints_prefers_multiple_matching_strategies():
    fingerprints = build_job_fingerprints(
        source="linkedin_email_alert",
        source_company_key="linkedin",
        external_job_id="123456",
        source_url="https://www.linkedin.com/jobs/view/123456/",
        company_name="Acme Corp",
        title="Backend Engineer",
    )

    assert len(fingerprints) == 3
    assert len(set(fingerprints)) == 3


def test_classify_availability_marks_closed_pages():
    status, reason = classify_availability_from_response(
        "https://www.linkedin.com/jobs/view/123456/",
        200,
        "https://www.linkedin.com/jobs/view/123456/",
        "This job is no longer accepting applications.",
    )

    assert status == "closed"
    assert "no longer available" in reason.lower()


def test_classify_availability_marks_open_pages():
    status, reason = classify_availability_from_response(
        "https://example.com/jobs/backend-engineer",
        200,
        "https://example.com/jobs/backend-engineer",
        "Apply now for this job and submit application today.",
    )

    assert status == "open"
    assert "application" in reason.lower()


def test_exact_hired_company_is_excluded_but_hire_feed_is_not():
    assert is_excluded_company_name("Hired") is True
    assert is_excluded_company_name("HIRED") is True
    assert is_excluded_company_name("Hire Feed") is False


def test_availability_check_skips_browser_scraper_when_flag_disabled(monkeypatch):
    job = Job(id=uuid4(), title="Backend Engineer", description="Apply now", source_url="https://example.com/job")
    fake_db = FakeDb(job)
    called = False

    def fail_if_called(_url):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(job_availability.settings, "enable_browser_job_checks", False)
    monkeypatch.setattr(job_availability, "scrape_job_page_with_selenium", fail_if_called)

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return SimpleNamespace(status_code=200, url="https://example.com/job", text="Apply now")

    monkeypatch.setattr(job_availability.httpx, "Client", FakeClient)

    updated = job_availability.verify_job_availability(fake_db, job.id)

    assert updated.availability_status == "open"
    assert called is False


def test_availability_check_never_browses_linkedin(monkeypatch):
    job = Job(
        id=uuid4(),
        title="Backend Engineer",
        description="Partial alert",
        source_url="https://www.linkedin.com/jobs/view/123456/",
    )
    fake_db = FakeDb(job)
    called = False

    def fail_if_called(_url):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr(job_availability.settings, "enable_browser_job_checks", True)
    monkeypatch.setattr(job_availability, "scrape_job_page_with_selenium", fail_if_called)

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return SimpleNamespace(
                status_code=200,
                url="https://www.linkedin.com/login",
                text="Sign in to continue",
            )

    monkeypatch.setattr(job_availability.httpx, "Client", FakeClient)

    updated = job_availability.verify_job_availability(fake_db, job.id)

    assert updated.availability_status == "unknown"
    assert called is False
