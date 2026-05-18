from pathlib import Path
import json
import sys

import httpx


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/analyze_job.py <job_payload.json>")

    payload_path = Path(sys.argv[1])
    if not payload_path.exists():
        raise SystemExit(f"File not found: {payload_path}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    response = httpx.post("http://127.0.0.1:8000/api/v1/job-fit/analyze", json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
    score = result["score"]

    print(f"job_id: {result['job']['id']}")
    print(f"title: {result['job']['title']}")
    print(f"company: {result['job']['company']['name']}")
    print(f"score: {score['score']}")
    print(f"recommendation: {score['recommendation']}")
    print(f"matched: {len(score['matched_skills'])}")
    print(f"missing: {len(score['missing_or_weak_skills'])}")
    if score["reasons"]:
        print("reasons:")
        for reason in score["reasons"]:
            print(f"- {reason}")
    if score["risks"]:
        print("risks:")
        for risk in score["risks"]:
            print(f"- {risk}")
    if score["missing_or_weak_skills"]:
        print("missing_or_weak_skills:")
        for item in score["missing_or_weak_skills"]:
            print(f"- {item['required_skill']}: {item['reason']}")


if __name__ == "__main__":
    main()
