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
    print(f"LLM triaged {len(triaged)} emails")
    for e in triaged:
        # Avoid potential None errors for print
        id_val = getattr(e, 'id', 'N/A')
        cat_val = getattr(e, 'category', 'N/A')
        from_val = getattr(e, 'from_email', 'N/A')
        reply_val = getattr(e, 'requires_reply', 'N/A')
        print(f"{id_val} {cat_val} {from_val} requires_reply={reply_val}")
finally:
    db.close()
