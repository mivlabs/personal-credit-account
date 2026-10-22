"""Стейт-машина заявки: единственное место, где определено, какие смены статуса допустимы.

Таблица TRANSITIONS — источник и для кода, и для docs/state-machine.md
(документ генерируется скриптом app.scripts.export_state_machine, тест сверяет файл с кодом).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, InvalidTransitionError
from app.db.models import LoanApplication, LoanApplicationAud
from app.domain.enums import FINAL_STATUSES, STATUS_NAMES, ApplicationStatus

S = ApplicationStatus
logger = logging.getLogger(__name__)


class Actor(StrEnum):
    CLIENT = "CLIENT"
    SYSTEM = "SYSTEM"
    UNDERWRITER = "UNDERWRITER"


ACTOR_NAMES = {
    Actor.CLIENT: "Клиент",
    Actor.SYSTEM: "Система",
    Actor.UNDERWRITER: "Андеррайтер",
}


@dataclass(frozen=True)
class Transition:
    source: ApplicationStatus
    target: ApplicationStatus
    actor: Actor
    condition: str


TRANSITIONS: tuple[Transition, ...] = (
    Transition(
        S.DRAFT, S.SUBMITTED, Actor.CLIENT, "Заполнены сумма, срок и цель; значения в диапазоне продукта"
    ),
    Transition(S.SUBMITTED, S.CHECKING, Actor.SYSTEM, "Заявка принята конвейером обработки"),
    Transition(S.CHECKING, S.NEEDS_INFO, Actor.SYSTEM, "Не хватает обязательных данных анкеты"),
    Transition(S.CHECKING, S.EXTERNAL_CHECK, Actor.SYSTEM, "Данных достаточно"),
    Transition(S.NEEDS_INFO, S.CHECKING, Actor.CLIENT, "Клиент дозаполнил запрошенные поля"),
    Transition(S.EXTERNAL_CHECK, S.SCORING, Actor.SYSTEM, "Внешние сервисы ответили"),
    Transition(S.EXTERNAL_CHECK, S.MANUAL_REVIEW, Actor.SYSTEM, "Внешний сервис не ответил за таймаут"),
    Transition(S.SCORING, S.APPROVED, Actor.SYSTEM, "Балл не ниже порога одобрения, сумма в пределах лимита"),
    Transition(
        S.SCORING,
        S.COUNTER_OFFER,
        Actor.SYSTEM,
        "Балл не ниже порога одобрения, запрошенная сумма выше лимита",
    ),
    Transition(S.SCORING, S.NEEDS_INFO, Actor.SYSTEM, "Для оценки не хватает данных"),
    Transition(S.SCORING, S.MANUAL_REVIEW, Actor.SYSTEM, "Балл в пограничной зоне"),
    Transition(S.SCORING, S.REJECTED, Actor.SYSTEM, "Сработал стоп-фактор или балл ниже порога отказа"),
    Transition(S.MANUAL_REVIEW, S.APPROVED, Actor.UNDERWRITER, "Решение андеррайтера с комментарием"),
    Transition(
        S.MANUAL_REVIEW,
        S.COUNTER_OFFER,
        Actor.UNDERWRITER,
        "Решение андеррайтера с комментарием и новой суммой",
    ),
    Transition(
        S.MANUAL_REVIEW,
        S.NEEDS_INFO,
        Actor.UNDERWRITER,
        "Решение андеррайтера с комментарием и списком полей",
    ),
    Transition(S.MANUAL_REVIEW, S.REJECTED, Actor.UNDERWRITER, "Решение андеррайтера с комментарием"),
    Transition(S.APPROVED, S.OFFER_ACCEPTED, Actor.CLIENT, "Клиент принял оффер"),
    Transition(S.APPROVED, S.DECLINED_BY_CLIENT, Actor.CLIENT, "Клиент отказался от оффера"),
    Transition(S.COUNTER_OFFER, S.OFFER_ACCEPTED, Actor.CLIENT, "Клиент принял встречное предложение"),
    Transition(
        S.COUNTER_OFFER, S.DECLINED_BY_CLIENT, Actor.CLIENT, "Клиент отказался от встречного предложения"
    ),
    Transition(S.OFFER_ACCEPTED, S.SIGNING, Actor.SYSTEM, "Подготовлено подписание"),
    Transition(S.SIGNING, S.ISSUED, Actor.CLIENT, "Код подписи подтверждён"),
)

_ALLOWED: dict[tuple[ApplicationStatus, ApplicationStatus], Transition] = {
    (t.source, t.target): t for t in TRANSITIONS
}


def find_transition(source: ApplicationStatus, target: ApplicationStatus) -> Transition | None:
    return _ALLOWED.get((source, target))


def is_allowed(source: ApplicationStatus, target: ApplicationStatus, actor: Actor | None = None) -> bool:
    t = find_transition(source, target)
    return t is not None and (actor is None or t.actor == actor)


def targets_from(source: ApplicationStatus) -> list[ApplicationStatus]:
    return [t.target for t in TRANSITIONS if t.source == source]


def record_creation(
    session: Session, application: LoanApplication, actor_user_id: int | None
) -> LoanApplicationAud:
    """Аудит создания черновика: from_status_code = NULL."""
    row = LoanApplicationAud(
        application_id=application.application_id,
        user_id=actor_user_id,
        from_status_code=None,
        to_status_code=application.status_code,
        event_desc="Черновик создан",
        create_dttm=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def transition(
    session: Session,
    application: LoanApplication,
    to_status: ApplicationStatus,
    actor_user_id: int | None,
    comment: str | None = None,
    *,
    actor: Actor | None = None,
) -> LoanApplicationAud:
    """Единственное место смены статуса заявки.

    Проверяет переход по таблице TRANSITIONS, меняет статус и пишет loan_application_aud в той же
    транзакции (коммитит вызывающий). Строка заявки блокируется на время транзакции, поэтому параллельный
    переход не пройдёт молча. Недопустимый переход — 409 INVALID_TRANSITION.
    """
    # Блокируем строку и читаем актуальный статус из БД, а не из объекта в памяти
    db_status = session.execute(
        select(LoanApplication.status_code)
        .where(LoanApplication.application_id == application.application_id)
        .with_for_update()
    ).scalar_one()
    source = ApplicationStatus(db_status)
    if source.value != application.status_code:
        raise InvalidTransitionError("Статус заявки уже изменился, обновите страницу и повторите действие")

    rule = find_transition(source, to_status)
    if rule is None:
        raise InvalidTransitionError(
            f"Из статуса «{STATUS_NAMES[source]}» нельзя перейти в «{STATUS_NAMES[to_status]}»"
        )
    if actor is not None and rule.actor != actor:
        raise ForbiddenError(
            f"Переход «{STATUS_NAMES[source]}» → «{STATUS_NAMES[to_status]}» выполняет "
            f"{ACTOR_NAMES[rule.actor].lower()}"
        )

    application.status_code = to_status.value
    row = LoanApplicationAud(
        application_id=application.application_id,
        user_id=actor_user_id,
        from_status_code=source.value,
        to_status_code=to_status.value,
        event_desc=comment,
        create_dttm=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    logger.info(
        "Переход статуса %s → %s",
        source.value,
        to_status.value,
        extra={"from_status": source.value, "to_status": to_status.value, "actor_user_id": actor_user_id},
    )
    return row


def render_state_machine_md() -> str:
    """Markdown-документ с таблицей переходов и диаграммой mermaid."""
    lines = [
        "# Стейт-машина заявки",
        "",
        "Документ сгенерирован из таблицы `TRANSITIONS` в `backend/app/domain/state_machine.py`:",
        "`uv run python -m app.scripts.export_state_machine`. Руками не править: тест сверяет файл с кодом.",
        "Любой переход, которого нет в таблице, API отклоняет ответом 409 `INVALID_TRANSITION`.",
        "Каждый переход пишет строку в `loan_application_aud` в той же транзакции.",
        "",
        "## Статусы",
        "",
        "| Код | Название для клиента | Конечный |",
        "|---|---|---|",
    ]
    for status in ApplicationStatus:
        final = "да" if status in FINAL_STATUSES else "нет"
        lines.append(f"| `{status.value}` | {STATUS_NAMES[status]} | {final} |")

    lines += [
        "",
        "## Переходы",
        "",
        "| Из | В | Кто инициирует | Условие |",
        "|---|---|---|---|",
    ]
    for t in TRANSITIONS:
        lines.append(f"| `{t.source.value}` | `{t.target.value}` | {ACTOR_NAMES[t.actor]} | {t.condition} |")

    lines += ["", "## Диаграмма", "", "```mermaid", "stateDiagram-v2", f"    [*] --> {S.DRAFT.value}"]
    for t in TRANSITIONS:
        lines.append(f"    {t.source.value} --> {t.target.value}: {ACTOR_NAMES[t.actor]}")
    for status in ApplicationStatus:
        if status in FINAL_STATUSES:
            lines.append(f"    {status.value} --> [*]")
    lines += ["```", ""]
    return "\n".join(lines)
