from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.evaluation_harness import load_golden_set
from app.langgraph_agents import extract_profile_from_text_with_ai, triage_email_content_with_ai
from app.ai_client import ai_agents_enabled
from app.config import get_settings


def main() -> int:
    settings = get_settings()
    dataset_path = Path(__file__).resolve().parents[1] / "evals" / "agent_golden_set.json"
    dataset = load_golden_set(dataset_path)

    profile_runs = 0
    email_runs = 0
    if not ai_agents_enabled():
        print("Skipping batch capture: OPENAI_API_KEY not configured.")
        return 0

    for sample in dataset.get("profile_extraction", []):
        try:
            profile = extract_profile_from_text_with_ai(sample.get("document_text", ""))
            profile_runs += 1
            print(f"Profile captured: sample={sample['id']} -> skills={len(profile.skills)} projects={len(profile.projects)}")
        except Exception as error:
            print(f"Profile ingestion failed for {sample['id']}: {error}")

    for sample in dataset.get("inbox_triage", []):
        try:
            triaged = triage_email_content_with_ai(
                from_email=sample.get("from_email", "unknown@example.com"),
                from_name=sample.get("from_name"),
                subject=sample.get("subject"),
                snippet=(sample.get("body_text") or "")[:200],
                body_text=sample.get("body_text"),
            )
            email_runs += 1
            print(f"Email captured: sample={sample['id']} -> category={triaged.category}")
        except Exception as error:
            print(f"Email triage failed for {sample['id']}: {error}")

    cap_dir = Path(settings.eval_capture_dir) if settings.eval_capture_dir else None
    captures = []
    if cap_dir and cap_dir.exists():
        for file in cap_dir.glob("capture_*.json"):
            try:
                captures.append(json.loads(file.read_text(encoding="utf-8")))
            except Exception:
                continue

    print("\nBatch run complete")
    print(f"profile_runs: {profile_runs}, email_runs: {email_runs}, captures: {len(captures)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
