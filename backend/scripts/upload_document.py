from pathlib import Path
import sys

import httpx


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/upload_document.py <source_type> <file_path>")

    source_type = sys.argv[1]
    file_path = Path(sys.argv[2])
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    with file_path.open("rb") as file_handle:
        response = httpx.post(
            "http://127.0.0.1:8000/api/v1/documents/upload",
            data={"source_type": source_type},
            files={"file": (file_path.name, file_handle)},
            timeout=30,
        )

    response.raise_for_status()
    payload = response.json()
    extracted_text = payload.get("extracted_text") or ""
    metadata = payload.get("document_metadata") or {}

    print(f"id: {payload['id']}")
    print(f"source_type: {payload['source_type']}")
    print(f"filename: {payload['original_filename']}")
    print(f"checksum: {payload['checksum'][:12]}")
    print(f"text_length: {len(extracted_text)}")
    print(f"metadata: {metadata}")


if __name__ == "__main__":
    main()
