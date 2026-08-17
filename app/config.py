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
    search_provider: str = "mock"

    # --- HTTP / extraction ---
    http_timeout_seconds: int = 10
    http_user_agent: str = "PetroLeadBot/1.0 (+https://example.com/bot)"
    max_concurrent_fetches: int = 5

    # --- Background jobs ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Rate limiting ---
    rate_limit_per_minute: int = 60

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
