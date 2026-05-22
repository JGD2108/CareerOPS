import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.job_description_state import description_is_complete, description_text_for_analysis, incomplete_description_reason
from app.models import (
    CandidateProfile,
    Job,
    JobRecommendation,
    JobScore,
    ProfileSkill,
    ProfileSkillAlias,
)
from app.profile_ingestion import get_profile
from app.semantic_embeddings import semantic_matches_for_job


ROLE_KEYWORDS = {
    "backend": ["backend", "api", "server", "microservice", "nestjs", "fastapi"],
    "data": ["data pipeline", "etl", "analytics", "bigquery", "data engineer", "sql"],
    "ai": ["ai", "llm", "agent", "rag", "prompt", "gemini", "openai", "vector"],
}

KNOWN_REQUIREMENTS = [
    "python",
    "fastapi",
    "django",
    "flask",
    "node.js",
    "node",
    "nestjs",
    "express",
    "typescript",
    "javascript",
    "react",
    "angular",
    "vue",
    "next.js",
    "postgresql",
    "sql",
    "mysql",
    "mongodb",
    "nosql",
    "prisma",
    "sqlalchemy",
    "docker",
    "kubernetes",
    "nginx",
    "aws",
    "azure",
    "gcp",
    "lambda",
    "s3",
    "ec2",
    "eventbridge",
    "boto3",
    "google cloud",
    "bigquery",
    "git",
    "github actions",
    "gitlab",
    "ci/cd",
    "rest",
    "rest api",
    "graphql",
    "api development",
    "api integration",
    "jwt",
    "oauth",
    "openapi",
    "swagger",
    "llm",
    "prompt engineering",
    "prompt design",
    "gemini",
    "openai",
    "gpt",
    "llm api",
    "pgvector",
    "vector search",
    "semantic search",
    "elasticsearch",
    "serverless",
    "data pipelines",
    "data ingestion",
    "etl",
    "apache spark",
    "apache kafka",
    "workflow automation",
    "automation",
    "redis",
    "rabbitmq",
    "langgraph",
    "langchain",
    "crew ai",
    "crewai",
    "jest",
    "pytest",
    "playwright",
    "selenium",
    "tailwind css",
    "material-ui",
]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", value.lower()).strip()


def _contains_term(text: str, term: str) -> bool:
    normalized_text = _normalize(text)
    normalized_term = _normalize(term)
    if normalized_term in {"sql", "aws", "gcp"}:
        return re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text) is not None
    return normalized_term in normalized_text


def parse_job_description(job: Job) -> dict:
    description = description_text_for_analysis(job)
    combined = " ".join(value for value in [job.title, job.seniority, job.location, job.work_mode, description] if value)
    required_skills = sorted({skill for skill in KNOWN_REQUIREMENTS if _contains_term(combined, skill)})

    years_match = re.search(r"(\d+)\+?\s*(?:years|yrs|anos|años)", combined, re.IGNORECASE)
    role_signals = {
        role: [keyword for keyword in keywords if _contains_term(combined, keyword)]
        for role, keywords in ROLE_KEYWORDS.items()
    }
    role_signals = {role: hits for role, hits in role_signals.items() if hits}

    return {
        "title": job.title,
        "location": job.location,
        "work_mode": job.work_mode,
        "seniority": job.seniority,
        "required_skills": required_skills,
        "years_experience": int(years_match.group(1)) if years_match else None,
        "role_signals": role_signals,
    }


def _profile_skill_index(profile: CandidateProfile) -> dict[str, tuple[ProfileSkill, str, str | None]]:
    index: dict[str, tuple[ProfileSkill, str, str | None]] = {}
    for skill in profile.skills:
        index[_normalize(skill.name)] = (skill, "direct", None)
        for alias in skill.aliases:
            index[_normalize(alias.alias)] = (skill, "alias", alias.rationale)
    return index


def _match_skills(required_skills: list[str], profile: CandidateProfile) -> tuple[list[dict], list[dict]]:
    skill_index = _profile_skill_index(profile)
    matched = []
    missing = []

    for requirement in required_skills:
        normalized_requirement = _normalize(requirement)
        direct_match = skill_index.get(normalized_requirement)
        fuzzy_match = next(
            (
                indexed
                for normalized_skill, indexed in skill_index.items()
                if normalized_requirement in normalized_skill or normalized_skill in normalized_requirement
            ),
            None,
        )
        indexed_skill = direct_match or fuzzy_match
        if indexed_skill:
            skill, match_type, rationale = indexed_skill
            matched.append(
                {
                    "required_skill": requirement,
                    "profile_skill": skill.name,
                    "evidence_level": skill.evidence_level,
                    "evidence_text": skill.evidence_text,
                    "match_type": match_type,
                    "rationale": rationale,
                }
            )
        else:
            missing.append({"required_skill": requirement, "reason": "No direct evidence found in profile sources."})

    return matched, missing


