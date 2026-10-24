"""Сроки жизни оффера и запроса данных: ленивая проверка в командах и массовое закрытие скриптом.

Планировщика нет. Просроченная заявка переводится в EXPIRED (актор SYSTEM) либо при первой команде клиента
(тогда он получает 409 EXPIRED), либо скриптом `python -m app.scripts.expire_stale`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import ExpiredError
from app.db.models import CreditDecision, InfoRequest, LoanApplication, LoanOffer
from app.domain.enums import ApplicationStatus, InfoRequestStatus
from app.domain.state_machine import Actor, transition
from app.services.mappers import latest_offer, open_info_requests

S = ApplicationStatus

_OFFER_STATUSES = (S.APPROVED.value, S.COUNTER_OFFER.value)


def stale_reason(session: Session, app: LoanApplication) -> str | None:
    """Почему заявка просрочена (текст для аудита) или None, если срок не истёк."""
    now = clock.now()
    if app.status_code in _OFFER_STATUSES:
        offer = latest_offer(session, app.application_id)
        if offer is not None and offer.valid_until_dttm is not None and now > offer.valid_until_dttm:
            return "Срок действия предложения истёк"
    elif app.status_code == S.NEEDS_INFO.value:
        if any(
            r.due_dttm is not None and now > r.due_dttm
            for r in open_info_requests(session, app.application_id)
        ):
            return "Срок ответа на запрос данных истёк"
    return None


def expire_if_stale(session: Session, app: LoanApplication) -> bool:
    """Переводит просроченную заявку в EXPIRED (без коммита; строка заявки должна быть заблокирована)."""
    reason = stale_reason(session, app)
    if reason is None:
        return False
    transition(session, app, S.EXPIRED, None, reason, actor=Actor.SYSTEM)
    return True


def ensure_not_expired(session: Session, app: LoanApplication) -> None:
    """Начало клиентской команды: если срок истёк, переход в EXPIRED коммитится и возвращается 409 EXPIRED."""
    if expire_if_stale(session, app):
        session.commit()  # коммитим до исключения, чтобы откат ошибки не отменил переход
        raise ExpiredError("Срок истёк: заявка закрыта. Создайте новую заявку")


def find_stale_application_ids(session: Session) -> list[int]:
    now = clock.now()
    offers = (
        select(CreditDecision.application_id)
        .join(LoanOffer, LoanOffer.decision_id == CreditDecision.decision_id)
        .where(LoanOffer.valid_until_dttm < now)
    )
    requests = select(InfoRequest.application_id).where(
        InfoRequest.request_status_code == InfoRequestStatus.OPEN.value, InfoRequest.due_dttm < now
    )
    candidates = select(LoanApplication.application_id).where(
        (LoanApplication.status_code.in_(_OFFER_STATUSES) & LoanApplication.application_id.in_(offers))
        | (LoanApplication.status_code == S.NEEDS_INFO.value) & LoanApplication.application_id.in_(requests)
    )
    return list(session.scalars(candidates.order_by(LoanApplication.application_id)))


def expire_all_stale(session_factory) -> int:
    """Закрывает все просроченные заявки; каждая в своей транзакции. Возвращает число закрытых."""
    with session_factory() as session:
        ids = find_stale_application_ids(session)
    closed = 0
    for application_id in ids:
        with session_factory() as session, session.begin():
            app = session.get(LoanApplication, application_id, with_for_update=True)
            if app is not None and expire_if_stale(session, app):
                closed += 1
    return closed
