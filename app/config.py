"""Application configuration.

Settings are loaded from environment variables / a `.env` file via
pydantic-settings. Nothing in this module should ever contain a real
secret — see `.env.example` for the variables this app understands.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Verification providers with an adapter written for them. "mx" means no
# provider: DNS only, so nothing is ever graded "deliverable". Kept here as a
# literal rather than imported from app.discovery.email_verification, because
# the discovery modules import this one and the reverse would risk a cycle —
# keep the two in step when an adapter is added.
SUPPORTED_EMAIL_VERIFY_PROVIDERS = frozenset({"mx"})


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
    # Apply pending Alembic migrations when the app starts. Turn off when
    # several app processes share one database, and run
    # `alembic upgrade head` once per deploy instead.
    run_migrations_on_startup: bool = True

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

    # --- Email verification ---
    # Which service confirms that a mailbox exists. "mx" (the default) has
    # none: it checks DNS only, which proves the domain accepts mail but not
    # that the address does, so nothing is ever graded "deliverable". Set a
    # real provider and its key to get mailbox-level verdicts.
    email_verify_provider: str = "mx"
    email_verify_api_key: str | None = None

    # --- Contact-data enrichment (optional) ---
    # https://hunter.io/ — resolves a specific person's likely business
    # email given their name and employer's domain. Only used as a
    # best-effort enrichment on top of the LinkedIn profile-snippet lookup
    # (see `discovery/email_finder.py`); never required.
    hunter_io_api_key: str | None = None

    # --- HTTP / extraction ---
    http_timeout_seconds: int = 10
    # Sent on every page we fetch. Site owners read this in their logs and
    # use it to decide whether to allow us, so it points at a real page.
    http_user_agent: str = "PetroLeadBot/1.0 (+https://petrolead.org/bot)"
    max_concurrent_fetches: int = 5

    # --- Background jobs ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Rate limiting ---
    # Requests per minute per client address, counted per process (see
    # `app.core.middleware`). The auth allowance is much smaller because
    # that's where password guessing happens.
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    auth_rate_limit_per_minute: int = 10
    # Behind a load balancer the socket address is the balancer's, so the
    # X-Forwarded-For header identifies the caller instead. Only turn this
    # on when a proxy you control really does set it — otherwise callers can
    # forge it and hand themselves a fresh rate-limit allowance per request.
    trust_proxy_headers: bool = False

    # --- API documentation ---
    # /docs, /redoc and /openapi.json describe every endpoint and schema.
    # Useful while developing, an unnecessary map of the attack surface in
    # production. Defaults to on in development only.
    docs_enabled: bool | None = None

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

    # --- Plans & credits ---
    # When on, every non-admin account needs a plan, spends email credits
    # on person lookups, and is held to its plan's limits — see
    # `app.services.billing_service`. Admins are never limited.
    billing_enforced: bool = True

    # --- Crypto payments ---
    # Public receiving addresses shown to customers at checkout; a coin is
    # only offered once its address is set. Never put private keys or seed
    # phrases anywhere in this app — confirming payments is done by hand.
    crypto_btc_address: str | None = None
    crypto_usdt_trc20_address: str | None = None
    crypto_trx_address: str | None = None
    # Minutes a BTC/TRX price quote holds before an unpaid order expires.
    crypto_quote_minutes: int = 60
    # Optional free CoinGecko "Demo" key for steadier BTC/TRX price quotes.
    coingecko_api_key: str | None = None

    # --- Email (optional) ---
    # When set, admins get an email for every payment waiting for confirmation.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    # Where the web app is served — used for links in those emails.
    app_base_url: str = "http://localhost:5173"

    # --- Logging ---
    log_level: str = "INFO"

    @field_validator("docs_enabled", "email_verify_api_key", mode="before")
    @classmethod
    def empty_string_means_unset(cls, value: object) -> object:
        """A variable set to nothing — `DOCS_ENABLED=` in a copied .env, or an
        empty field in a platform dashboard — means "not configured". Treat it
        as unset, rather than refusing to start on an unparseable bool or
        handing a provider an empty string as its API key."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("email_verify_provider")
    @classmethod
    def known_verification_provider(cls, value: str) -> str:
        """Refuse to start on a provider with no adapter.

        Falling back to DNS-only would be worse than not starting: the
        setting would appear to be configured while every address came back
        unconfirmed, and the first sign of trouble would be bounced mail.
        """
        name = (value or "").strip().lower()
        if name not in SUPPORTED_EMAIL_VERIFY_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_EMAIL_VERIFY_PROVIDERS))
            raise ValueError(
                f"EMAIL_VERIFY_PROVIDER={value!r} has no adapter yet (supported: {supported}). "
                "Add one in app/discovery/email_verification.py and list it in "
                "SUPPORTED_EMAIL_VERIFY_PROVIDERS before setting it."
            )
        return name

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Managed platforms hand out `postgres://` URLs, which SQLAlchemy 2
        rejects — it wants an explicit driver, and psycopg 3 is what's
        installed. Rewriting here means a platform's connection string can be
        used verbatim."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def refuse_insecure_production_secrets(self) -> Settings:
        """Refuse to start outside development with the shared dev signing
        key. Anyone who has read this open-source default could otherwise
        mint a valid session token for any account, so this is a hard stop
        rather than a warning that scrolls past in a deploy log."""
        if self.app_env != "development" and self.using_default_secret_key:
            raise ValueError(
                "SECRET_KEY is still the insecure development default while APP_ENV="
                f"{self.app_env!r}. Generate one with: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def using_default_secret_key(self) -> bool:
        return self.secret_key == "dev-insecure-secret-key-change-me"

    @property
    def serve_docs(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
