from __future__ import annotations

import re
import unicodedata

try:
    from ftfy import fix_text as _fix_text
except ImportError:  # pragma: no cover - optional fallback for older environments
    _fix_text = None


_ACUTE_MAP = {
    "a": "\u00e1",
    "e": "\u00e9",
    "i": "\u00ed",
    "\u0131": "\u00ed",
    "o": "\u00f3",
    "u": "\u00fa",
    "A": "\u00c1",
    "E": "\u00c9",
    "I": "\u00cd",
    "\u0130": "\u00cd",
    "O": "\u00d3",
    "U": "\u00da",
}
_TILDE_MAP = {
    "n": "\u00f1",
    "N": "\u00d1",
}
_DIAERESIS_MAP = {
    "u": "\u00fc",
    "U": "\u00dc",
}
_BULLET_MARKERS = {"-", "*", "\u2022", "\u25e6"}


def _repair_marker_accents(text: str) -> str:
    def replace_acute(match: re.Match[str]) -> str:
        return _ACUTE_MAP.get(match.group(1), match.group(1))

    def replace_tilde(match: re.Match[str]) -> str:
        return _TILDE_MAP.get(match.group(1), match.group(1))

    def replace_diaeresis(match: re.Match[str]) -> str:
        return _DIAERESIS_MAP.get(match.group(1), match.group(1))

    repaired = re.sub(r"[\u00b4`]\s*([aeiouAEIOU\u0131\u0130])", replace_acute, text)
    repaired = re.sub(r"[\u02dc~]\s*([nN])", replace_tilde, repaired)
    repaired = re.sub(r"[\u00a8]\s*([uU])", replace_diaeresis, repaired)
    return repaired


def repair_mojibake(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value

    if _fix_text is not None:
        cleaned = _fix_text(cleaned)
        cleaned = _fix_text(cleaned)

    replacements = {
        "\u00a0": " ",
        "\u00c2": "",
        "\u0091": "",
        "\u0098": "",
        "\u0099": "",
        "\u00e2\u20ac\u201d": "-",
        "\u00e2\u20ac\u201c": "-",
        "\u2014": "-",
        "\u2013": "-",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2026": "...",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)

    cleaned = _repair_marker_accents(cleaned)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = re.sub(r"[\u034f\u200b-\u200f\u202a-\u202e]", " ", cleaned)
    cleaned = re.sub(r"[\u0000-\u0008\u000b-\u001f\u007f-\u009f]", "", cleaned)
    cleaned = re.sub(r"[ \t]+([,.;:!?])", r"\1", cleaned)
    return cleaned


def normalize_text_block(value: str | None) -> str | None:
    repaired = repair_mojibake(value)
    if repaired is None:
        return None
    repaired = repaired.replace("\r\n", "\n").replace("\r", "\n")
    repaired = re.sub(r"[ \t]+", " ", repaired)
    repaired = re.sub(r" *\n *", "\n", repaired)
    repaired = re.sub(r"\n{3,}", "\n\n", repaired)
    return repaired.strip()


def normalize_text_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for value in values:
        cleaned = normalize_text_block(value)
        if cleaned:
            normalized.append(cleaned)
    return normalized


def normalize_display_text(value: str | None, *, fallback: str | None = None) -> str | None:
    cleaned = normalize_text_block(value)
    if cleaned:
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
    return fallback


def normalize_display_list(values: list[str] | None) -> list[str]:
    return normalize_text_list(values)


def normalize_bullet_text(value: str | None) -> str | None:
    cleaned = normalize_display_text(value)
    if not cleaned:
        return None
    marker = cleaned[0]
    if marker in _BULLET_MARKERS and len(cleaned) > 1:
        return cleaned[1:].strip()
    return cleaned
