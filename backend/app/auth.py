from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


settings = get_settings()
PUBLIC_AUTH_PATHS = {"/api/v1/auth/status", "/api/v1/gmail/oauth/callback"}


def auth_status() -> dict[str, bool]:
    return {"enabled": settings.app_auth_enabled, "configured": bool(settings.app_api_key)}


def require_app_auth(
    request: Request | str | None = None,
    x_careerops_key: str | None = Header(default=None),
) -> None:
    if isinstance(request, str):
        x_careerops_key = request
        request = None

    if request and request.url.path in PUBLIC_AUTH_PATHS:
        return
    if not settings.app_auth_enabled:
        return
    if not settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_AUTH_ENABLED is true but APP_API_KEY is not configured.",
        )
    if x_careerops_key != settings.app_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid CareerOps API key.")
