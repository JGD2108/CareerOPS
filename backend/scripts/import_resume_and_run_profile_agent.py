from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.documents import store_local_document
from app.langgraph_agents import run_profile_ingestion_agent
from app.models import SourceType


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_resume_and_run_profile_agent.py <absolute-path-to-resume.pdf>")
        return 1

    resume_path = sys.argv[1]
    db = SessionLocal()
    try:
        document = store_local_document(db, source_type=SourceType.CV, local_path=resume_path)
        profile = run_profile_ingestion_agent(db, document_id=document.id)
        print(
            {
                "document_id": str(document.id),
                "document_filename": document.original_filename,
                "profile_id": str(profile.id),
                "display_name": profile.display_name,
                "skills": len(profile.skills),
                "projects": len(profile.projects),
                "experiences": len(profile.experiences),
            }
        )
        return 0
    except Exception as error:
        print(f"ERROR: {error}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
