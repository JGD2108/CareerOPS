from pathlib import Path
import sys

import httpx


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/generate_cv_preview.py <job_id>")

    job_id = sys.argv[1]
    plans_response = httpx.get(f"http://127.0.0.1:8000/api/v1/jobs/{job_id}/cv-tailoring-plans", timeout=30)
    plans_response.raise_for_status()
    plans = plans_response.json()
    if not plans:
        raise SystemExit("No CV tailoring plans found for this job.")

    latest_plan = plans[0]
    preview_response = httpx.post(
        f"http://127.0.0.1:8000/api/v1/cv-versions/{latest_plan['id']}/latex-preview",
        timeout=30,
    )
    preview_response.raise_for_status()
    cv_version = preview_response.json()
    output_path = Path(cv_version["generated_file_path"])

    print(f"cv_version_id: {cv_version['id']}")
    print(f"status: {cv_version['status']}")
    print(f"latex_preview: {output_path}")
    print(f"exists: {output_path.exists()}")


if __name__ == "__main__":
    main()
