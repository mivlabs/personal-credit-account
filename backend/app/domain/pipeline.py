"""Конвейер обработки заявки после подачи (и после дозаполнения данных).

SUBMITTED → CHECKING → EXTERNAL_CHECK → SCORING → итог решения.
Все переходы, проверки и решение атомарны с командой подачи.
"""

import json
import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core import clock
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
                due_dttm=clock.now() + timedelta(days=get_settings().info_request_ttl_days),
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
    client = get_external_checks_client(session)
    results = client.fetch_all(app.application_id, app.company)
    session.info["decision_external_snapshot"] = {
        source.value: {"status": result.status.value, "data": result.data}
        for source, result in results.results.items()
    }
    transition(
        session,
        app,
        S.SCORING,
        None,
        "Ответы внешних сервисов сохранены",
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


def process_pipeline(session: Session, app: LoanApplication) -> None:
    """Runs under the application row lock, atomically with submission and its audit."""
    token = application_id_var.set(app.application_id)
    try:
        for _ in range(MAX_STEPS):
            handler = _HANDLERS.get(ApplicationStatus(app.status_code))
            if handler is None:
                return
            handler(session, app)
        raise RuntimeError("Pipeline exceeded its bounded number of steps")
    finally:
        application_id_var.reset(token)


def run_pipeline(application_id: int) -> None:
    with get_sessionmaker()() as session, session.begin():
        app = session.get(LoanApplication, application_id, with_for_update=True)
        if app is not None:
            process_pipeline(session, app)
