import json
import sys

import httpx


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "category:primary newer_than:30d"
    payload = {"query": query, "max_results": 25}
    response = httpx.post("http://127.0.0.1:8000/api/v1/gmail/sync", json=payload, timeout=120.0)
    print(response.status_code)
    print(json.dumps(response.json(), indent=2))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
