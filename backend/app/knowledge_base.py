from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.audit import write_audit_log
from app.models import CandidateProfile, ProfileSkill, ProfileSkillAlias
from app.profile_ingestion import get_profile


CONTROLLED_ALIASES = {
    "REST APIs": [
        ("api development", "REST APIs in the profile support general API development claims."),
        ("api integration", "REST APIs in the profile support API integration claims."),
        ("http api", "REST APIs in the profile support HTTP API work."),
    ],
    "workflow automation": [
        ("automation", "Workflow automation in the profile supports automation claims."),
        ("business process automation", "Workflow automation supports business process automation claims."),
    ],
    "data pipelines": [
        ("etl", "Data pipelines in the profile support ETL-style workflow claims."),
        ("data ingestion", "Data pipelines support data ingestion claims when the job uses that language."),
    ],
    "AWS Lambda": [
        ("serverless", "AWS Lambda evidence supports serverless workflow claims."),
        ("serverless functions", "AWS Lambda evidence supports serverless functions."),
    ],
    "S3": [
        ("object storage", "S3 evidence supports object storage claims."),
        ("cloud storage", "S3 evidence supports cloud storage claims."),
    ],
    "Gemini API": [
        ("llm api", "Gemini API evidence supports LLM API integration claims."),
        ("generative ai api", "Gemini API evidence supports generative AI API integration claims."),
    ],
    "LLM prompting": [
        ("prompting", "LLM prompting evidence supports prompting claims."),
        ("prompt design", "LLM prompting evidence supports prompt design claims."),
    ],
    "pgvector": [
        ("vector search", "pgvector evidence supports vector search claims."),
        ("vector database", "pgvector evidence supports vector database claims."),
    ],
    "semantic search": [
        ("retrieval", "Semantic search evidence supports retrieval workflow claims."),
        ("search relevance", "Semantic search evidence supports search relevance claims."),
    ],
    "PostgreSQL": [
        ("relational database", "PostgreSQL evidence supports relational database work."),
        ("database modeling", "PostgreSQL evidence supports database modeling when paired with schema work."),
    ],
    "Docker": [
        ("containerization", "Docker evidence supports containerization claims."),
        ("containers", "Docker evidence supports container-based deployment claims."),
    ],
}


def _normalize(value: str) -> str:
    return value.strip().lower()


def rebuild_skill_aliases(db: Session) -> list[ProfileSkillAlias]:
    profile = get_profile(db)
    if not profile:
        raise ValueError("Candidate profile not found.")

    db.execute(delete(ProfileSkillAlias))
    created: list[ProfileSkillAlias] = []
    skills_by_name = {_normalize(skill.name): skill for skill in profile.skills}

    for canonical_name, aliases in CONTROLLED_ALIASES.items():
        skill = skills_by_name.get(_normalize(canonical_name))
        if not skill:
            continue
        for alias, rationale in aliases:
            row = ProfileSkillAlias(profile_skill_id=skill.id, alias=alias, rationale=rationale)
            db.add(row)
            created.append(row)

    write_audit_log(
        db,
        event_type="knowledge_base.aliases_rebuilt",
        entity_type="candidate_profile",
        entity_id=profile.id,
        details={"alias_count": len(created)},
    )
    db.commit()
    return list_skill_aliases(db)


def list_skill_aliases(db: Session) -> list[ProfileSkillAlias]:
    return list(
        db.scalars(
            select(ProfileSkillAlias)
            .options(selectinload(ProfileSkillAlias.skill))
            .order_by(ProfileSkillAlias.alias.asc())
        )
    )


def find_evidence_for_claim(db: Session, claim: str) -> dict:
    profile = db.scalar(
        select(CandidateProfile)
        .options(
            selectinload(CandidateProfile.skills).selectinload(ProfileSkill.aliases),
            selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.experiences),
        )
        .order_by(CandidateProfile.created_at.asc())
    )
    if not profile:
        raise ValueError("Candidate profile not found.")

    claim_normalized = _normalize(claim)
    matches = []

    for skill in profile.skills:
        terms = [(skill.name, "skill")] + [(alias.alias, "skill_alias") for alias in skill.aliases]
        for term, source_type in terms:
            if _normalize(term) in claim_normalized or claim_normalized in _normalize(term):
                matches.append(
                    {
                        "source_type": source_type,
                        "matched_term": term,
                        "canonical_skill": skill.name,
                        "evidence_text": skill.evidence_text,
                    }
                )

    for project in profile.projects:
        if _normalize(project.name) in claim_normalized:
            matches.append(
                {
                    "source_type": "project",
                    "matched_term": project.name,
                    "canonical_skill": None,
                    "evidence_text": project.evidence_text,
                }
            )

    return {
        "claim": claim,
        "is_supported": bool(matches),
        "matches": matches[:10],
    }
