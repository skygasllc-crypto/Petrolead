"""Application configuration.

Settings are loaded from environment variables / a `.env` file via
pydantic-settings. Nothing in this module should ever contain a real
secret — see `.env.example` for the variables this app understands.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    app_name: str = "PetroLead"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api"

    # --- Database ---
    # Defaults to a local SQLite file so the app is runnable with zero
    # external setup. Point DATABASE_URL at Postgres for staging/production.
    database_url: str = "sqlite:///./petrolead.db"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Search providers ---
    google_cse_api_key: str | None = None
    google_cse_engine_id: str | None = None
    bing_search_api_key: str | None = None
    serpapi_api_key: str | None = None
    searchapi_io_api_key: str | None = None
    serper_api_key: str | None = None
    search_provider: str = "mock"

    # --- Contact-data enrichment (optional) ---
    # https://hunter.io/ — resolves a specific person's likely business
    # email given their name and employer's domain. Only used as a
    # best-effort enrichment on top of the LinkedIn profile-snippet lookup
    # (see `discovery/email_finder.py`); never required.
    hunter_io_api_key: str | None = None

    # --- HTTP / extraction ---
    http_timeout_seconds: int = 10
    http_user_agent: str = "PetroLeadBot/1.0 (+https://example.com/bot)"
    max_concurrent_fetches: int = 5

    # --- Background jobs ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Rate limiting ---
    rate_limit_per_minute: int = 60

    # --- Authentication ---
    # Dev-only default so the app runs with zero setup; MUST be overridden
    # (a long random value) outside development — see .env.example.
    secret_key: str = "dev-insecure-secret-key-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7  # 1 week

    # Comma-separated email addresses that get admin access (view every
    # account, block/unblock). Synced onto the matching User row on every
    # register/login — see `app.api.auth`. Empty by default: nobody is an
    # admin until you set this.
    admin_emails: str = ""

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def using_default_secret_key(self) -> bool:
        return self.secret_key == "dev-insecure-secret-key-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
