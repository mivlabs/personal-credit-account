"""Подбор продукта по цели, сумме и сроку: правила из recommendation.yaml, без LLM."""

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ProductCode, PurposeCategory


class Penalties(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    amount_above_max: int = Field(ge=0, le=100)
    amount_below_min: int = Field(ge=0, le=100)
    term_above_max: int = Field(ge=0, le=100)
    term_below_min: int = Field(ge=0, le=100)
    term_atypical: int = Field(ge=0, le=100)


class PurposeRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    label: str = Field(min_length=1)
    fit: dict[ProductCode, int]
    typical_term_months: tuple[int, int]
    reasons: dict[ProductCode, str]

    @model_validator(mode="after")
    def validate_rule(self):
        products = set(ProductCode)
        if set(self.fit) != products or set(self.reasons) != products:
            raise ValueError("fit and reasons must cover every product")
        if any(not 0 <= v <= 100 for v in self.fit.values()):
            raise ValueError("fit must be in 0..100")
        low, high = self.typical_term_months
        if not 0 < low <= high:
            raise ValueError("Invalid typical term range")
        return self


class RecommendationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: str
    recommend_threshold: int = Field(ge=1, le=100)
    penalties: Penalties
    purposes: dict[PurposeCategory, PurposeRule]

    @model_validator(mode="after")
    def validate_config(self):
        if set(self.purposes) != set(PurposeCategory):
            raise ValueError("Rules must cover every purpose category")
        return self


@lru_cache
def load_recommendation_config() -> RecommendationConfig:
    path = Path(__file__).with_name("recommendation.yaml")
    return RecommendationConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ProductLimits:
    code: ProductCode
    min_amount: Decimal
    max_amount: Decimal
    min_term: int
    max_term: int


@dataclass(frozen=True)
class Match:
    code: ProductCode
    score: int
    recommended: bool
    reasons: list[str]


def _money(value: Decimal) -> str:
    if value >= 1_000_000:
        return f"{(value / 1_000_000).normalize():f} млн ₽".replace(".", ",")
    return f"{value:,.0f} ₽".replace(",", " ")


def rank_products(
    products: list[ProductLimits],
    purpose: PurposeCategory,
    amount: Decimal | None,
    term_months: int | None,
    config: RecommendationConfig,
) -> list[Match]:
    rule = config.purposes[purpose]
    pen = config.penalties
    typical_low, typical_high = rule.typical_term_months
    scored: list[tuple[ProductLimits, int, bool, list[str]]] = []
    for p in products:
        score = rule.fit[p.code]
        reasons = [rule.reasons[p.code]]
        in_range = True
        if amount is not None:
            if amount > p.max_amount:
                score -= pen.amount_above_max
                in_range = False
                reasons.append(f"сумма {_money(amount)} выше максимума продукта ({_money(p.max_amount)})")
            elif amount < p.min_amount:
                score -= pen.amount_below_min
                in_range = False
                reasons.append(f"сумма {_money(amount)} ниже минимума продукта ({_money(p.min_amount)})")
            else:
                reasons.append(f"сумма {_money(amount)} входит в диапазон продукта")
        if term_months is not None:
            if term_months > p.max_term:
                score -= pen.term_above_max
                in_range = False
                reasons.append(f"срок {term_months} мес. больше максимума продукта ({p.max_term} мес.)")
            elif term_months < p.min_term:
                score -= pen.term_below_min
                in_range = False
                reasons.append(f"срок {term_months} мес. меньше минимума продукта ({p.min_term} мес.)")
            else:
                reasons.append(f"срок {term_months} мес. подходит для продукта")
                if not typical_low <= term_months <= typical_high:
                    score -= pen.term_atypical
                    reasons.append(f"для этой цели обычно берут {typical_low}–{typical_high} мес.")
        scored.append((p, max(0, min(100, score)), in_range, reasons))

    order = list(ProductCode)
    scored.sort(key=lambda s: (-s[1], order.index(s[0].code)))
    # Рекомендуется лучший из продуктов, у которых сумма и срок в допустимых диапазонах
    best = next((p for p, _, in_range, _ in scored if in_range), None)
    return [
        Match(p.code, score, p is best and score >= config.recommend_threshold, reasons)
        for p, score, in_range, reasons in scored
    ]
