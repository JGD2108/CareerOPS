from app.models import PortalCheckConfidence, PublicJobStatus
from app.portal_status_checker import classify_public_job_page, detect_provider


def test_detect_provider_for_official_ats_hosts():
    assert detect_provider("https://jobs.lever.co/acme/123") == "lever"
    assert detect_provider("https://acme.greenhouse.io/jobs/123") == "greenhouse"
    assert detect_provider("https://acme.wd5.myworkdayjobs.com/en-US/jobs/job/123") == "workday"
    assert detect_provider("https://jobs.smartrecruiters.com/acme/123") == "smartrecruiters"


def test_classifies_open_public_job_page():
    result = classify_public_job_page(
        "https://jobs.lever.co/acme/123",
        200,
        "https://jobs.lever.co/acme/123",
        "<main><h1>Backend Engineer</h1><button>Apply for this job</button></main>",
    )

    assert result.status == PublicJobStatus.OPEN
    assert result.confidence == PortalCheckConfidence.MEDIUM
    assert result.provider == "lever"
    assert result.login_required is False


def test_classifies_no_longer_accepting_before_open_words():
    result = classify_public_job_page(
        "https://acme.greenhouse.io/jobs/123",
        200,
        "https://acme.greenhouse.io/jobs/123",
        "This position is no longer accepting applications. Job details are retained for reference.",
    )

    assert result.status == PublicJobStatus.NO_LONGER_ACCEPTING_APPLICATIONS
    assert result.confidence == PortalCheckConfidence.HIGH


def test_classifies_removed_status_codes():
    result = classify_public_job_page(
        "https://company.example/careers/backend-engineer",
        404,
        "https://company.example/careers/backend-engineer",
        "Not found",
    )

    assert result.status == PublicJobStatus.REMOVED
    assert result.confidence == PortalCheckConfidence.HIGH


def test_classifies_login_required_portal():
    result = classify_public_job_page(
        "https://candidate.example/applications",
        200,
        "https://candidate.example/login",
        "<form id='login'><input name='email'><input name='password'></form>",
    )

    assert result.status == PublicJobStatus.LOGIN_REQUIRED
    assert result.login_required is True
    assert result.user_action_required is False


def test_classifies_mfa_as_user_action_required():
    result = classify_public_job_page(
        "https://candidate.example/applications",
        200,
        "https://candidate.example/mfa",
        "Enter the verification code from your multi-factor authentication app.",
    )

    assert result.status == PublicJobStatus.LOGIN_REQUIRED
    assert result.login_required is True
    assert result.user_action_required is True


def test_linkedin_is_reference_only():
    result = classify_public_job_page(
        "https://www.linkedin.com/jobs/view/123",
        200,
        "https://www.linkedin.com/jobs/view/123",
        "Apply now",
    )

    assert result.status == PublicJobStatus.UNKNOWN
    assert result.provider == "linkedin"
    assert "does not scrape" in result.evidence_summary
