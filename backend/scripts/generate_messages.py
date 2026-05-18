import sys

import httpx


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/generate_messages.py <job_id>")

    job_id = sys.argv[1]
    payload = {
        "draft_types": ["linkedin", "application_email", "short_cover_letter"],
        "tone": "natural-professional",
        "language": "english",
    }
    response = httpx.post(
        f"http://127.0.0.1:8000/api/v1/jobs/{job_id}/message-drafts",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    drafts = response.json()

    print(f"draft_count: {len(drafts)}")
    for draft in drafts:
        print("---")
        print(f"id: {draft['id']}")
        print(f"type: {draft['draft_type']}")
        print(f"status: {draft['status']}")
        if draft["subject"]:
            print(f"subject: {draft['subject']}")
        print(draft["body"])


if __name__ == "__main__":
    main()
