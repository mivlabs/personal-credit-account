from pydantic import AwareDatetime, ConfigDict, Field

from app.domain.enums import (
    ApplicationField,
    ApplicationStatus,
    DecisionOutcome,
    InfoRequestStatus,
    OfferStatus,
    ProductCode,
    StageCode,
    StageState,
)
from app.schemas.base import ApiModel, Money, Rate
from app.schemas.product import ProductOut


class ApplicationFields(ApiModel):
    model_config = ConfigDict(extra="forbid")
    """Поля анкеты, общие для создания, обновления черновика и дозаполнения."""

    requested_amount: Money | None = Field(default=None, gt=0, description="Запрошенная сумма, ₽")
    term_months: int | None = Field(default=None, gt=0, le=600, description="Срок, мес.")
    purpose: str | None = Field(default=None, max_length=2000, description="Цель кредита")
    revenue_amount: Money | None = Field(default=None, description="Годовая выручка со слов клиента, ₽")
    debt_amount: Money | None = Field(default=None, description="Текущая долговая нагрузка, ₽")


class ApplicationCreate(ApplicationFields):
    """Создание черновика: продукт обязателен, остальные поля можно прислать позже."""

    product_code: ProductCode
    draft_step: int | None = Field(
        default=None, ge=1, le=20, description="Шаг мастера, на котором остановился клиент"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "productCode": "EQUIPMENT",
                    "requestedAmount": 1500000.0,
                    "termMonths": 24,
                    "draftStep": 2,
                }
            ]
        }
    )


class ApplicationUpdate(ApplicationFields):
    """Частичное обновление черновика. Продукт после создания не меняется."""

    draft_step: int | None = Field(default=None, ge=1, le=20, description="Шаг мастера")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "purpose": "Покупка фрезерного станка",
                    "revenueAmount": 12000000.0,
                    "debtAmount": 0.0,
                    "draftStep": 3,
                }
            ]
        }
    )


