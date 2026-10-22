"""Движок решения: стоп-факторы → скоринг → кредитная политика.

СЕГОДНЯ заглушка: любая заявка уходит на ручную проверку. В четверг здесь скоринг по карте из конфига,
сигнатура `decide(application, external_data, config) -> DecisionResult` не меняется.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.db.models import LoanApplication
from app.domain.decision.config import DecisionConfig
from app.domain.enums import ApplicationField, DecisionOutcome
from app.integrations.base import ExternalData


@dataclass(frozen=True)
class FactorResult:
    code: str
    value: str | None
    points: int


@dataclass(frozen=True)
class InfoRequestSpec:
    description: str
    fields: list[ApplicationField]


@dataclass(frozen=True)
class DecisionResult:
    outcome: DecisionOutcome
    score: int | None
    factors: list[FactorResult] = field(default_factory=list)
    reason: str = ""  # для клиента, простым языком
    offer_amt: Decimal | None = None  # для COUNTER_OFFER
    info_request: InfoRequestSpec | None = None  # для NEEDS_INFO
    note: str | None = None  # внутренний комментарий для аудита (причина попадания в очередь и т.п.)


def decide(
    application: LoanApplication, external_data: ExternalData, config: DecisionConfig
) -> DecisionResult:
    return DecisionResult(
        outcome=DecisionOutcome.MANUAL_REVIEW,
        score=None,
        reason="Заявка передана специалисту",
        note="Автоматическая оценка пока не подключена: заявка передана специалисту",
    )
