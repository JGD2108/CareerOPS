from types import SimpleNamespace

from app.gmail_integration import (
    _category_allows_application_link,
    _classify_email,
    _default_reply_body,
    _infer_email_language,
    _is_job_inbox_email,
    _is_target_role,
)
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


def test_spanish_linkedin_profile_mismatch_is_rejection():
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Your application to Ingeniero de datos at Enersinc",
        body_text=(
            "Your update from Enersinc\n"
            "Gracias por tu interés en el puesto de Ingeniero de datos en Enersinc. "
            "Lamentablemente, no cumples con el perfil que exige el cargo.\n"
            "Saludos cordiales,\n"
            "Enersinc"
        ),
        from_email="jobs-noreply@linkedin.com",
    )

    assert category == EmailCategory.REJECTION
    assert urgency == "normal"
    assert requires_reply is False
    assert "rejected" in suggested_action.lower()


def test_generic_application_confirmation_is_not_downgraded_to_other():
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Thank you for applying to Acme",
        body_text="We received your application for the Junior AI Engineer role. Your resume has been received.",
        from_email="no-reply@greenhouse.io",
    )

    assert category == EmailCategory.APPLICATION_CONFIRMATION
    assert urgency == "normal"
    assert requires_reply is False
    assert "application confirmation" in suggested_action.lower()


def test_job_inbox_filter_excludes_linkedin_alerts_and_other_noise():
    visible_email = SimpleNamespace(category=EmailCategory.INTERVIEW_INVITATION, application_id=None)
    hidden_job_alert = SimpleNamespace(category=EmailCategory.JOB_ALERT, application_id=None)
    hidden_other = SimpleNamespace(category=EmailCategory.OTHER, application_id=None)
    linked_other = SimpleNamespace(category=EmailCategory.OTHER, application_id="123")

    assert _is_job_inbox_email(visible_email) is True
    assert _is_job_inbox_email(hidden_job_alert) is False
    assert _is_job_inbox_email(hidden_other) is False
    assert _is_job_inbox_email(linked_other) is True


def test_only_actionable_email_categories_allow_auto_linking():
    assert _category_allows_application_link(EmailCategory.INTERVIEW_INVITATION) is True
    assert _category_allows_application_link(EmailCategory.APPLICATION_CONFIRMATION) is True
    assert _category_allows_application_link(EmailCategory.JOB_ALERT) is False
    assert _category_allows_application_link(EmailCategory.OTHER) is False


def test_community_newsletter_is_not_misclassified_as_interview() -> None:
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="just showing up is the first win",
        body_text="resume reviews tomorrow, laid off lounge wednesday, community update for builders",
        from_email="community@torc.dev",
    )

    assert category == EmailCategory.OTHER
    assert urgency == "normal"
    assert requires_reply is False
    assert "Ignore" in suggested_action


def test_ai_engineer_title_counts_as_target_role() -> None:
    assert _is_target_role("Junior AI Engineer") is True


def test_linkedin_social_acceptance_is_not_recruiter_follow_up() -> None:
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Boris accepted your invitation, explore their network",
        body_text="See more people from their company and keep building your network on LinkedIn.",
        from_email="messages-noreply@linkedin.com",
    )

    assert category == EmailCategory.OTHER
    assert urgency == "normal"
    assert requires_reply is False
    assert "Ignore" in suggested_action


def test_greenhouse_growth_email_is_not_recruiter_follow_up() -> None:
    category, urgency, requires_reply, suggested_action = _classify_email(
        subject="Show recruiters you're really interested with Dream Job",
        body_text="Get noticed by every hiring team and boost your profile visibility with Dream Job.",
        from_email="notifications@us.greenhouse-jobs.com",
    )

    assert category == EmailCategory.OTHER
    assert urgency == "normal"
    assert requires_reply is False
    assert "Ignore" in suggested_action


def test_recruiter_follow_up_reply_uses_email_language() -> None:
    email = SimpleNamespace(
        category=EmailCategory.RECRUITER_FOLLOW_UP,
        company_name="Acme",
        subject="Hola, seguimiento de tu postulación",
        snippet="Hola, quería dar seguimiento a tu mensaje.",
        body_text="Hola, quería dar seguimiento a tu mensaje y confirmar los siguientes pasos.",
    )

    assert _infer_email_language(email) == "spanish"
    body = _default_reply_body(email)

    assert body.startswith("Hola,")
    assert "seguimiento" in body.lower()
