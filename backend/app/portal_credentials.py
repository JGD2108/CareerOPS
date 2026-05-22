from __future__ import annotations

from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Application, PortalCredential
from app.schemas import PortalCredentialCreate, PortalCredentialUpdate


def generate_local_encryption_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _resolve_encryption_key(key: str | None = None) -> bytes:
    resolved = key or get_settings().portal_credential_encryption_key
    if not resolved:
        raise ValueError(
            "PORTAL_CREDENTIAL_ENCRYPTION_KEY is not configured. "
            "Generate a Fernet key and store it outside Postgres before saving portal credentials."
        )
    return resolved.encode("utf-8")


def encrypt_portal_password(password: str, key: str | None = None) -> str:
    if not password:
        raise ValueError("Portal password cannot be empty.")
    return Fernet(_resolve_encryption_key(key)).encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_portal_password(encrypted_password: str, key: str | None = None) -> str:
    try:
        return Fernet(_resolve_encryption_key(key)).decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except InvalidToken as error:
        raise ValueError("Portal credential could not be decrypted with the configured key.") from error


def list_portal_credentials(db: Session, application_id: UUID) -> list[PortalCredential]:
    return (
        db.query(PortalCredential)
        .filter(PortalCredential.application_id == application_id)
        .order_by(PortalCredential.created_at.desc())
        .all()
    )


def create_portal_credential(
    db: Session,
    application_id: UUID,
    payload: PortalCredentialCreate,
) -> PortalCredential | None:
    application = db.get(Application, application_id)
    if not application:
        return None

    credential = PortalCredential(
        application_id=application.id,
        company_id=application.job.company_id if application.job else None,
        portal_name=payload.portal_name,
        portal_url=str(payload.portal_url),
        username=payload.username,
        encrypted_password=encrypt_portal_password(payload.password),
        encryption_key_id=get_settings().portal_credential_encryption_key_id,
        mfa_enabled=payload.mfa_enabled,
        daily_check_allowed=payload.daily_check_allowed,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def update_portal_credential(
    db: Session,
    credential_id: UUID,
    payload: PortalCredentialUpdate,
) -> PortalCredential | None:
    credential = db.get(PortalCredential, credential_id)
    if not credential:
        return None

    if payload.portal_name is not None:
        credential.portal_name = payload.portal_name
    if payload.portal_url is not None:
        credential.portal_url = str(payload.portal_url)
    if payload.username is not None:
        credential.username = payload.username
    if payload.password is not None:
        credential.encrypted_password = encrypt_portal_password(payload.password)
        credential.encryption_key_id = get_settings().portal_credential_encryption_key_id
    if payload.mfa_enabled is not None:
        credential.mfa_enabled = payload.mfa_enabled
    if payload.daily_check_allowed is not None:
        credential.daily_check_allowed = payload.daily_check_allowed

    db.commit()
    db.refresh(credential)
    return credential


def delete_portal_credential(db: Session, credential_id: UUID) -> bool:
    credential = db.get(PortalCredential, credential_id)
    if not credential:
        return False
    db.delete(credential)
    db.commit()
    return True
