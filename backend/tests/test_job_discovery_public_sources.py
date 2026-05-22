from types import SimpleNamespace

from app import crud
from app.gmail_integration import _classify_email, _extract_job_alert_candidates
from app.job_discovery import JobDiscoverySourceConfig, _smartrecruiters_jobs, _workday_jobs
from app.models import ApplicationStatus, EmailCategory


def test_smartrecruiters_payload_is_normalized_into_jobs():
    jobs = _smartrecruiters_jobs(
        {
            "content": [
                {
                    "id": "sr-123",
                    "name": "Backend Engineer",
                    "location": {"city": "Bogotá"},
                    "type": "Remote",
                    "jobAd": {"text": "Build APIs with Python and FastAPI."},
                    "applyUrl": "https://example.com/jobs/sr-123",
                }
            ]
        },
        JobDiscoverySourceConfig(source="smartrecruiters", company_key="example", company_name_override="Example Co"),
    )

    assert len(jobs) == 1
    assert jobs[0].source == "smartrecruiters"
    assert jobs[0].company_name == "Example Co"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].job_url == "https://example.com/jobs/sr-123"


def test_workday_payload_is_normalized_into_jobs():
    jobs = _workday_jobs(
        {
            "jobPostings": [
                {
                    "title": "Backend Engineer",
                    "jobDescription": {"text": "Build APIs with Python and FastAPI."},
                    "locationsText": "Bogotá, Colombia",
                    "jobPostingId": "wd-123",
                    "externalPath": "/en-US/Example/job/Bogota/Backend_Engineer_JR123",
                }
            ]
        },
        JobDiscoverySourceConfig(source="workday", company_key="example", company_name_override="Example Co"),
    )

    assert len(jobs) == 1
    assert jobs[0].source == "workday"
    assert jobs[0].company_name == "Example Co"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].job_url == "https://example.wd5.myworkdayjobs.com/en-US/Example/job/Bogota/Backend_Engineer_JR123"


def test_applied_jobs_are_filtered_out_of_the_jobs_list():
    visible_job = SimpleNamespace(applications=[])
    hidden_job = SimpleNamespace(applications=[SimpleNamespace(status=ApplicationStatus.APPLIED)])

    assert crud._has_applied_application(visible_job) is False
    assert crud._has_applied_application(hidden_job) is True

    jobs = [visible_job, hidden_job]
    visible_jobs = [job for job in jobs if not crud._has_applied_application(job)]

    assert visible_jobs == [visible_job]


def test_glassdoor_and_computrabajo_alerts_classify_as_job_alerts():
    glassdoor_category, _, _, _ = _classify_email(
        subject="New jobs for you",
        body_text="Backend Engineer at Acme Corp",
        from_email="alerts@glassdoor.com",
    )
    computrabajo_category, _, _, _ = _classify_email(
        subject="Vacancies for you",
        body_text="Acme Corp is hiring Backend Engineer",
        from_email="jobs@computrabajo.com",
    )
    workday_category, _, _, _ = _classify_email(
        subject="New jobs for you",
        body_text="Backend Engineer - Acme Corp",
        from_email="alerts@myworkdayjobs.com",
    )

    assert glassdoor_category.name == "JOB_ALERT"
    assert computrabajo_category.name == "JOB_ALERT"
    assert workday_category.name == "JOB_ALERT"


def test_generic_job_alert_extraction_finds_title_and_company():
    email = SimpleNamespace(
        category=EmailCategory.JOB_ALERT,
        subject="New jobs for you",
        snippet="Backend Engineer at Acme Corp",
        body_text="Backend Engineer at Acme Corp\nApply now",
    )

    candidates = _extract_job_alert_candidates(email, source_kind="glassdoor_email_alert")

    assert candidates
    assert candidates[0]["title"] == "Backend Engineer"
    assert candidates[0]["company"] == "Acme Corp"


def test_ai_engineer_alert_extraction_keeps_target_role():
    email = SimpleNamespace(
        category=EmailCategory.JOB_ALERT,
        subject="New jobs for you",
        snippet="Junior AI Engineer at Acme Labs",
        body_text="Junior AI Engineer at Acme Labs\nApply now",
    )

    candidates = _extract_job_alert_candidates(email, source_kind="glassdoor_email_alert")

    assert candidates
    assert candidates[0]["title"] == "Junior AI Engineer"
    assert candidates[0]["company"] == "Acme Labs"
