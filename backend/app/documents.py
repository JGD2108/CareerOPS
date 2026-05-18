from hashlib import sha256
import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import write_audit_log
from app.config import get_settings
from app.models import Document, SourceType


TEXT_EXTENSIONS = {".txt", ".md", ".tex"}
DOCX_EXTENSIONS = {".docx"}


def _storage_root() -> Path:
    settings = get_settings()
    root = Path(settings.local_storage_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[2] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def _extract_pdf_text(path: Path) -> tuple[str, dict]:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(text.strip())

    return "\n\n".join(page for page in pages if page), {"page_count": len(reader.pages)}


def _extract_text(path: Path, content_type: str | None) -> tuple[str | None, dict]:
    suffix = path.suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        return _extract_pdf_text(path)
    if suffix in DOCX_EXTENSIONS or content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        document = DocxDocument(str(path))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs), {"parser": "docx", "paragraph_count": len(paragraphs)}
    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8"), {"parser": "plain_text"}
    return None, {"parser": "unsupported"}


def _store_document_bytes(
    db: Session,
    *,
    filename: str,
    content: bytes,
    source_type: SourceType,
    content_type: str | None,
) -> Document:
    checksum = sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.checksum == checksum))
    if existing:
        return existing

    documents_dir = _storage_root() / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)

    storage_name = f"{uuid4()}_{_safe_filename(filename or 'document')}"
    storage_path = documents_dir / storage_name
    storage_path.write_bytes(content)

    extracted_text, metadata = _extract_text(storage_path, content_type)
    document = Document(
        source_type=source_type,
        original_filename=filename or storage_name,
        storage_path=str(storage_path),
        content_type=content_type,
        checksum=checksum,
        extracted_text=extracted_text,
        document_metadata={
            **metadata,
            "size_bytes": len(content),
            "original_content_type": content_type,
        },
    )
    db.add(document)
    db.flush()
    write_audit_log(
        db,
        event_type="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        details={
            "source_type": source_type,
            "original_filename": document.original_filename,
            "checksum": checksum,
        },
    )
    db.commit()
    db.refresh(document)
    return document


async def store_uploaded_document(db: Session, *, file: UploadFile, source_type: SourceType) -> Document:
    content = await file.read()
    return _store_document_bytes(
        db,
        filename=file.filename or "document",
        content=content,
        source_type=source_type,
        content_type=file.content_type,
    )


def store_local_document(db: Session, *, source_type: SourceType, local_path: str) -> Document:
    path = Path(local_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Local document not found at {path}")
    content_type, _ = mimetypes.guess_type(str(path))
    return _store_document_bytes(
        db,
        filename=path.name,
        content=path.read_bytes(),
        source_type=source_type,
        content_type=content_type,
    )


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))
