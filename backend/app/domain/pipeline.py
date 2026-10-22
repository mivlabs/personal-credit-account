"""Конвейер обработки заявки после подачи (и после дозаполнения данных).

SUBMITTED → CHECKING → EXTERNAL_CHECK → SCORING → итог решения. Каждый шаг делает ровно один переход
в отдельной транзакции, поэтому клиент видит промежуточные статусы. Запускается через BackgroundTasks
FastAPI (без очередей). Сегодня внешние проверки отключены, а движок решения отправляет всё на ручную проверку.
"""

import json
import logging
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import application_id_var
from app.db.models import InfoRequest, LoanApplication
from app.db.session import get_sessionmaker
from app.domain.decision.config import load_decision_config
from app.domain.decision.engine import decide
from app.domain.decision.service import record_auto_decision
from app.domain.enums import ApplicationStatus, InfoRequestStatus
from app.domain.fields import FIELD_ATTR, REQUIRED_FOR_SUBMIT
from app.domain.state_machine import Actor, transition
from app.integrations.base import get_external_checks_client, load_external_data

logger = logging.getLogger(__name__)
S = ApplicationStatus

MAX_STEPS = 10


def _start(session: Session, app: LoanApplication) -> None:
    transition(session, app, S.CHECKING, None, "Заявка принята в обработку", actor=Actor.SYSTEM)


def _check_completeness(session: Session, app: LoanApplication) -> None:
    missing = [f for f in REQUIRED_FOR_SUBMIT if getattr(app, FIELD_ATTR[f]) in (None, "")]
    if missing:
        session.add(
            InfoRequest(
                application_id=app.application_id,
                user_id=None,
                request_desc="Заполните недостающие данные заявки",
                field_list_cval=json.dumps([f.value for f in missing]),
                request_status_code=InfoRequestStatus.OPEN.value,
            )
        )
        transition(
            session,
            app,
            S.NEEDS_INFO,
            None,
            "Не хватает данных: " + ", ".join(f.value for f in missing),
            actor=Actor.SYSTEM,
        )
        return
    transition(session, app, S.EXTERNAL_CHECK, None, "Данных достаточно", actor=Actor.SYSTEM)


def _external_checks(session: Session, app: LoanApplication) -> None:
    client = get_external_checks_client()
    client.fetch_all(app.application_id, app.company)
    transition(
        session,
        app,
        S.SCORING,
        None,
        "Внешние проверки пока отключены",
        actor=Actor.SYSTEM,
    )


def _score(session: Session, app: LoanApplication) -> None:
    external_data = load_external_data(session, app.application_id)
    result = decide(app, external_data, load_decision_config())
    record_auto_decision(session, app, result)


_HANDLERS: dict[ApplicationStatus, Callable[[Session, LoanApplication], None]] = {
    S.SUBMITTED: _start,
    S.CHECKING: _check_completeness,
    S.EXTERNAL_CHECK: _external_checks,
    S.SCORING: _score,
}


def run_pipeline(application_id: int) -> None:
    """Точка входа для BackgroundTasks: ведёт заявку, пока её ведёт система."""
    token = application_id_var.set(application_id)
    delay = get_settings().pipeline_step_delay_seconds
    try:
        for _ in range(MAX_STEPS):
            with get_sessionmaker()() as session, session.begin():
                app = session.get(LoanApplication, application_id)
                if app is None:
                    logger.error("Заявка для конвейера не найдена")
                    return
                handler = _HANDLERS.get(ApplicationStatus(app.status_code))
                if handler is None:
                    return
                handler(session, app)
            if delay:
                time.sleep(delay)
    except Exception:
        # Заявка остаётся в последнем записанном статусе; восстановление зависших заявок — отдельная задача
        logger.exception("Сбой конвейера обработки заявки")
    finally:
        application_id_var.reset(token)
