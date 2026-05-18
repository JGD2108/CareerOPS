import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gmail_integration import authenticate_gmail


def main() -> int:
    status = authenticate_gmail()
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