def _recommend(score: int, missing_count: int) -> JobRecommendation:
    if score >= 75 and missing_count <= 3:
        return JobRecommendation.APPLY_NOW
    if score >= 45:
        return JobRecommendation.REVIEW
    return JobRecommendation.IGNORE


def get_latest_job_score(db: Session, job_id: UUID) -> JobScore | None:
    return db.scalar(select(JobScore).where(JobScore.job_id == job_id).order_by(JobScore.created_at.desc()))


def ensure_job_score(db: Session, job_id: UUID) -> JobScore | None:
    existing = get_latest_job_score(db, job_id)
    if existing:
        return existing
    return score_job_fit(db, job_id)


def score_job_fit(db: Session, job_id: UUID, *, preliminary: bool = False) -> JobScore | None:
    job = db.get(Job, job_id)
    profile = get_profile(db)
    if not job or not profile:
        return None
    if not preliminary and not description_is_complete(job):
        raise ValueError(incomplete_description_reason(job))

    extracted = parse_job_description(job)
    extracted["description_status"] = job.description_status
    extracted["description_quality"] = job.description_quality
    extracted["preliminary"] = preliminary
    required_skills = extracted["required_skills"]
    matched, missing = _match_skills(required_skills, profile)

    if required_skills:
        skill_score = round((len(matched) / len(required_skills)) * 100)
    else:
        skill_score = 35

    role_bonus = 0
    role_signals = extracted["role_signals"]
    if "backend" in role_signals:
        role_bonus += 8
    if "ai" in role_signals:
        role_bonus += 8
    if "data" in role_signals:
        role_bonus += 5

    score = max(0, min(100, skill_score + role_bonus))
    semantic_matches = []
    semantic_bonus = 0
    try:
        semantic_matches = semantic_matches_for_job(db, job_id, limit=5)
    except Exception:
        semantic_matches = []
    if semantic_matches:
        best_similarity = max(item["similarity"] for item in semantic_matches)
        if best_similarity >= 0.82:
            semantic_bonus = 10
        elif best_similarity >= 0.74:
            semantic_bonus = 6
        elif best_similarity >= 0.66:
            semantic_bonus = 3
        score = max(0, min(100, score + semantic_bonus))
        extracted["semantic_matches"] = [
            {
                "source_table": item["source_table"],
                "source_id": str(item["source_id"]),
                "metadata": item["metadata"],
                "similarity": item["similarity"],
            }
            for item in semantic_matches
        ]
        extracted["semantic_bonus"] = semantic_bonus
    recommendation = _recommend(score, len(missing))

    reasons = []
    risks = []
    if matched:
        reasons.append(f"Matched {len(matched)} of {len(required_skills)} extracted technical requirements.")
    if role_signals:
        reasons.append(f"Role signals detected: {', '.join(sorted(role_signals.keys()))}.")
    if semantic_matches:
        reasons.append(f"Semantic profile retrieval found {len(semantic_matches)} supporting evidence records.")
    if not required_skills:
        risks.append("The parser found no known technical requirements; manual review is needed.")
    if preliminary:
        risks.append("Preliminary score only: the job description has not been fully resolved.")
    if missing:
        risks.append(f"{len(missing)} extracted requirements do not have direct profile evidence yet.")

    evidence = [
        {
            "claim": f"Candidate has evidence for {item['profile_skill']}.",
            "source": "profile_skills",
            "evidence_text": item["evidence_text"],
        }
        for item in matched[:10]
    ]
    evidence.extend(
        {
            "claim": f"Semantic evidence match: {item['metadata'].get('name') or item['metadata'].get('kind') or item['source_table']}",
            "source": item["source_table"],
            "evidence_text": item["content"][:500],
            "similarity": item["similarity"],
        }
        for item in semantic_matches[:5]
    )

    job_score = JobScore(
        job_id=job.id,
        candidate_profile_id=profile.id,
        score=score,
        recommendation=recommendation,
        extracted_requirements=extracted,
        matched_skills=matched,
        missing_or_weak_skills=missing,
        reasons=reasons,
        risks=risks,
        evidence=evidence,
    )
    db.add(job_score)
    db.flush()
    write_audit_log(
        db,
        event_type="job.scored",
        entity_type="job_score",
        entity_id=job_score.id,
        details={"job_id": str(job.id), "score": score, "recommendation": recommendation},
    )
    db.commit()
    db.refresh(job_score)
    return job_score


def list_job_scores(db: Session, job_id: UUID) -> list[JobScore]:
    return list(
        db.scalars(select(JobScore).where(JobScore.job_id == job_id).order_by(JobScore.created_at.desc()))
    )
