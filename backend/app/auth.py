from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import Header, HTTPException, Request, Response, status

from app.config import get_settings


settings = get_settings()
PUBLIC_AUTH_PATHS = {
    "/api/v1/auth/status",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/gmail/oauth/callback",
}


def _auth_mode(client_host: str | None = None) -> str:
    if not settings.app_auth_enabled:
        return "disabled"
    if settings.allow_loopback_auth_bypass and _is_loopback_client(client_host):
        return "loopback"
    return "session"


def _is_loopback_client(client_host: str | None) -> bool:
    return client_host in {"127.0.0.1", "::1", "localhost"}


def _session_secret() -> bytes:
    if not settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_AUTH_ENABLED is true but APP_API_KEY is not configured.",
        )
    return settings.app_api_key.encode("utf-8")


def _sign_session_payload(payload: str) -> str:
    digest = hmac.new(_session_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_session_cookie_value(now: int | None = None) -> str:
    issued_at = int(now if now is not None else time.time())
    payload = f"careerops:{issued_at}"
    return f"{payload}.{_sign_session_payload(payload)}"


def validate_session_cookie(cookie_value: str | None, now: int | None = None) -> bool:
    if not cookie_value or "." not in cookie_value:
        return False
    payload, signature = cookie_value.rsplit(".", 1)
    expected_signature = _sign_session_payload(payload)
    if not hmac.compare_digest(signature, expected_signature):
        return False
    prefix, _, issued_at_raw = payload.partition(":")
    if prefix != "careerops":
        return False
    try:
        issued_at = int(issued_at_raw)
    except ValueError:
        return False
    current_time = int(now if now is not None else time.time())
    if issued_at > current_time + 60:
        return False
    return current_time - issued_at <= settings.app_session_max_age_seconds


def auth_status(
    *,
    session_cookie: str | None = None,
    client_host: str | None = None,
) -> dict[str, bool | str]:
    mode = _auth_mode(client_host)
    authenticated = (
        not settings.app_auth_enabled
        or mode == "loopback"
        or validate_session_cookie(session_cookie)
    )
    return {
        "enabled": settings.app_auth_enabled,
        "configured": bool(settings.app_api_key),
        "authenticated": authenticated,
        "mode": mode,
    }


def set_auth_cookie(response: Response) -> None:
    response.set_cookie(
        key=settings.app_session_cookie_name,
        value=create_session_cookie_value(),
        max_age=settings.app_session_max_age_seconds,
        httponly=True,
        secure=settings.app_env.lower() != "local",
        samesite="lax",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.app_session_cookie_name,
        httponly=True,
        secure=settings.app_env.lower() != "local",
        samesite="lax",
    )


def validate_app_auth(
    x_careerops_key: str | None,
    request_path: str | None = None,
    client_host: str | None = None,
    session_cookie: str | None = None,
) -> None:
    if request_path in PUBLIC_AUTH_PATHS:
        return
    if not settings.app_auth_enabled:
        return
    if settings.allow_loopback_auth_bypass and _is_loopback_client(client_host):
        return
    _session_secret()
    if validate_session_cookie(session_cookie):
        return
    if x_careerops_key != settings.app_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")


def require_app_auth(
    request: Request,
    x_careerops_key: str | None = Header(default=None),
) -> None:
    validate_app_auth(
        x_careerops_key=x_careerops_key,
        request_path=request.url.path,
        client_host=request.client.host if request.client else None,
        session_cookie=request.cookies.get(settings.app_session_cookie_name),
    )
