from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareerOps Agent"
    app_env: str = "local"
    database_url: str
    local_storage_dir: str = "../storage"
    enable_job_discovery_scheduler: bool = False
    discovery_schedule_hour: int = 8
    discovery_schedule_minute: int = 0
    enable_portal_status_scheduler: bool = False
    portal_status_schedule_hour: int = 9
    portal_status_schedule_minute: int = 0
    scheduler_timezone: str = "America/Bogota"
    gmail_credentials_file: str = "../storage/secrets/gmail_credentials.json"
    gmail_credentials_json: str | None = None
    gmail_token_file: str = "../storage/secrets/gmail_token.json"
    gmail_token_json: str | None = None
    gmail_oauth_redirect_uri: str = "http://127.0.0.1:8000/api/v1/gmail/oauth/callback"
    frontend_app_url: str | None = None
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    cors_origin_regex: str | None = None
    app_auth_enabled: bool = False
    allow_loopback_auth_bypass: bool = True
    app_api_key: str | None = None
    portal_credential_encryption_key: str | None = None
    portal_credential_encryption_key_id: str = "local-env"
    local_document_allowed_roots: str = "~/Documents,~/Desktop,~/Downloads,../storage"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_profile_model: str = "gpt-5-mini"
    openai_email_model: str = "gpt-5-nano"
    openai_job_model: str = "gpt-5-nano"
    openai_cv_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    ai_agent_max_input_chars: int = 24000
    eval_capture_dir: str | None = "../evals/captures"
    scheduler_lock_file: str = "../storage/locks/job_discovery_scheduler.lock"
    target_role_keywords: str = (
        "junior software engineer,software engineer,junior software developer,"
        "software developer,backend engineer,back-end engineer,backend developer,"
        "desarrollador backend,desarrollador de software,programador,"
        "full stack engineer,full-stack engineer,fullstack engineer,full stack developer,"
        "full-stack developer,fullstack developer,programador full stack,desarrollador full stack,"
        "data engineer,junior data engineer,developer de datos,ingeniero de datos,"
        "python developer,python engineer,ai engineer,junior ai engineer,ai developer,"
        "machine learning engineer,ml engineer,llm engineer"
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql://", 1)
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def resolve_config_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (Path(__file__).resolve().parents[2] / path).resolve()
