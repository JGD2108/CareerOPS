from app.gmail_integration import _classify_email
from app.models import EmailCategory


def test_marketing_brand_email_is_not_interview_invitation():
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Shop the New Mexico Third Jersey",
        body_text="Every detail reflects the strength, identity, and pride of Mexico. Display images.",
        from_email="adidas@us-news.comms.adidas.com",
    )

    assert category == EmailCategory.OTHER
    assert urgency == "normal"
    assert requires_reply is False
    assert "Ignore" in suggested_action


def test_linkedin_job_alert_is_classified_as_job_alert():
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Junior Software Engineer (Colombia) at Sezzle",
        body_text="LinkedIn Job Alerts\nJunior Software Engineer (Colombia) at Sezzle\nView job: https://www.linkedin.com/comm/jobs/view/4271082569/",
        from_email="jobalerts-noreply@linkedin.com",
    )

    assert category == EmailCategory.JOB_ALERT
    assert urgency == "normal"
    assert requires_reply is False
    assert "score" in suggested_action.lower()


def test_interview_email_requires_human_reply():
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Interview availability for Backend Engineer",
        body_text="Could you share your availability for a technical interview next week?",
        from_email="recruiter@example.com",
    )

    assert category == EmailCategory.INTERVIEW_INVITATION
    assert urgency == "high"
    assert requires_reply is True
    assert "availability" in suggested_action.lower()


def test_rejection_email_updates_tracker_guidance():
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Application update",
        body_text="Unfortunately, we will not be moving forward with your application.",
        from_email="careers@example.com",
    )

    assert category == EmailCategory.REJECTION
    assert urgency == "normal"
    assert requires_reply is False
    assert "rejected" in suggested_action.lower()
