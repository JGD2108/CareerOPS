import json
import sys
from pathlib import Path

import httpx


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_job_discovery.py <payload.json>")
        return 1

    payload_path = Path(sys.argv[1])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    response = httpx.post("http://127.0.0.1:8000/api/v1/job-discovery/discover", json=payload, timeout=60.0)
    print(response.status_code)
    print(json.dumps(response.json(), indent=2))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
