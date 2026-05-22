import sys
from pathlib import Path
ROOT = Path('.').resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.db import SessionLocal
from app.langgraph_agents import run_recent_unlinked_email_triage_agent

db = SessionLocal()
try:
    triaged = run_recent_unlinked_email_triage_agent(db, limit=50)
    print(f"Triaged {len(triaged)} emails")
    for e in triaged:
        print(f"{e.id} {e.category} {e.from_email}")
finally:
    db.close()
