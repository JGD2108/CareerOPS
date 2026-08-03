from app.documents import _extract_text
from app.documents import is_evaluation_artifact_document
from app.documents import validate_local_document_path
from app.models import Document, SourceType


def test_eval_document_detection_by_filename():
    document = Document(
        source_type=SourceType.CV,
        original_filename="profile_sample_4.txt",
        storage_path="C:/tmp/profile_sample_4.txt",
    )

    assert is_evaluation_artifact_document(document) is True


def test_eval_document_detection_by_metadata_flag():
    document = Document(
        source_type=SourceType.CV,
        original_filename="resume.pdf",
        storage_path="C:/tmp/resume.pdf",
        document_metadata={"eval_artifact": True},
    )

    assert is_evaluation_artifact_document(document) is True


def test_real_candidate_document_is_not_flagged():
    document = Document(
        source_type=SourceType.CV,
        original_filename="jose_david_resume.pdf",
        storage_path="C:/resume/jose_david_resume.pdf",
        document_metadata={"page_count": 2},
    )

    assert is_evaluation_artifact_document(document) is False


def test_validate_local_document_path_accepts_allowed_file(tmp_path, monkeypatch):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    resume_path = allowed_root / "resume.md"
    resume_path.write_text("# Resume", encoding="utf-8")

    monkeypatch.setattr(
        "app.documents._allowed_local_document_roots",
        lambda: [allowed_root.resolve()],
    )

    assert validate_local_document_path(str(resume_path)) == resume_path.resolve()


def test_validate_local_document_path_rejects_file_outside_allowed_roots(tmp_path, monkeypatch):
    allowed_root = tmp_path / "allowed"
    disallowed_root = tmp_path / "private"
    allowed_root.mkdir()
    disallowed_root.mkdir()
    secret_path = disallowed_root / "secret.txt"
    secret_path.write_text("top secret", encoding="utf-8")

    monkeypatch.setattr(
        "app.documents._allowed_local_document_roots",
        lambda: [allowed_root.resolve()],
    )

    try:
        validate_local_document_path(str(secret_path))
    except ValueError as error:
        assert "restricted to approved folders" in str(error)
    else:
        raise AssertionError("Expected outside path to be rejected.")


def test_validate_local_document_path_rejects_unsupported_extension(tmp_path, monkeypatch):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    binary_path = allowed_root / "archive.zip"
    binary_path.write_bytes(b"PK\x03\x04")

    monkeypatch.setattr(
        "app.documents._allowed_local_document_roots",
        lambda: [allowed_root.resolve()],
    )

    try:
        validate_local_document_path(str(binary_path))
    except ValueError as error:
        assert "Unsupported local document type" in str(error)
    else:
        raise AssertionError("Expected unsupported extension to be rejected.")


def test_tex_document_extraction_preserves_raw_latex_template(tmp_path):
    tex_path = tmp_path / "resume_template.tex"
    tex_content = "\\documentclass{article}\n\\begin{document}\n\\section{Summary}\nRaw   spacing\n\\end{document}\n"
    tex_path.write_text(tex_content, encoding="utf-8")

    extracted_text, metadata = _extract_text(tex_path, "application/x-tex")

    assert extracted_text == tex_content
    assert metadata["parser"] == "latex_template"
    assert metadata["cv_template"] is True
