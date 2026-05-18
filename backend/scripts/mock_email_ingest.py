import json

import httpx


PAYLOAD = {
    "from_header": "Alex Recruiter <alex@alias-test-labs.com>",
    "subject": "Interview availability for Backend Engineer, AI Workflows",
    "body_text": "Hi Jose, we'd love to schedule an interview this week. Please share your availability for a 45 minute call.",
}


def main() -> int:
    response = httpx.post("http://127.0.0.1:8000/api/v1/emails/mock-ingest", json=PAYLOAD, timeout=60.0)
    print(response.status_code)
    print(json.dumps(response.json(), indent=2))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
