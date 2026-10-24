"""Validated, versioned demo credit policy; no network access at runtime."""

from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings


class DecisionConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: str
    snapshot_date: date
    approve_threshold: int = Field(ge=1, le=100)
    reject_threshold: int = Field(ge=0, le=99)
    min_company_age_months: int = Field(ge=0)
    max_overdue_days: int = Field(ge=0)
    revenue_limit_share: Decimal = Field(gt=0, le=1)
    debt_limit_share: Decimal = Field(ge=0)
    age_bands: list[tuple[int, int]]
    revenue_bands: list[tuple[int, int]]
    debt_bands: list[tuple[Decimal, int]]
    overdue_bands: list[tuple[int, int]]
    industry_points: dict[str, int]
    key_rate_pct: Decimal = Field(ge=0, le=100)
    key_rate_date: date
    key_rate_source: str = Field(min_length=1)
    product_spreads: dict[str, Decimal]
    risk_surcharge_pct: Decimal = Field(ge=0, le=100)
    low_risk_threshold: int = Field(ge=0, le=100)
    # Расхождение анкеты с источником выше порога (в процентах) → ручная проверка
    data_mismatch_pct: Decimal = Field(ge=0)
    # Выручка только со слов клиента: лимит умножается на коэффициент
    client_declared_limit_factor: Decimal = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_policy(self):
        if self.reject_threshold >= self.approve_threshold:
            raise ValueError("reject_threshold must be below approve_threshold")
        if set(self.product_spreads) != {"WORKING_CAPITAL", "EQUIPMENT", "OVERDRAFT"} or any(
            v < 0 or v > 100 for v in self.product_spreads.values()
        ):
            raise ValueError("Product spreads must cover the three products and be in 0..100")
        maxima = []
        for bands in (self.age_bands, self.revenue_bands, self.debt_bands, self.overdue_bands):
            if not bands or any(a[0] >= b[0] for a, b in zip(bands, bands[1:], strict=False)):
                raise ValueError("Scoring bands must be nonempty and strictly increasing")
            if any(not 0 <= points <= 100 for _, points in bands):
                raise ValueError("Invalid factor points")
            maxima.append(max(points for _, points in bands))
        if (
            not self.industry_points
            or "other" not in self.industry_points
            or any(not 0 <= p <= 100 for p in self.industry_points.values())
        ):
            raise ValueError("Invalid industry points")
        if sum(maxima) + max(self.industry_points.values()) != 100:
            raise ValueError("Maximum score must equal 100")
        return self


@lru_cache
def load_decision_config() -> DecisionConfig:
    path = Path(__file__).with_name("policy.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings = get_settings()
    # Ключевую ставку можно переопределить окружением: значение нужно сверить с cbr.ru на дату проверки
    if settings.key_rate_pct is not None:
        raw["key_rate_pct"] = str(settings.key_rate_pct)
    if settings.key_rate_date is not None:
        raw["key_rate_date"] = settings.key_rate_date.isoformat()
    return DecisionConfig.model_validate(raw)
