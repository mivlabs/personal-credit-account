from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Базовая схема API: snake_case внутри, camelCase снаружи."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        # В схеме ответа поля с дефолтами тоже обязательны: фронт получает типы без лишних `?`
        json_schema_serialization_defaults_required=True,
    )


# Деньги: внутри Decimal (numeric(18,2)), в JSON — число с двумя знаками, а не строка.
Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=18, decimal_places=2),
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema(
        {
            "type": "number",
            "minimum": 0,
            "multipleOf": 0.01,
            "description": "Сумма в рублях, не более 2 знаков после запятой",
        }
    ),
]

# Ставка: numeric(7,4), % годовых
Rate = Annotated[
    Decimal,
    Field(ge=0, max_digits=7, decimal_places=4),
    PlainSerializer(float, return_type=float, when_used="json"),
    WithJsonSchema(
        {
            "type": "number",
            "minimum": 0,
            "description": "Процентная ставка, % годовых",
        }
    ),
]
