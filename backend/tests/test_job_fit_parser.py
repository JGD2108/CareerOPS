from app.job_fit import parse_job_description
from app.models import Job


def test_parse_job_description_extracts_role_signals_and_requirements():
    job = Job(
        title="Junior Backend Engineer",
        location="Remote Colombia",
        work_mode="remote",
        seniority="junior",
        description=(
            "We need 1+ years of experience with Python, FastAPI, PostgreSQL, "
            "Docker, REST APIs, workflow automation, and LLM integrations."
        ),
    )

    parsed = parse_job_description(job)

    assert parsed["years_experience"] == 1
    assert "python" in parsed["required_skills"]
    assert "fastapi" in parsed["required_skills"]
    assert "postgresql" in parsed["required_skills"]
    assert "docker" in parsed["required_skills"]
    assert "backend" in parsed["role_signals"]
    assert "ai" in parsed["role_signals"]
