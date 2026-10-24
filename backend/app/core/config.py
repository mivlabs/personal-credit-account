from datetime import date
from decimal import Decimal
from functools import lru_cache

from pydantic import Field, field_validator
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
    # Пауза между шагами конвейера: на демо клиент успевает увидеть этапы. В тестах 0.
    pipeline_step_delay_seconds: float = 0.0
    # Переопределение ключевой ставки ЦБ из policy.yaml (проверить значение на cbr.ru)
    key_rate_pct: Decimal | None = Field(default=None, ge=0, le=100)
    key_rate_date: date | None = None
    # Сроки жизни: оффер и запрос данных (проверяются лениво при командах и скриптом expire_stale)
    offer_ttl_days: int = Field(default=30, gt=0)
    info_request_ttl_days: int = Field(default=14, gt=0)
    # Дата расчёта возраста компании; по умолчанию сегодня по Europe/Moscow
    as_of_date: date | None = None

    @field_validator(
        "key_rate_pct",
        "key_rate_date",
        "as_of_date",
        "offer_ttl_days",
        "info_request_ttl_days",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, value):
        # docker compose передаёт незаданные переменные пустой строкой
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
