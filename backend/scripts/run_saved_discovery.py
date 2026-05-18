import json

import httpx


def main() -> int:
    response = httpx.post("http://127.0.0.1:8000/api/v1/job-discovery/run-saved", timeout=120.0)
    print(response.status_code)
    print(json.dumps(response.json(), indent=2))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
