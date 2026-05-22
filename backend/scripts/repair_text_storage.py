from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_client import ai_agents_enabled
from app.db import SessionLocal
from app.documents import is_evaluation_artifact_document
from app.langgraph_agents import run_profile_ingestion_agent
from app.models import CandidateProfile, Document, Email, SourceType
from app.profile_ingestion import extract_profile_from_latest_cv
from app.text_normalization import normalize_text_block, normalize_text_list


def _latest_trusted_cv(db) -> Document | None:
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.source_type == SourceType.CV, Document.extracted_text.is_not(None))
            .order_by(Document.created_at.desc())
        )
    )
    for document in documents:
        if not is_evaluation_artifact_document(document):
            return document
    return None


def _normalize_profile_preferences(preferences: dict | None) -> dict | None:
    if not isinstance(preferences, dict):
        return preferences

    normalized = dict(preferences)
    for key in ["profile_origin", "source_document_id"]:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = normalize_text_block(value)

    for key in ["communication_style", "work_preferences"]:
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = normalize_text_list([item for item in value if isinstance(item, str)])

    return normalized


def main() -> int:
    db = SessionLocal()
    try:
        updated_documents = 0
        updated_emails = 0
        updated_profiles = 0

        for document in db.scalars(select(Document)):
            if document.extracted_text:
                normalized_text = normalize_text_block(document.extracted_text)
                if normalized_text and normalized_text != document.extracted_text:
                    document.extracted_text = normalized_text
                    updated_documents += 1

        for email in db.scalars(select(Email)):
            changed = False
            for field in ["company_name", "from_name", "subject", "snippet", "body_text", "suggested_action"]:
                value = getattr(email, field)
                if isinstance(value, str):
                    normalized_value = normalize_text_block(value)
                    if normalized_value != value:
                        setattr(email, field, normalized_value)
                        changed = True
            if changed:
                updated_emails += 1

        for profile in db.scalars(select(CandidateProfile)):
            changed = False
            for field in ["display_name", "headline", "location", "summary"]:
                value = getattr(profile, field)
                if isinstance(value, str):
                    normalized_value = normalize_text_block(value)
                    if normalized_value != value:
                        setattr(profile, field, normalized_value)
                        changed = True
            normalized_preferences = _normalize_profile_preferences(profile.preferences)
            if normalized_preferences != profile.preferences:
                profile.preferences = normalized_preferences
                changed = True
            if changed:
                updated_profiles += 1

        db.commit()

        rebuilt_profile = False
        trusted_cv = _latest_trusted_cv(db)
        if trusted_cv:
            if ai_agents_enabled():
                run_profile_ingestion_agent(db, document_id=trusted_cv.id)
            else:
                extract_profile_from_latest_cv(db)
            rebuilt_profile = True

        print(
            {
                "updated_documents": updated_documents,
                "updated_emails": updated_emails,
                "updated_profiles": updated_profiles,
                "rebuilt_profile": rebuilt_profile,
                "trusted_cv_id": str(trusted_cv.id) if trusted_cv else None,
            }
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
