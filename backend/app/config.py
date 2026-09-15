from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, overridable via environment variables (prefix SHORTY_)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHORTY_", extra="ignore")

    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./shorty.db"
    machine_id: int = 1  # 0..1023; used for sqlite/dev. On Postgres a DB lease overrides this.
    auto_create_tables: bool = True  # dev/tests use create_all; prod uses Alembic (set False)

    cache_capacity: int = 10_000
    cache_ttl_seconds: int = 300

    rate_limit_capacity: float = 100.0
    rate_limit_refill_per_second: float = 10.0

    analytics_flush_interval_seconds: float = 5.0
    analytics_batch_size: int = 500

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
