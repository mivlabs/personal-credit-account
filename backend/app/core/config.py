from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения (значения по умолчанию подходят для локальной разработки)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://credit:credit@localhost:5432/credit"
    jwt_secret: str = Field(default="change-me-in-production-please-32+chars", min_length=16)
    jwt_ttl_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    demo_sign_code: str = "123456"
    mocks_base_url: str = "http://localhost:8081"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
