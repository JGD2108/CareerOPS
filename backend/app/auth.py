from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


settings = get_settings()
PUBLIC_AUTH_PATHS = {"/api/v1/auth/status", "/api/v1/gmail/oauth/callback"}


def auth_status() -> dict[str, bool]:
    return {"enabled": settings.app_auth_enabled, "configured": bool(settings.app_api_key)}


def _is_loopback_client(client_host: str | None) -> bool:
    return client_host in {"127.0.0.1", "::1", "localhost"}


def validate_app_auth(
    x_careerops_key: str | None,
    request_path: str | None = None,
    client_host: str | None = None,
) -> None:
    if request_path in PUBLIC_AUTH_PATHS:
        return
    if not settings.app_auth_enabled:
        return
    if settings.allow_loopback_auth_bypass and _is_loopback_client(client_host):
        return
    if not settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_AUTH_ENABLED is true but APP_API_KEY is not configured.",
        )
    if x_careerops_key != settings.app_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid CareerOps API key.")


def require_app_auth(
    request: Request,
    x_careerops_key: str | None = Header(default=None),
) -> None:
    validate_app_auth(
        x_careerops_key=x_careerops_key,
        request_path=request.url.path,
        client_host=request.client.host if request.client else None,
    )
