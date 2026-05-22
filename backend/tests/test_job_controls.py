from app.job_availability import classify_availability_from_response
from app.job_controls import build_job_fingerprints


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
