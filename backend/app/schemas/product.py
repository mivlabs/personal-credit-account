from datetime import date

from pydantic import ConfigDict, Field

from app.domain.enums import ProductCode
from app.schemas.base import ApiModel, Money, Rate


class RateBreakdownOut(ApiModel):
    """Разложение ставки: ключевая ставка ЦБ + спред продукта + риск-надбавка."""

    key_rate: Rate = Field(description="Ключевая ставка Банка России, % годовых")
    key_rate_date: date = Field(description="Дата, на которую принято значение ключевой ставки")
    key_rate_source: str = Field(description="Источник значения ключевой ставки")
    product_spread: Rate = Field(description="Спред продукта, п.п.")
    risk_surcharge: Rate = Field(description="Риск-надбавка, п.п.")
    total: Rate = Field(description="Итоговая ставка, % годовых")


class ProductOut(ApiModel):
    code: ProductCode
    name: str
    min_amount: Money = Field(description="Минимальная сумма, ₽")
    max_amount: Money = Field(description="Максимальная сумма, ₽")
    min_term_months: int = Field(description="Минимальный срок, мес.")
    max_term_months: int = Field(description="Максимальный срок, мес.")
    rate: Rate = Field(description="Ставка «от», % годовых (то же, что rateFrom)")
    rate_from: Rate = Field(description="Минимальная ставка без риск-надбавки, % годовых")
    rate_breakdown: RateBreakdownOut = Field(description="Разложение минимальной ставки")
    requirements: str | None = Field(default=None, description="Требования к заёмщику")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "WORKING_CAPITAL",
                    "name": "Оборотный кредит",
                    "minAmount": 300000.0,
                    "maxAmount": 10000000.0,
                    "minTermMonths": 3,
                    "maxTermMonths": 36,
                    "rate": 16.5,
                    "rateFrom": 16.5,
                    "rateBreakdown": {
                        "keyRate": 14.0,
                        "keyRateDate": "2026-09-11",
                        "keyRateSource": "Банк России, решение Совета директоров от 11.09.2026",
                        "productSpread": 2.5,
                        "riskSurcharge": 0.0,
                        "total": 16.5,
                    },
                    "requirements": "Бизнесу не менее 6 месяцев, нет просрочки свыше 90 дней",
                }
            ]
        }
    )
