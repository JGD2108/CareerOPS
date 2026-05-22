from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any, Callable

from app.ai_client import ai_agents_enabled
from app.ai_schemas import AIProfileExtraction
from app.config import get_settings
from app.gmail_integration import _classify_email
from app.langgraph_agents import extract_profile_from_text_with_ai
from app.models import EmailCategory

settings = get_settings()


CAREEROPS_RELEVANT_CATEGORIES = {
    EmailCategory.APPLICATION_CONFIRMATION,
    EmailCategory.INTERVIEW_INVITATION,
    EmailCategory.CODING_ASSESSMENT,
    EmailCategory.RECRUITER_FOLLOW_UP,
    EmailCategory.REJECTION,
    EmailCategory.OFFER,
    EmailCategory.DOCUMENTS_REQUESTED,
    EmailCategory.FORM_PENDING,
}

ProfilePredictor = Callable[[str], AIProfileExtraction]


def load_golden_set(dataset_path: Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Golden set must be a JSON object.")
    return data


def validate_golden_set(dataset: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    inbox_samples = dataset.get("inbox_triage", [])
    profile_samples = dataset.get("profile_extraction", [])

    for index, sample in enumerate(inbox_samples, start=1):
        for field in ["id", "subject", "from_email", "body_text", "expected"]:
            if field not in sample:
                errors.append(f"inbox_triage[{index}] missing field: {field}")
        expected = sample.get("expected", {})
        for field in ["category", "relevant_to_careerops", "requires_reply"]:
            if field not in expected:
                errors.append(f"inbox_triage[{index}].expected missing field: {field}")

    for index, sample in enumerate(profile_samples, start=1):
        for field in ["id", "document_text", "expected"]:
            if field not in sample:
                errors.append(f"profile_extraction[{index}] missing field: {field}")

    return errors


def evaluate_inbox_triage(samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(samples)
    expected_positive = 0
    predicted_positive = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    exact_category_matches = 0
    rows: list[dict[str, Any]] = []

    for sample in samples:
        expected = sample["expected"]
        predicted_category, predicted_urgency, predicted_requires_reply, predicted_action = _classify_email(
            sample["subject"],
            sample["body_text"],
            sample["from_email"],
        )

        expected_category = EmailCategory(expected["category"])
        expected_relevant = bool(expected["relevant_to_careerops"])
        predicted_relevant = predicted_category in CAREEROPS_RELEVANT_CATEGORIES

        expected_positive += int(expected_relevant)
        predicted_positive += int(predicted_relevant)
        true_positives += int(expected_relevant and predicted_relevant)
        false_positives += int(not expected_relevant and predicted_relevant)
        false_negatives += int(expected_relevant and not predicted_relevant)
        exact_category_matches += int(predicted_category == expected_category)

        rows.append(
            {
                "id": sample["id"],
                "expected_category": expected_category.value,
                "predicted_category": predicted_category.value,
                "expected_relevant_to_careerops": expected_relevant,
                "predicted_relevant_to_careerops": predicted_relevant,
                "expected_requires_reply": bool(expected["requires_reply"]),
                "predicted_requires_reply": predicted_requires_reply,
                "expected_urgency": expected.get("urgency"),
                "predicted_urgency": predicted_urgency,
                "predicted_suggested_action": predicted_action,
            }
        )

    precision = true_positives / predicted_positive if predicted_positive else 0.0
    recall = true_positives / expected_positive if expected_positive else 0.0
    false_positive_rate = false_positives / max(total - expected_positive, 1)
    category_accuracy = exact_category_matches / total if total else 0.0

    return {
        "sample_count": total,
        "expected_positive": expected_positive,
        "predicted_positive": predicted_positive,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "category_accuracy": round(category_accuracy, 4),
        "rows": rows,
    }


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.lower().strip().split())


def _normalize_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [_normalize_text(item) for item in values if _normalize_text(item)]


def _phrase_matches(expected_phrase: str, candidates: list[str]) -> bool:
    needle = _normalize_text(expected_phrase)
    if not needle:
        return False
    return any(needle in candidate or candidate in needle for candidate in candidates if candidate)


def score_profile_prediction(expected: dict[str, Any], predicted: AIProfileExtraction) -> dict[str, Any]:
    scalar_fields = ["display_name", "headline", "location"]
    scalar_total = 0
    scalar_matches = 0
    scalar_results: dict[str, bool | None] = {}
    for field in scalar_fields:
        expected_value = expected.get(field)
        if expected_value is None:
            scalar_results[field] = None
            continue
        scalar_total += 1
        predicted_value = getattr(predicted, field)
        matched = _phrase_matches(str(expected_value), [_normalize_text(predicted_value)])
        scalar_matches += int(matched)
        scalar_results[field] = matched

    predicted_skill_names = _normalize_list([skill.name for skill in predicted.skills])
    expected_skills = _normalize_list(expected.get("skills", []))
    matched_skills = [skill for skill in expected_skills if _phrase_matches(skill, predicted_skill_names)]
    skill_recall = len(matched_skills) / len(expected_skills) if expected_skills else 1.0

    project_candidates = _normalize_list(
        [
            " ".join(filter(None, [project.name, project.description or "", project.impact or ""]))
            for project in predicted.projects
        ]
    )
    expected_projects = _normalize_list(expected.get("projects", []))
    matched_projects = [project for project in expected_projects if _phrase_matches(project, project_candidates)]
    project_recall = len(matched_projects) / len(expected_projects) if expected_projects else 1.0

    predicted_comm_style = _normalize_list(predicted.communication_style)
    expected_comm_style = _normalize_list(expected.get("communication_style", []))
    matched_comm_style = [token for token in expected_comm_style if _phrase_matches(token, predicted_comm_style)]
    communication_style_recall = (
        len(matched_comm_style) / len(expected_comm_style) if expected_comm_style else 1.0
    )

    predicted_preferences = _normalize_list(predicted.work_preferences)
    expected_preferences = _normalize_list(expected.get("work_preferences", []))
    matched_preferences = [token for token in expected_preferences if _phrase_matches(token, predicted_preferences)]
    work_preferences_recall = (
        len(matched_preferences) / len(expected_preferences) if expected_preferences else 1.0
    )

    evidence_texts = (
        [skill.evidence_text for skill in predicted.skills]
        + [project.evidence_text for project in predicted.projects]
        + [experience.evidence_text for experience in predicted.experiences]
        + [education.evidence_text for education in predicted.education]
        + [certification.evidence_text for certification in predicted.certifications]
    )
    evidence_total = len(evidence_texts)
    evidence_backed = sum(1 for text in evidence_texts if _normalize_text(text))
    evidence_coverage = evidence_backed / evidence_total if evidence_total else 1.0

    overall_components = [
        scalar_matches / scalar_total if scalar_total else 1.0,
        skill_recall,
        project_recall,
        communication_style_recall,
        work_preferences_recall,
        evidence_coverage,
    ]
    overall_score = sum(overall_components) / len(overall_components)

    return {
        "scalar_field_accuracy": round(scalar_matches / scalar_total, 4) if scalar_total else 1.0,
        "skill_recall": round(skill_recall, 4),
        "project_recall": round(project_recall, 4),
        "communication_style_recall": round(communication_style_recall, 4),
        "work_preferences_recall": round(work_preferences_recall, 4),
        "evidence_coverage": round(evidence_coverage, 4),
        "overall_score": round(overall_score, 4),
        "matched_skills": matched_skills,
        "matched_projects": matched_projects,
        "matched_communication_style": matched_comm_style,
        "matched_work_preferences": matched_preferences,
        "scalar_results": scalar_results,
    }


def summarize_profile_dataset(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_count = len(samples)
    expected_fields = set()
    for sample in samples:
        expected = sample.get("expected", {})
        expected_fields.update(expected.keys())

    return {
        "sample_count": sample_count,
        "expected_fields": sorted(expected_fields),
        "status": "dataset_only",
        "note": "Pass include_profile_ai=True to run the LangGraph-backed profile extraction evaluator.",
    }


def evaluate_profile_extraction(
    samples: list[dict[str, Any]],
    *,
    predictor: ProfilePredictor | None = None,
) -> dict[str, Any]:
    if predictor is None:
        return summarize_profile_dataset(samples)

    rows: list[dict[str, Any]] = []
    aggregate_score = 0.0
    aggregate_evidence_coverage = 0.0
    aggregate_skill_recall = 0.0
    aggregate_project_recall = 0.0
    aggregate_comm_recall = 0.0
    aggregate_preferences_recall = 0.0

    for sample in samples:
        prediction = predictor(sample["document_text"])
        score = score_profile_prediction(sample["expected"], prediction)
        aggregate_score += score["overall_score"]
        aggregate_evidence_coverage += score["evidence_coverage"]
        aggregate_skill_recall += score["skill_recall"]
        aggregate_project_recall += score["project_recall"]
        aggregate_comm_recall += score["communication_style_recall"]
        aggregate_preferences_recall += score["work_preferences_recall"]
        rows.append(
            {
                "id": sample["id"],
                "predicted_display_name": prediction.display_name,
                "predicted_headline": prediction.headline,
                "predicted_location": prediction.location,
                **score,
            }
        )

    total = len(samples)
    return {
        "sample_count": total,
        "status": "evaluated",
        "overall_score": round(aggregate_score / total, 4) if total else 0.0,
        "evidence_coverage": round(aggregate_evidence_coverage / total, 4) if total else 0.0,
        "skill_recall": round(aggregate_skill_recall / total, 4) if total else 0.0,
        "project_recall": round(aggregate_project_recall / total, 4) if total else 0.0,
        "communication_style_recall": round(aggregate_comm_recall / total, 4) if total else 0.0,
        "work_preferences_recall": round(aggregate_preferences_recall / total, 4) if total else 0.0,
        "rows": rows,
    }


def _capture_summary() -> dict[str, int]:
    capture_dir = settings.eval_capture_dir
    captures_summary = {"total_calls": 0, "total_estimated_tokens": 0}
    try:
        if capture_dir:
            cap_path = Path(capture_dir)
            for file in cap_path.glob("capture_*.json"):
                try:
                    payload = json.loads(file.read_text(encoding="utf-8"))
                    captures_summary["total_calls"] += 1
                    captures_summary["total_estimated_tokens"] += int(payload.get("estimated_total_tokens", 0))
                except Exception:
                    continue
    except Exception:
        pass
    return captures_summary


def build_report(
    dataset: dict[str, list[dict[str, Any]]],
    *,
    include_profile_ai: bool = False,
) -> dict[str, Any]:
    errors = validate_golden_set(dataset)
    if errors:
        raise ValueError("Invalid golden set:\n- " + "\n- ".join(errors))

    profile_predictor: ProfilePredictor | None = None
    profile_evaluation_mode = "dataset_only"
    if include_profile_ai:
        if ai_agents_enabled():
            profile_predictor = extract_profile_from_text_with_ai
            profile_evaluation_mode = "langgraph_profile_agent"
        else:
            profile_evaluation_mode = "skipped_missing_openai_key"

    report = {
        "inbox_triage": evaluate_inbox_triage(dataset.get("inbox_triage", [])),
        "profile_extraction": evaluate_profile_extraction(
            dataset.get("profile_extraction", []),
            predictor=profile_predictor,
        ),
        "profile_evaluation_mode": profile_evaluation_mode,
        "cost_summary": _capture_summary(),
    }
    return report
