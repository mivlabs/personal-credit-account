"""Стейт-машина заявки: единственное место, где определено, какие смены статуса допустимы.

Таблица TRANSITIONS — источник и для кода, и для docs/state-machine.md
(документ генерируется скриптом app.scripts.export_state_machine, тест сверяет файл с кодом).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import FINAL_STATUSES, STATUS_NAMES, ApplicationStatus

S = ApplicationStatus


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
