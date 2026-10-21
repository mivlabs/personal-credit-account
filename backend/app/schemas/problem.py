from pydantic import ConfigDict, Field

from app.domain.enums import ErrorCode
from app.schemas.base import ApiModel


class FieldError(ApiModel):
    field: str = Field(description="Имя поля (camelCase) или заголовка", examples=["requestedAmount"])
    message: str = Field(description="Что не так, простым языком")
    code: str | None = Field(default=None, description="Машинный код ошибки поля")


class ProblemDetail(ApiModel):
    """Ошибка в формате RFC 7807 (`application/problem+json`)."""

    type: str = Field(description="URN типа проблемы", examples=["urn:problem:validation-error"])
    title: str = Field(description="Краткий заголовок", examples=["Ошибка валидации"])
    status: int = Field(description="HTTP-статус", examples=[422])
    detail: str | None = Field(default=None, description="Подробности для человека")
    code: ErrorCode = Field(description="Машинный код ошибки")
    instance: str | None = Field(default=None, description="Путь запроса")
    errors: list[FieldError] = Field(default_factory=list, description="Ошибки по полям")
    request_id: str | None = Field(default=None, description="Идентификатор запроса для логов")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "urn:problem:validation-error",
                    "title": "Ошибка валидации",
                    "status": 422,
                    "detail": "Запрос не прошёл проверку: исправьте отмеченные поля",
                    "code": "VALIDATION_ERROR",
                    "instance": "/api/v1/applications/42/submit",
                    "errors": [
                        {
                            "field": "requestedAmount",
                            "message": "Сумма должна быть от 300 000 до 10 000 000 ₽",
                            "code": "OUT_OF_RANGE",
                        }
                    ],
                    "requestId": "a1b2c3d4",
                }
            ]
        }
    )
