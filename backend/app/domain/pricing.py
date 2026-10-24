"""Единая ставка: ключевая ставка ЦБ + спред продукта + риск-надбавка."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.decision.config import DecisionConfig


@dataclass(frozen=True)
class RateBreakdown:
    key_rate: Decimal
    key_rate_date: date
    key_rate_source: str
    product_spread: Decimal
    risk_surcharge: Decimal
    total: Decimal

    def to_json(self) -> dict:
        return {
            "keyRate": str(self.key_rate),
            "keyRateDate": self.key_rate_date.isoformat(),
            "keyRateSource": self.key_rate_source,
            "productSpread": str(self.product_spread),
            "riskSurcharge": str(self.risk_surcharge),
            "total": str(self.total),
        }


def compute_rate(
    product_code: str, score: int | None, config: DecisionConfig, *, with_surcharge: bool = True
) -> RateBreakdown:
    """Надбавка применяется, если балла нет (ручное решение) или он ниже порога низкого риска."""
    surcharge = (
        config.risk_surcharge_pct
        if with_surcharge and (score is None or score < config.low_risk_threshold)
        else Decimal(0)
    )
    spread = config.product_spreads[product_code]
    return RateBreakdown(
        key_rate=config.key_rate_pct,
        key_rate_date=config.key_rate_date,
        key_rate_source=config.key_rate_source,
        product_spread=spread,
        risk_surcharge=surcharge,
        total=config.key_rate_pct + spread + surcharge,
    )


def rate_from(product_code: str, config: DecisionConfig) -> RateBreakdown:
    """«От X %»: минимальная ставка без риск-надбавки."""
    return compute_rate(product_code, None, config, with_surcharge=False)
