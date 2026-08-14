from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./aln.db"
    redis_url: str = "redis://localhost:6379/0"
    google_ads_mutations_enabled: bool = False
    global_kill_switch: bool = True
    default_daily_budget_limit: str = "100.00"


settings = Settings()

