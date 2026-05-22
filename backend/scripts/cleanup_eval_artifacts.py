from __future__ import annotations

import shutil
import sys
from pathlib import Path
from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_client import ai_agents_enabled
from app.db import SessionLocal
from app.documents import is_evaluation_artifact_document
from app.langgraph_agents import run_profile_ingestion_agent
from app.models import Document, Email, RawEmail, SourceType
from app.profile_ingestion import extract_profile_from_latest_cv


def _latest_trusted_cv_id(db):
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.source_type == SourceType.CV, Document.extracted_text.is_not(None))
            .order_by(Document.created_at.desc())
        )
    )
    for document in documents:
        if not is_evaluation_artifact_document(document):
            return document.id
    return None


def main() -> int:
    db = SessionLocal()
    try:
        eval_documents = [
            document
            for document in db.scalars(select(Document))
            if is_evaluation_artifact_document(document)
        ]
        eval_document_ids = {document.id for document in eval_documents}
        eval_paths = [Path(document.storage_path) for document in eval_documents if document.storage_path]

        golden_raw_email_ids = set(
            db.scalars(
                select(RawEmail.id).where(RawEmail.raw_payload["golden_sample"].as_boolean() == True)  # noqa: E712
            )
        )

        email_delete_count = 0
        raw_email_delete_count = 0
        document_delete_count = 0

        if golden_raw_email_ids:
            email_delete_count = db.execute(
                delete(Email).where(Email.raw_email_id.in_(golden_raw_email_ids))
            ).rowcount or 0
            raw_email_delete_count = db.execute(
                delete(RawEmail).where(RawEmail.id.in_(golden_raw_email_ids))
            ).rowcount or 0

        if eval_document_ids:
            document_delete_count = db.execute(
                delete(Document).where(Document.id.in_(eval_document_ids))
            ).rowcount or 0

        db.commit()

        for path in eval_paths:
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

        tmp_eval_dir = (ROOT.parent / "storage" / "tmp_eval_docs").resolve()
        if tmp_eval_dir.exists():
            shutil.rmtree(tmp_eval_dir, ignore_errors=True)

        rebuilt_profile = False
        trusted_cv_id = _latest_trusted_cv_id(db)
        if trusted_cv_id:
            trusted_document = db.get(Document, trusted_cv_id)
            if trusted_document:
                if ai_agents_enabled():
                    run_profile_ingestion_agent(db, document_id=trusted_document.id)
                else:
                    extract_profile_from_latest_cv(db)
                rebuilt_profile = True

        print(
            {
                "deleted_eval_documents": document_delete_count,
                "deleted_eval_emails": email_delete_count,
                "deleted_eval_raw_emails": raw_email_delete_count,
                "rebuilt_profile": rebuilt_profile,
                "trusted_cv_id": trusted_cv_id,
            }
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
