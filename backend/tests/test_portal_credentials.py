import pytest

from app.portal_credentials import (
    decrypt_portal_password,
    encrypt_portal_password,
    generate_local_encryption_key,
)
from app.schemas import PortalCredentialRead


def test_portal_password_encryption_round_trip():
    key = generate_local_encryption_key()
    plaintext = "not-for-logs"

    encrypted = encrypt_portal_password(plaintext, key=key)

    assert encrypted != plaintext
    assert plaintext not in encrypted
    assert decrypt_portal_password(encrypted, key=key) == plaintext


def test_portal_password_wrong_key_fails():
    encrypted = encrypt_portal_password("secret", key=generate_local_encryption_key())

    with pytest.raises(ValueError):
        decrypt_portal_password(encrypted, key=generate_local_encryption_key())


def test_portal_credential_read_schema_does_not_expose_password_fields():
    fields = set(PortalCredentialRead.model_fields)

    assert "password" not in fields
    assert "encrypted_password" not in fields
