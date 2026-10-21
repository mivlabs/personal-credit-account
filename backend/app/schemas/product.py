from pydantic import ConfigDict, Field

from app.domain.enums import ProductCode
from app.schemas.base import ApiModel, Money, Rate


class ProductOut(ApiModel):
    code: ProductCode
    name: str
    min_amount: Money = Field(description="Минимальная сумма, ₽")
    max_amount: Money = Field(description="Максимальная сумма, ₽")
    min_term_months: int = Field(description="Минимальный срок, мес.")
    max_term_months: int = Field(description="Максимальный срок, мес.")
    rate: Rate = Field(description="Базовая ставка, % годовых")
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
                    "rate": 18.5,
                    "requirements": "Бизнесу не менее 6 месяцев, нет просрочки свыше 90 дней",
                }
            ]
        }
    )
