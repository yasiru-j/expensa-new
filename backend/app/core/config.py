from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> backend -> repo root
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(_ROOT_ENV), ".env"), extra="ignore")

    environment: str = "development"

    # Database: owner runs migrations, app serves requests under RLS.
    database_url_owner: str
    database_url_app: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object storage. s3_endpoint_url is used for server-side calls (PUT, HEAD,
    # DELETE) — inside Docker this is the internal service hostname (minio:9000).
    # s3_public_endpoint_url is used ONLY when signing presigned GET URLs, since
    # those are followed by a browser outside the Docker network; an S3
    # signature covers the host, so a URL signed for one endpoint can't simply
    # be string-rewritten to another without invalidating the signature.
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "expensa-receipts"
    s3_region: str = "us-east-1"

    # Extraction (OpenAI). Model tiering (TRD §8): the cheap model runs first;
    # the escalated model is only tried when the cheap model's own confidence
    # is below the threshold or server-side validation flags an issue.
    openai_api_key: str = ""
    openai_extraction_model: str = "gpt-4o-mini"
    openai_extraction_model_escalated: str = "gpt-4o"
    model_tier_confidence_threshold: float = Field(0.7, ge=0, le=1)

    # Upload guardrails — enforced before any OpenAI call. A single-page PDF
    # is processed inline; a PDF with 2..max_pdf_pages pages is dispatched to
    # the async worker (only page 1 is ever extracted from either — this app
    # never splits or extracts multiple receipts from one document).
    max_upload_size_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 5

    # Cost control (TRD §8). Quota is enforced via an atomic increment-and-check
    # on the `usage` table; rate limiting via a Redis sliding window.
    monthly_extraction_quota: int = Field(50, ge=1)
    upload_rate_limit_per_hour: int = Field(20, ge=1)
    rate_limit_window_seconds: int = Field(3600, ge=1)

    # A `processing` row older than this (crash between the two upload
    # transactions, or a worker that never came back) gets swept to `failed`.
    stale_processing_minutes: int = Field(15, ge=1)

    # CORS / cookies
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    frontend_url: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
