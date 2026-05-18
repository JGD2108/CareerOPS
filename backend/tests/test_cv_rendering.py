from types import SimpleNamespace

from app.cv_tailoring import _render_skills_section, _render_summary_section


def _cv_version():
    return SimpleNamespace(
        tailoring_plan={
            "job": {"title": "Backend Engineer"},
            "skills_to_prioritize": [
                "Python",
                "FastAPI",
                "PostgreSQL",
                "Docker",
                "Gemini API",
                "pgvector",
                "AWS Lambda",
            ],
            "experience_bullets_to_reuse": [
                {
                    "bullet": "Delivered 13 backend modules, 16 Prisma models, and 97 route/controller decorators.",
                }
            ],
            "projects_to_prioritize": [
                {
                    "existing_content": {
                        "impact": "Refactored a monolithic API into a 7-container Docker platform.",
                    }
                }
            ],
        }
    )


def test_summary_uses_metrics_and_target_role_without_fabricating():
    summary = _render_summary_section(_cv_version())

    assert "Backend Engineer" in summary
    assert "13 backend modules" in summary
    assert "7-container" in summary
    assert "unicorn" not in summary.lower()


def test_skills_are_grouped_for_ats_readability():
    skills = _render_skills_section(_cv_version())

    assert "Full-stack and backend" in skills
    assert "Data, AI, and automation" in skills
    assert "Cloud, deployment, and tools" in skills
    assert "Gemini API" in skills
    assert "AWS Lambda" in skills
