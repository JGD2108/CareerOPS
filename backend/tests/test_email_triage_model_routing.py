from app import ai_client
from app import langgraph_agents
from app.ai_schemas import AIEmailTriage
from app.models import EmailCategory


def test_email_triage_escalates_ambiguous_primary_result(monkeypatch) -> None:
    calls: list[str] = []

    def fake_generate_structured_output(**kwargs):
        model = kwargs["model"]
        calls.append(model)
        if model == "gpt-5-nano":
            return AIEmailTriage(
                relevant_to_careerops=False,
                category=EmailCategory.OTHER,
                confidence=45,
                suggested_action="Review manually.",
                reasoning="Ambiguous status update.",
            )
        return AIEmailTriage(
            relevant_to_careerops=True,
            category=EmailCategory.REJECTION,
            company_name="Urrly",
            role_hint="AI-Enabled Software Engineer",
            confidence=92,
            suggested_action="Update the tracker to rejected.",
            reasoning="The email says other candidates aligned more closely.",
        )

    monkeypatch.setattr(ai_client.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(langgraph_agents.settings, "openai_email_model", "gpt-5-nano")
    monkeypatch.setattr(langgraph_agents.settings, "openai_email_escalation_model", "gpt-5-mini")
    monkeypatch.setattr(langgraph_agents, "generate_structured_output", fake_generate_structured_output)

    triage, model_used, escalated = langgraph_agents.triage_email_content_with_ai_routed(
        from_email="candidate-0cfec3531cc3@urrly.breezy-mail.com",
        from_name="Rupam Patra",
        subject="Re: Urrly opportunity",
        body_text=(
            "There were a few candidates whose experience aligned a bit more with what our client is looking for."
        ),
    )

    assert calls == ["gpt-5-nano", "gpt-5-mini"]
    assert escalated is True
    assert model_used == "gpt-5-mini"
    assert triage.category == EmailCategory.REJECTION
    assert triage.company_name == "Urrly"


def test_email_triage_keeps_high_confidence_primary_result(monkeypatch) -> None:
    calls: list[str] = []

    def fake_generate_structured_output(**kwargs):
        calls.append(kwargs["model"])
        return AIEmailTriage(
            relevant_to_careerops=False,
            category=EmailCategory.OTHER,
            confidence=95,
            suggested_action="Ignore newsletter content.",
            reasoning="Generic marketing email.",
        )

    monkeypatch.setattr(ai_client.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(langgraph_agents.settings, "openai_email_model", "gpt-5-nano")
    monkeypatch.setattr(langgraph_agents.settings, "openai_email_escalation_model", "gpt-5-mini")
    monkeypatch.setattr(langgraph_agents, "generate_structured_output", fake_generate_structured_output)

    triage, model_used, escalated = langgraph_agents.triage_email_content_with_ai_routed(
        from_email="newsletter@example.com",
        subject="Weekly product update",
        body_text="New platform features and customer stories.",
    )

    assert calls == ["gpt-5-nano"]
    assert escalated is False
    assert model_used == "gpt-5-nano"
    assert triage.category == EmailCategory.OTHER


def test_email_triage_does_not_downgrade_deterministic_rejection(monkeypatch) -> None:
    calls: list[str] = []

    def fake_generate_structured_output(**kwargs):
        model = kwargs["model"]
        calls.append(model)
        if model == "gpt-5-nano":
            return AIEmailTriage(
                relevant_to_careerops=True,
                category=EmailCategory.REJECTION,
                company_name="Urrly",
                confidence=84,
                suggested_action="Update the tracker to rejected.",
                reasoning="The email says other candidates aligned more closely.",
            )
        return AIEmailTriage(
            relevant_to_careerops=False,
            category=EmailCategory.OTHER,
            confidence=94,
            suggested_action="Review manually.",
            reasoning="Ambiguous recruiter message.",
        )

    monkeypatch.setattr(ai_client.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(langgraph_agents.settings, "openai_email_model", "gpt-5-nano")
    monkeypatch.setattr(langgraph_agents.settings, "openai_email_escalation_model", "gpt-5-mini")
    monkeypatch.setattr(langgraph_agents, "generate_structured_output", fake_generate_structured_output)

    triage, model_used, escalated = langgraph_agents.triage_email_content_with_ai_routed(
        from_email="candidate-0cfec3531cc3@urrly.breezy-mail.com",
        subject="Re: Urrly opportunity",
        body_text="There were a few candidates whose experience aligned a bit more with what our client is looking for.",
    )

    assert calls == ["gpt-5-nano", "gpt-5-mini"]
    assert escalated is True
    assert model_used == "gpt-5-nano"
    assert triage.category == EmailCategory.REJECTION
