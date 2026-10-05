from decimal import Decimal
from functools import cached_property

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

GOOGLE_ADS_API_VERSION = "v25"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./aln_hub_ia.db"
    # Public origin of the panel (https://app.example.com). OAuth callbacks return the user here.
    app_url: str = "http://localhost:3000"
    # Public base of this API as the browser and OAuth providers see it. In production the web
    # service proxies /api to the API, so this is usually "<app_url>/api".
    public_api_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"
    trust_proxy_headers: bool = True

    # Safety switches. Mutations stay blocked unless BOTH the global switch is off and the
    # provider flag is on.
    global_kill_switch: bool = True
    google_ads_mutations_enabled: bool = False
    tiktok_ads_mutations_enabled: bool = False
    default_daily_budget_limit: Decimal = Decimal("100.00")

    # Auth
    allow_signup: bool = False
    session_ttl_hours: int = 24 * 7
    session_cookie_name: str = "alnia_session"

    # Encryption: comma-separated Fernet keys, newest first (MultiFernet rotation).
    token_encryption_keys: str | None = None
    token_encryption_key: str | None = None  # legacy single key, still accepted

    # Google Ads
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_ads_developer_token: str | None = None
    google_ads_login_customer_id: str | None = None
    google_ads_daily_operation_quota: int = 15000

    # TikTok for Business (Marketing API)
    tiktok_app_id: str | None = None
    tiktok_app_secret: str | None = None

    # AI copilot (optional). Without a key the copilot answers from the deterministic audit.
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"

    # Worker
    run_worker_in_api: bool = False
    worker_poll_seconds: float = 2.0
    metrics_cache_minutes: int = 15
    metrics_sync_hour_utc: int = 6  # 03:00 in São Paulo

    sentry_dsn: str | None = None
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @cached_property
    def allowed_origins(self) -> list[str]:
        origins = {origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()}
        origins.add(self.app_url.rstrip("/"))
        return sorted(origins)

    @property
    def encryption_keys(self) -> list[str]:
        raw = self.token_encryption_keys or self.token_encryption_key or ""
        return [key.strip() for key in raw.split(",") if key.strip()]

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_ads_developer_token)

    @property
    def tiktok_configured(self) -> bool:
        return bool(self.tiktok_app_id and self.tiktok_app_secret)

    def mutations_enabled(self, provider: str) -> bool:
        if self.global_kill_switch:
            return False
        if provider == "GOOGLE_ADS":
            return self.google_ads_mutations_enabled
        if provider == "TIKTOK_ADS":
            return self.tiktok_ads_mutations_enabled
        return False

    @model_validator(mode="after")
    def production_requirements(self) -> "Settings":
        if not self.is_production:
            return self
        missing = []
        if self.database_url.startswith("sqlite"):
            missing.append("DATABASE_URL (Postgres)")
        if not self.encryption_keys:
            missing.append("TOKEN_ENCRYPTION_KEYS")
        if not self.app_url.startswith("https://"):
            missing.append("APP_URL (https)")
        if not self.public_api_url.startswith("https://"):
            missing.append("PUBLIC_API_URL (https)")
        if missing:
            raise ValueError("Configuração de produção incompleta: " + ", ".join(missing))
        return self


settings = Settings()
