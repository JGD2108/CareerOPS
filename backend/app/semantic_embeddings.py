from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai_client import generate_embedding
from app.audit import write_audit_log
from app.config import get_settings
from app.models import (
    CandidateProfile,
    Job,
    ProfileCertification,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
)
from app.profile_ingestion import get_profile


settings = get_settings()


@dataclass
class EmbeddingSource:
    source_table: str
    source_id: UUID
    owner_type: str
    owner_id: UUID | None
    content: str
    metadata: dict[str, Any]


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def _profile_sources(profile: CandidateProfile) -> list[EmbeddingSource]:
    sources: list[EmbeddingSource] = []
    for skill in profile.skills:
        content = f"Skill: {skill.name}\nCategory: {skill.category or 'uncategorized'}\nEvidence: {skill.evidence_text}"
        sources.append(
            EmbeddingSource(
                source_table="profile_skills",
                source_id=skill.id,
                owner_type="profile",
                owner_id=profile.id,
                content=content,
                metadata={"kind": "skill", "name": skill.name, "evidence_level": str(skill.evidence_level)},
            )
        )
    for project in profile.projects:
        content = "\n".join(
            [
                f"Project: {project.name}",
                f"Description: {project.description or ''}",
                f"Technologies: {', '.join(project.technologies or [])}",
                f"Impact: {project.impact or ''}",
                f"Evidence: {project.evidence_text}",
            ]
        )
        sources.append(
            EmbeddingSource(
                source_table="profile_projects",
                source_id=project.id,
                owner_type="profile",
                owner_id=profile.id,
                content=content,
                metadata={"kind": "project", "name": project.name},
            )
        )
    for experience in profile.experiences:
        content = "\n".join(
            [
                f"Experience: {experience.title} at {experience.company}",
                f"Location: {experience.location or ''}",
                f"Dates: {experience.start_date or ''} - {experience.end_date or ''}",
                f"Bullets: {' '.join(experience.bullets or [])}",
                f"Evidence: {experience.evidence_text}",
            ]
        )
        sources.append(
            EmbeddingSource(
                source_table="profile_experience",
                source_id=experience.id,
                owner_type="profile",
                owner_id=profile.id,
                content=content,
                metadata={"kind": "experience", "company": experience.company, "title": experience.title},
            )
        )
    for education in profile.education:
        content = f"Education: {education.degree} at {education.institution}. {education.evidence_text}"
        sources.append(
            EmbeddingSource(
                source_table="profile_education",
                source_id=education.id,
                owner_type="profile",
                owner_id=profile.id,
                content=content,
                metadata={"kind": "education", "institution": education.institution},
            )
        )
    for certification in profile.certifications:
        content = f"Certification: {certification.name}. Issuer: {certification.issuer or ''}. {certification.evidence_text}"
        sources.append(
            EmbeddingSource(
                source_table="profile_certifications",
                source_id=certification.id,
                owner_type="profile",
                owner_id=profile.id,
                content=content,
                metadata={"kind": "certification", "name": certification.name},
            )
        )
    return sources


def _job_source(job: Job) -> EmbeddingSource:
    company = job.company.name if job.company else "Unknown company"
    content = "\n".join(
        [
            f"Job: {job.title}",
            f"Company: {company}",
            f"Location: {job.location or ''}",
            f"Work mode: {job.work_mode or ''}",
            f"Seniority: {job.seniority or ''}",
            f"Description: {job.description}",
        ]
    )
    return EmbeddingSource(
        source_table="jobs",
        source_id=job.id,
        owner_type="job",
        owner_id=job.id,
        content=content,
        metadata={"kind": "job", "title": job.title, "company": company, "source": job.source},
    )


