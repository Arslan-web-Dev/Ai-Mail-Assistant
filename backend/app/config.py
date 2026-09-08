"""
Centralized application settings.

All secrets are read from environment variables only. Nothing here is ever
sent to the frontend. Import `settings` everywhere instead of calling
os.environ directly, so there is exactly one source of truth.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    app_secret_key: str = "dev-secret-change-me"
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    allowed_origins: str = "http://localhost:3000"

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    # Google OAuth / Gmail
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/gmail/callback"
    google_oauth_scopes: str = (
        "openid email profile "
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/gmail.send"
    )

    # Token encryption
    token_encryption_key: str = ""

    # Gmail push notifications (Pub/Sub) — Module 3
    google_pubsub_topic: str = ""        # e.g. projects/my-project/topics/gmail-push
    google_pubsub_audience: str = ""     # webhook URL Pub/Sub pushes to, used to verify OIDC token
    google_pubsub_service_account: str = ""  # expected token issuer/email for push auth verification
    watch_renewal_days: int = 6          # Gmail watch() expires after 7 days; renew before then

    # OpenAI (later modules)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Redis / Celery (later modules)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def google_scopes_list(self) -> List[str]:
        return [s.strip() for s in self.google_oauth_scopes.split(" ") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
