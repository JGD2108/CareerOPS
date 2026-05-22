from pathlib import Path

from app.ai_schemas import (
    AIProfileExtraction,
    AIProfileProject,
    AIProfileSkill,
)
from app.evaluation_harness import build_report, load_golden_set
from app.models import EvidenceLevel
from app.evaluation_harness import score_profile_prediction


def test_golden_set_is_valid_and_inbox_baseline_is_strong():
    dataset_path = Path(__file__).resolve().parents[1] / "evals" / "agent_golden_set.json"
    dataset = load_golden_set(dataset_path)
    report = build_report(dataset)
    assert report["inbox_triage"]["sample_count"] >= 8
    # Expect high baseline but allow room for expansion: >= 90% precision & recall
    assert report["inbox_triage"]["precision"] >= 0.9
    assert report["inbox_triage"]["recall"] >= 0.9
    assert report["inbox_triage"]["false_positive_rate"] <= 0.1
    assert report["profile_extraction"]["sample_count"] >= 3


def test_profile_prediction_scoring_rewards_supported_matches():
    prediction = AIProfileExtraction(
        display_name="Ana Torres",
        headline="Backend engineer",
        location="Miami",
        communication_style=["clear", "technical"],
        work_preferences=["backend", "local-first"],
        skills=[
            AIProfileSkill(
                name="Python",
                category="backend",
                evidence_level=EvidenceLevel.STRONG,
                evidence_text="worked with Python",
            ),
            AIProfileSkill(
                name="FastAPI",
                category="backend",
                evidence_level=EvidenceLevel.STRONG,
                evidence_text="worked with FastAPI",
            ),
        ],
        projects=[
            AIProfileProject(
                name="internal job routing service",
                description="routing service",
                technologies=["Python"],
                impact="presented a migration plan",
                evidence_text="led an internal job routing service",
            )
        ],
    )
    expected = {
        "display_name": "Ana Torres",
        "headline": "Backend engineer",
        "location": "Miami",
        "skills": ["Python", "FastAPI"],
        "projects": ["internal job routing service"],
        "communication_style": ["clear", "technical"],
        "work_preferences": ["backend", "local-first"],
    }

    score = score_profile_prediction(expected, prediction)

    assert score["overall_score"] >= 0.95
    assert score["evidence_coverage"] == 1.0
    assert score["skill_recall"] == 1.0
    assert score["project_recall"] == 1.0
