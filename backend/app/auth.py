from fastapi import Header, HTTPException, status

from app.config import get_settings


settings = get_settings()


def auth_status() -> dict[str, bool]:
    return {"enabled": settings.app_auth_enabled, "configured": bool(settings.app_api_key)}


def require_app_auth(x_careerops_key: str | None = Header(default=None)) -> None:
    if not settings.app_auth_enabled:
        return
    if not settings.app_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_AUTH_ENABLED is true but APP_API_KEY is not configured.",
        )
    if x_careerops_key != settings.app_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid CareerOps API key.")