def _upsert_embedding(db: Session, source: EmbeddingSource) -> bool:
    content = source.content.strip()
    if not content:
        return False
    content_hash = _hash_content(content)
    existing_hash = db.scalar(
        text(
            """
            SELECT content_hash
            FROM semantic_embeddings
            WHERE source_table = :source_table AND source_id = :source_id
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"source_table": source.source_table, "source_id": source.source_id},
    )
    if existing_hash == content_hash:
        return False

    vector = generate_embedding(content[:12000], model=settings.openai_embedding_model)
    db.execute(
        text("DELETE FROM semantic_embeddings WHERE source_table = :source_table AND source_id = :source_id"),
        {"source_table": source.source_table, "source_id": source.source_id},
    )
    db.execute(
        text(
            """
            INSERT INTO semantic_embeddings (
                source_table,
                source_id,
                owner_type,
                owner_id,
                content,
                content_hash,
                embedding,
                embedding_metadata,
                model
            )
            VALUES (
                :source_table,
                :source_id,
                :owner_type,
                :owner_id,
                :content,
                :content_hash,
                CAST(:embedding AS vector),
                CAST(:metadata AS jsonb),
                :model
            )
            """
        ),
        {
            "source_table": source.source_table,
            "source_id": source.source_id,
            "owner_type": source.owner_type,
            "owner_id": source.owner_id,
            "content": content,
            "content_hash": content_hash,
            "embedding": _vector_literal(vector),
            "metadata": json.dumps(source.metadata),
            "model": settings.openai_embedding_model,
        },
    )
    return True


def rebuild_semantic_embeddings(db: Session, *, include_jobs: bool = False, job_limit: int = 100) -> dict[str, int]:
    profile = get_profile(db)
    if not profile:
        raise ValueError("Candidate profile not found. Build the profile before generating embeddings.")

    sources = _profile_sources(profile)
    if include_jobs:
        jobs = list(db.scalars(select(Job).order_by(Job.created_at.desc()).limit(job_limit)))
        sources.extend(_job_source(job) for job in jobs)

    created_or_updated = 0
    skipped = 0
    for source in sources:
        if _upsert_embedding(db, source):
            created_or_updated += 1
        else:
            skipped += 1

    write_audit_log(
        db,
        event_type="semantic_embeddings.rebuilt",
        entity_type="semantic_embeddings",
        details={
            "include_jobs": include_jobs,
            "job_limit": job_limit,
            "created_or_updated": created_or_updated,
            "skipped": skipped,
            "model": settings.openai_embedding_model,
        },
    )
    db.commit()
    return {"created_or_updated": created_or_updated, "skipped": skipped, "total_sources": len(sources)}


def ensure_job_embedding(db: Session, job_id: UUID) -> bool:
    job = db.get(Job, job_id)
    if not job:
        raise ValueError("Job not found.")
    changed = _upsert_embedding(db, _job_source(job))
    db.commit()
    return changed


def semantic_matches_for_job(db: Session, job_id: UUID, *, limit: int = 5) -> list[dict[str, Any]]:
    job_embedding = db.execute(
        text(
            """
            SELECT embedding::text
            FROM semantic_embeddings
            WHERE source_table = 'jobs' AND source_id = :job_id
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"job_id": job_id},
    ).scalar()
    if job_embedding is None:
        return []

    rows = db.execute(
        text(
            """
            SELECT
                source_table,
                source_id,
                content,
                embedding_metadata,
                1 - (embedding <=> CAST(:job_embedding AS vector)) AS similarity
            FROM semantic_embeddings
            WHERE owner_type = 'profile'
            ORDER BY embedding <=> CAST(:job_embedding AS vector)
            LIMIT :limit
            """
        ),
        {"job_id": job_id, "job_embedding": job_embedding, "limit": limit},
    ).mappings()
    return [
        {
            "source_table": row["source_table"],
            "source_id": row["source_id"],
            "content": row["content"],
            "metadata": row["embedding_metadata"] or {},
            "similarity": round(float(row["similarity"]), 4),
        }
        for row in rows
    ]
