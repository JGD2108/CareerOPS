from app.text_normalization import normalize_bullet_text
from app.text_normalization import normalize_display_text
from app.text_normalization import normalize_text_block


def test_normalize_text_block_repairs_utf8_mojibake() -> None:
    broken = "Jose David G\u00c3\u00b3mez De La Hoz"
    assert normalize_text_block(broken) == "Jose David G\u00f3mez De La Hoz"


def test_normalize_text_block_repairs_pdf_accent_markers() -> None:
    broken = "G\u00b4 omez de la Hoz"
    assert normalize_text_block(broken) == "G\u00f3mez de la Hoz"


def test_normalize_text_block_repairs_spanish_markers() -> None:
    broken = "espa\u02dc nol biling\u00a8 ue Ingenier\u00b4 \u0131a"
    assert normalize_text_block(broken) == "espa\u00f1ol biling\u00fce Ingenier\u00eda"


def test_normalize_text_block_normalizes_common_dash_artifacts() -> None:
    broken = "Software Engineer \u00e2\u20ac\u201d Backend"
    assert normalize_text_block(broken) == "Software Engineer - Backend"


def test_normalize_display_text_strips_html_after_normalizing() -> None:
    broken = "<p>Ingenier\u00c3\u00ada de datos</p>"
    assert normalize_display_text(broken) == "Ingenier\u00eda de datos"


def test_normalize_bullet_text_removes_leading_marker() -> None:
    assert normalize_bullet_text("\u2022 Lider\u00c3\u00a9 migraciones") == "Lider\u00e9 migraciones"
