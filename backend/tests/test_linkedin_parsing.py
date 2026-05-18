from types import SimpleNamespace

from app.gmail_integration import _extract_linkedin_job_alerts
from app.models import EmailCategory


def test_extracts_target_linkedin_job_alerts_only():
    email = SimpleNamespace(
        category=EmailCategory.JOB_ALERT,
        subject="LinkedIn Job Alerts",
        snippet="Junior Software Engineer (Colombia) at Sezzle",
        body_text="\n".join(
            [
                "Junior Software Engineer (Colombia) at Sezzle",
                "https://www.linkedin.com/comm/jobs/view/4271082569/",
                "Shop Manager at Retail Brand",
                "Data Engineer Junior at CloudData",
                "https://www.linkedin.com/comm/jobs/view/1111111111/",
            ]
        ),
    )

    candidates = _extract_linkedin_job_alerts(email)

    assert [candidate["title"] for candidate in candidates] == [
        "Junior Software Engineer (Colombia)",
        "Data Engineer Junior",
    ]
    assert candidates[0]["company"] == "Sezzle"
    assert candidates[0]["url"].startswith("https://www.linkedin.com/comm/jobs/view/")


def test_non_job_alert_email_does_not_create_jobs():
    email = SimpleNamespace(
        category=EmailCategory.OTHER,
        subject="Your posts got impressions",
        snippet="This is LinkedIn engagement content.",
        body_text="Software Engineer at Example",
    )

    assert _extract_linkedin_job_alerts(email) == []
