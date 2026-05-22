from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation_harness import build_report, load_golden_set


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "evals" / "agent_golden_set.json"


def _format_summary(report: dict[str, object]) -> str:
    inbox = report["inbox_triage"]
    profile = report["profile_extraction"]
    cost = report.get("cost_summary", {})
    profile_mode = report.get("profile_evaluation_mode", "dataset_only")
    profile_summary = (
        f"- samples: {profile['sample_count']}\n"
        f"- status: {profile['status']}\n"
    )
    if profile["status"] == "evaluated":
        profile_summary += (
            f"- overall_score: {profile['overall_score']}\n"
            f"- evidence_coverage: {profile['evidence_coverage']}\n"
            f"- skill_recall: {profile['skill_recall']}\n"
            f"- project_recall: {profile['project_recall']}\n"
            f"- communication_style_recall: {profile['communication_style_recall']}\n"
            f"- work_preferences_recall: {profile['work_preferences_recall']}\n"
        )
    else:
        expected_fields = profile.get("expected_fields", [])
        profile_summary += (
            f"- expected_fields: {', '.join(expected_fields) if expected_fields else 'none'}\n"
            f"- note: {profile.get('note', 'n/a')}\n"
        )
    return (
        "Inbox triage\n"
        f"- samples: {inbox['sample_count']}\n"
        f"- precision: {inbox['precision']}\n"
        f"- recall: {inbox['recall']}\n"
        f"- false_positive_rate: {inbox['false_positive_rate']}\n"
        f"- category_accuracy: {inbox['category_accuracy']}\n\n"
        "Profile extraction\n"
        f"- mode: {profile_mode}\n"
        f"{profile_summary}\n"
        "Cost summary\n"
        f"- model calls captured: {cost.get('total_calls', 0)}\n"
        f"- estimated tokens: {cost.get('total_estimated_tokens', 0)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate CareerOps agent baselines against a golden set.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to the golden set JSON file.")
    parser.add_argument("--output", type=Path, help="Optional JSON report output path.")
    parser.add_argument(
        "--run-profile-ai",
        action="store_true",
        help="Run the LangGraph-backed profile extraction evaluator on the profile samples.",
    )
    args = parser.parse_args()

    dataset = load_golden_set(args.dataset)
    report = build_report(dataset, include_profile_ai=args.run_profile_ai)

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(_format_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
