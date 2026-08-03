from app.models import SourceType
from app.public_profile_enrichment import (
    PublicProjectEvidence,
    _evidence_project_keys,
    _extract_metric_bullets,
    _extract_technologies,
    _repo_fingerprint,
)


def test_metric_extraction_accepts_explicit_numerics() -> None:
    text = "Reduced latency by 42% and handled 1200 requests per minute."
    bullets = _extract_metric_bullets(text)
    assert bullets
    assert any("42%" in bullet for bullet in bullets)


def test_metric_extraction_rejects_non_numeric_claims() -> None:
    text = "Improved performance significantly and increased reliability."
    bullets = _extract_metric_bullets(text)
    assert bullets == []


def test_tech_extraction_from_text_tokens() -> None:
    tech = _extract_technologies("Built with Python, FastAPI, and React.")
    assert "python" in tech
    assert "fastapi" in tech
    assert "react" in tech


def test_repo_fingerprint_normalization() -> None:
    assert _repo_fingerprint("https://www.github.com/User/Repo") == "github.com/user/repo"


def test_evidence_keys_include_name_and_repo_fingerprint() -> None:
    evidence = PublicProjectEvidence(
        name="My Project",
        description=None,
        impact=None,
        technologies=[],
        evidence_text="text",
        source_type=SourceType.GITHUB,
        repo_url="https://github.com/user/my-project",
    )
    name_key, repo_key = _evidence_project_keys(evidence)
    assert name_key == "my project"
    assert repo_key == "github.com/user/my-project"
