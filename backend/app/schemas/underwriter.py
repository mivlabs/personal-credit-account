from typing import Annotated, Any

from pydantic import AwareDatetime, ConfigDict, Field, StringConstraints

from app.domain.enums import (
    ApplicationField,
    ApplicationStatus,
    CheckSource,
    CheckStatus,
    DecisionOutcome,
    DecisionType,
    ManualOutcome,
    ProductCode,
)
from app.schemas.application import ApplicationOut
from app.schemas.base import ApiModel, Money
from app.schemas.company import CompanyOut


class QueueItem(ApiModel):
    status: ApplicationStatus = ApplicationStatus.MANUAL_REVIEW
    status_name: str = "На рассмотрении у специалиста"
    application_id: int
    company_name: str
    product_code: ProductCode
    product_name: str
    requested_amount: Money | None
    score: int | None = Field(default=None, description="Балл скоринга 0–100; пусто, если балла нет")
    submitted_at: AwareDatetime
    waiting_seconds: int = Field(description="Сколько заявка ждёт в очереди, секунд")
    queue_reason: str = Field(description="Почему заявка попала в очередь")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "applicationId": 42,
                    "companyName": "ООО «Ромашка»",
                    "productCode": "WORKING_CAPITAL",
                    "productName": "Оборотный кредит",
                    "requestedAmount": 3000000.0,
                    "score": 55,
                    "submittedAt": "2026-10-22T09:15:00+03:00",
                    "waitingSeconds": 1260,
                    "queueReason": "Балл в пограничной зоне: 55",
                }
            ]
        }
    )


class QueueOut(ApiModel):
    items: list[QueueItem] = Field(description="Старые заявки сверху")
    total: int
    limit: int
    offset: int


class ExternalCheckOut(ApiModel):
    id: int
    source: CheckSource
    status: CheckStatus
    response: dict[str, Any] | None = Field(default=None, description="Ответ сервиса как есть")
    requested_at: AwareDatetime
    responded_at: AwareDatetime | None = None


class DecisionFactorOut(ApiModel):
    explanation: str = ""
    code: str = Field(examples=["REVENUE"])
    value: str | None = Field(default=None, description="Значение фактора на момент решения")
    points: int = Field(description="Баллы по скоринг-карте")


class DecisionDetailOut(ApiModel):
    id: int
    type: DecisionType
    outcome: DecisionOutcome
    score: int | None = None
    reason: str = Field(description="Причина для клиента")
    comment: str | None = Field(default=None, description="Комментарий андеррайтера")
    decided_by: str | None = Field(
        default=None, description="ФИО андеррайтера; пусто для автоматического решения"
    )
    created_at: AwareDatetime
    snapshot: dict[str, Any] | None = Field(
        default=None, description="Структурированный снимок решения: входы, факторы, лимит, ставка"
    )
    factors: list[DecisionFactorOut] = Field(default_factory=list)


class UnderwriterApplicationOut(ApiModel):
    """Всё на одном экране: анкета, внешние данные, балл и факторы, история решений."""

    application: ApplicationOut
    company: CompanyOut
    external_checks: list[ExternalCheckOut]
    decisions: list[DecisionDetailOut] = Field(description="От новых к старым")
    queue_reason: str | None = Field(default=None, description="Почему заявка попала в очередь")
    auto_limit: Money | None = Field(
        default=None,
        description="Расчётный лимит из последнего автоматического снимка; null, если лимита нет",
    )


class RecheckRequest(ApiModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] = Field(
        description="Зачем нужна повторная проверка (обязателен, пишется в аудит)"
    )

    model_config = ConfigDict(json_schema_extra={"examples": [{"comment": "БКИ был недоступен, повторяем"}]})


class InfoRequestInput(ApiModel):
    description: str = Field(
        min_length=1, max_length=2000, description="Что нужно дозаполнить, простым языком"
    )
    fields: list[ApplicationField] = Field(
        min_length=1, description="Какие поля анкеты клиент должен заполнить"
    )


class DecisionRequest(ApiModel):
    outcome: ManualOutcome
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] = Field(
        description="Комментарий андеррайтера (обязателен, пустой не принимается)"
    )
    client_reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Причина решения простым языком для клиента; если не задана, берётся стандартная формулировка",
    )
    offer_amount: Money | None = Field(default=None, gt=0, description="Обязательна для COUNTER_OFFER")
    offer_term_months: int | None = Field(
        default=None, gt=0, description="Срок оффера; по умолчанию как в заявке"
    )
    info_request: InfoRequestInput | None = Field(default=None, description="Обязателен для NEEDS_INFO")
    override_limit: bool = Field(
        default=False,
        description="Подтверждение решения выше расчётного лимита (APPROVED на запрошенную сумму или COUNTER_OFFER выше лимита)",
    )
    # Кросс-полевые правила (offerAmount для COUNTER_OFFER, infoRequest для NEEDS_INFO) проверяет
    # сервис решения, чтобы вернуть 422 с ошибкой по конкретному полю.


DECISION_REQUEST_EXAMPLES = {
    "approve": {
        "summary": "Одобрить",
        "value": {
            "outcome": "APPROVED",
            "comment": "Молодая компания, но выручка подтверждена выпиской",
            "clientReason": "Выручка компании подтверждает возможность платить по кредиту",
        },
    },
    "counterOffer": {
        "summary": "Встречное предложение",
        "value": {
            "outcome": "COUNTER_OFFER",
            "comment": "Сумма выше допустимой долговой нагрузки",
            "clientReason": "Мы можем предложить меньшую сумму: так платёж будет комфортнее",
            "offerAmount": 2000000.0,
        },
    },
    "needsInfo": {
        "summary": "Запросить данные",
        "value": {
            "outcome": "NEEDS_INFO",
            "comment": "Нет подтверждения выручки",
            "infoRequest": {
                "description": "Укажите годовую выручку за последний год",
                "fields": ["revenueAmount"],
            },
        },
    },
    "reject": {
        "summary": "Отказать",
        "value": {
            "outcome": "REJECTED",
            "comment": "Высокая долговая нагрузка",
            "clientReason": "Сейчас долговая нагрузка компании выше допустимой",
        },
    },
}


class AuditEntryOut(ApiModel):
    id: int
    user_id: int | None = Field(default=None, description="Пусто для системных переходов")
    user_name: str | None = None
    from_status: str | None = Field(default=None, description="Пусто при создании")
    to_status: str
    comment: str | None = None
    created_at: AwareDatetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 101,
                    "userId": None,
                    "userName": None,
                    "fromStatus": "SCORING",
                    "toStatus": "MANUAL_REVIEW",
                    "comment": "Балл в пограничной зоне: 55",
                    "createdAt": "2026-10-22T09:15:04+03:00",
                }
            ]
        }
    )