class MissingInfoAnswer(ApplicationFields):
    """Дозаполнение: допустимы только поля из открытого запроса данных, иначе 422."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"revenueAmount": 8500000.0}]})


class StatusHistoryItem(ApiModel):
    from_status: ApplicationStatus | None = Field(default=None, description="Пусто при создании")
    to_status: ApplicationStatus
    to_status_name: str
    at: AwareDatetime


class InfoRequestOut(ApiModel):
    id: int
    description: str = Field(description="Что нужно дозаполнить, простым языком")
    fields: list[ApplicationField] = Field(description="Какие поля анкеты нужно заполнить")
    status: InfoRequestStatus
    created_at: AwareDatetime
    answered_at: AwareDatetime | None = None


class ClientDecisionOut(ApiModel):
    """Решение для клиента: исход и причина простым языком, без баллов и факторов."""

    outcome: DecisionOutcome
    reason: str
    decided_at: AwareDatetime


class OfferOut(ApiModel):
    id: int
    amount: Money = Field(description="Предложенная сумма, ₽ (при контроффере меньше запрошенной)")
    term_months: int
    rate: Rate
    monthly_payment: Money | None = Field(
        default=None, description="Ориентировочный аннуитетный платёж, ₽; null для овердрафта"
    )
    status: OfferStatus
    accepted_at: AwareDatetime | None = None
    signed_at: AwareDatetime | None = None


class ApplicationSummary(ApiModel):
    """Строка списка «мои заявки»."""

    id: int
    product_code: ProductCode
    product_name: str
    status: ApplicationStatus
    status_name: str
    requested_amount: Money | None = None
    term_months: int | None = None
    draft_step: int | None = None
    action_required: bool = Field(
        description="От клиента нужно действие (дозаполнить, принять оффер, подписать)"
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ApplicationOut(ApiModel):
    available_actions: list[str] = Field(
        default_factory=list, description="Допустимые действия для текущей роли"
    )
    id: int
    company_id: int
    product: ProductOut
    status: ApplicationStatus
    status_name: str
    requested_amount: Money | None = None
    term_months: int | None = None
    purpose: str | None = None
    revenue_amount: Money | None = None
    debt_amount: Money | None = None
    draft_step: int | None = None
    submitted_at: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    history: list[StatusHistoryItem] = Field(description="История переходов статуса, от старых к новым")
    open_info_requests: list[InfoRequestOut] = Field(description="Открытые запросы данных")
    decision: ClientDecisionOut | None = Field(default=None, description="Последнее решение")
    offer: OfferOut | None = Field(default=None, description="Актуальный оффер")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 42,
                    "companyId": 1,
                    "product": {
                        "code": "EQUIPMENT",
                        "name": "Кредит на оборудование",
                        "minAmount": 500000.0,
                        "maxAmount": 30000000.0,
                        "minTermMonths": 12,
                        "maxTermMonths": 60,
                        "rate": 16.9,
                        "requirements": None,
                    },
                    "status": "APPROVED",
                    "statusName": "Одобрено",
                    "requestedAmount": 1500000.0,
                    "termMonths": 24,
                    "purpose": "Покупка фрезерного станка",
                    "revenueAmount": 12000000.0,
                    "debtAmount": 0.0,
                    "draftStep": 3,
                    "submittedAt": "2026-10-22T09:15:00+03:00",
                    "createdAt": "2026-10-22T09:00:00+03:00",
                    "updatedAt": "2026-10-22T09:15:04+03:00",
                    "history": [
                        {
                            "fromStatus": None,
                            "toStatus": "DRAFT",
                            "toStatusName": "Черновик",
                            "at": "2026-10-22T09:00:00+03:00",
                        },
                        {
                            "fromStatus": "DRAFT",
                            "toStatus": "SUBMITTED",
                            "toStatusName": "Подана",
                            "at": "2026-10-22T09:15:00+03:00",
                        },
                    ],
                    "openInfoRequests": [],
                    "decision": {
                        "outcome": "APPROVED",
                        "reason": "Стабильная выручка и чистая кредитная история",
                        "decidedAt": "2026-10-22T09:15:04+03:00",
                    },
                    "offer": {
                        "id": 7,
                        "amount": 1500000.0,
                        "termMonths": 24,
                        "rate": 16.9,
                        "monthlyPayment": 74091.34,
                        "status": "SENT",
                        "acceptedAt": None,
                        "signedAt": None,
                    },
                }
            ]
        }
    )


class TimelineStage(ApiModel):
    code: StageCode
    name: str
    description: str = Field(description="Что происходит на этом этапе, простым языком")
    state: StageState
    action_required: bool = Field(description="От клиента нужно действие на этом этапе")
    entered_at: AwareDatetime | None = Field(default=None, description="Когда этап начался")


class TimelineOut(ApiModel):
    application_id: int
    current_status: ApplicationStatus
    current_status_name: str
    stages: list[TimelineStage]
    history: list[StatusHistoryItem]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "applicationId": 42,
                    "currentStatus": "NEEDS_INFO",
                    "currentStatusName": "Нужны данные",
                    "stages": [
                        {
                            "code": "DRAFT",
                            "name": "Заявка",
                            "description": "Вы заполняете заявку",
                            "state": "done",
                            "actionRequired": False,
                            "enteredAt": "2026-10-22T09:00:00+03:00",
                        },
                        {
                            "code": "SUBMITTED",
                            "name": "Подана",
                            "description": "Заявка принята банком",
                            "state": "done",
                            "actionRequired": False,
                            "enteredAt": "2026-10-22T09:15:00+03:00",
                        },
                        {
                            "code": "REVIEW",
                            "name": "Проверка",
                            "description": "Банк проверяет данные и оценивает заявку",
                            "state": "current",
                            "actionRequired": True,
                            "enteredAt": "2026-10-22T09:15:02+03:00",
                        },
                        {
                            "code": "DECISION",
                            "name": "Решение",
                            "description": "Банк сообщает решение",
                            "state": "upcoming",
                            "actionRequired": False,
                            "enteredAt": None,
                        },
                    ],
                    "history": [],
                }
            ]
        }
    )


class AcceptOfferResponse(ApiModel):
    application: ApplicationOut
    sign_hint: str = Field(
        description="Подсказка для демо с кодом подписи (код берётся из DEMO_SIGN_CODE)",
        examples=["Демо-режим: для подписания введите код 123456"],
    )


class SignRequest(ApiModel):
    code: str = Field(min_length=1, max_length=16, description="Код подтверждения подписи")

    model_config = ConfigDict(json_schema_extra={"examples": [{"code": "123456"}]})
