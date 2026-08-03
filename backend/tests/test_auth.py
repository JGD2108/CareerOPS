from fastapi import HTTPException

from app import auth


def test_app_auth_allows_local_when_disabled(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", False)

    assert auth.validate_app_auth(None) is None


def test_app_auth_rejects_invalid_key(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", True)
    monkeypatch.setattr(auth.settings, "allow_loopback_auth_bypass", False)
    monkeypatch.setattr(auth.settings, "app_api_key", "secret")

    try:
        auth.validate_app_auth("wrong")
    except HTTPException as error:
        assert error.status_code == 401
    else:
        raise AssertionError("Expected invalid API key to be rejected.")


def test_app_auth_accepts_valid_session_cookie(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", True)
    monkeypatch.setattr(auth.settings, "allow_loopback_auth_bypass", False)
    monkeypatch.setattr(auth.settings, "app_api_key", "secret")
    monkeypatch.setattr(auth.settings, "app_session_max_age_seconds", 60)

    cookie_value = auth.create_session_cookie_value()

    assert auth.validate_app_auth(None, "/api/v1/jobs", session_cookie=cookie_value) is None
    short_lived_cookie = auth.create_session_cookie_value(now=100)
    assert auth.validate_session_cookie(short_lived_cookie, now=159)
    assert not auth.validate_session_cookie(short_lived_cookie, now=161)


def test_auth_status_reports_authenticated_session(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", True)
    monkeypatch.setattr(auth.settings, "allow_loopback_auth_bypass", False)
    monkeypatch.setattr(auth.settings, "app_api_key", "secret")

    cookie_value = auth.create_session_cookie_value()

    assert auth.auth_status(session_cookie=cookie_value, client_host="203.0.113.10") == {
        "enabled": True,
        "configured": True,
        "authenticated": True,
        "mode": "session",
    }


def test_app_auth_accepts_valid_key(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", True)
    monkeypatch.setattr(auth.settings, "allow_loopback_auth_bypass", False)
    monkeypatch.setattr(auth.settings, "app_api_key", "secret")

    assert auth.validate_app_auth("secret") is None


def test_app_auth_allows_public_oauth_callback(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", True)
    monkeypatch.setattr(auth.settings, "app_api_key", "secret")

    assert auth.validate_app_auth(None, "/api/v1/gmail/oauth/callback") is None


def test_app_auth_allows_loopback_desktop_client(monkeypatch):
    monkeypatch.setattr(auth.settings, "app_auth_enabled", True)
    monkeypatch.setattr(auth.settings, "allow_loopback_auth_bypass", True)
    monkeypatch.setattr(auth.settings, "app_api_key", "secret")

    assert auth.validate_app_auth(None, "/api/v1/jobs", client_host="127.0.0.1") is None
