"""Запись решения по заявке: общая для автоматического и ручного решения.

В одной транзакции: credit_decision, факторы, оффер (для одобрения и контроффера), запрос данных
(для NEEDS_INFO) и переход статуса через стейт-машину.
"""

import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    CreditDecision,
    DecisionFactor,
    ExternalCheck,
    InfoRequest,
    LoanApplication,
    LoanOffer,
)
from app.domain.clock import as_of_date
from app.domain.decision.config import load_decision_config
from app.domain.decision.engine import DecisionResult, FactorResult, InfoRequestSpec
from app.domain.decision.snapshot import build_auto_snapshot
from app.domain.enums import (
    ApplicationStatus,
    DecisionOutcome,
    DecisionType,
    InfoRequestStatus,
    OfferStatus,
)
from app.domain.offers import monthly_payment
from app.domain.pricing import compute_rate
from app.domain.state_machine import Actor, transition


def record_decision(
    session: Session,
    application: LoanApplication,
    *,
    decision_type: DecisionType,
    user_id: int | None,
    outcome: DecisionOutcome,
    score: int | None,
    factors: list[FactorResult],
    reason: str,
    comment: str | None,
    offer_amount: Decimal | None = None,
    offer_term_months: int | None = None,
    info_request: InfoRequestSpec | None = None,
    audit_comment: str | None = None,
    offer_rate: Decimal | None = None,
    snapshot: dict | None = None,
) -> CreditDecision:
    decision = CreditDecision(
        application_id=application.application_id,
        user_id=user_id,
        decision_type_code=decision_type.value,
        outcome_code=outcome.value,
        score_qnt=score,
        reason_desc=reason,
        comment_desc=comment,
        decision_snapshot=snapshot,
    )
    session.add(decision)
    session.flush()

    for f in factors:
        session.add(
            DecisionFactor(
                decision_id=decision.decision_id,
                factor_code=f.code,
                factor_cval=json.dumps({"value": f.value, "explanation": f.explanation}, ensure_ascii=False),
                point_qnt=f.points,
            )
        )

    if outcome in (DecisionOutcome.APPROVED, DecisionOutcome.COUNTER_OFFER):
        amount = offer_amount if offer_amount is not None else application.requested_amt
        term = offer_term_months if offer_term_months is not None else application.term_qnt
        rate = (
            offer_rate
            if offer_rate is not None
            else compute_rate(application.product.product_code, None, load_decision_config()).total
        )
        session.add(
            LoanOffer(
                decision_id=decision.decision_id,
                offer_amt=amount,
                term_qnt=term,
                rate_nval=rate,
                monthly_payment_amt=Decimal(0)
                if application.product.product_code == "OVERDRAFT"
                else monthly_payment(amount, rate, term),
                offer_status_code=OfferStatus.SENT.value,
            )
        )

    if outcome == DecisionOutcome.NEEDS_INFO and info_request is not None:
        session.add(
            InfoRequest(
                application_id=application.application_id,
                user_id=user_id,
                request_desc=info_request.description,
                field_list_cval=json.dumps([f.value for f in info_request.fields]),
                request_status_code=InfoRequestStatus.OPEN.value,
            )
        )

    actor = Actor.UNDERWRITER if decision_type == DecisionType.MANUAL else Actor.SYSTEM
    transition(
        session,
        application,
        ApplicationStatus(outcome.value),
        user_id,
        audit_comment or comment or reason,
        actor=actor,
    )
    session.flush()
    return decision


def _external_checks_block(session: Session, application: LoanApplication) -> list[dict]:
    """Последняя попытка по каждому источнику в рамках текущей проверки."""
    latest: dict[str, ExternalCheck] = {}
    for row in session.scalars(
        select(ExternalCheck)
        .where(ExternalCheck.application_id == application.application_id)
        .order_by(ExternalCheck.check_id)
    ):
        latest[row.source_code] = row
    return [
        {
            "source": row.source_code,
            "status": row.check_status_code,
            "requestedAt": row.request_dttm.isoformat() if row.request_dttm else None,
            "respondedAt": row.response_dttm.isoformat() if row.response_dttm else None,
        }
        for row in latest.values()
    ]


def record_auto_decision(
    session: Session, application: LoanApplication, result: DecisionResult
) -> CreditDecision:
    config = load_decision_config()
    product_code = application.product.product_code
    rate = (
        compute_rate(product_code, result.score, config)
        if result.outcome in (DecisionOutcome.APPROVED, DecisionOutcome.COUNTER_OFFER)
        else None
    )
    snapshot = build_auto_snapshot(
        result=result,
        config=config,
        as_of=as_of_date(),
        product_max=application.product.max_amt,
        external_checks=_external_checks_block(session, application),
        rate=rate,
    )
    return record_decision(
        session,
        application,
        decision_type=DecisionType.AUTO,
        user_id=None,
        outcome=result.outcome,
        score=result.score,
        factors=result.factors,
        reason=result.reason,
        comment=None,
        snapshot=snapshot,
        offer_rate=rate.total if rate else None,
        offer_amount=result.offer_amt,
        info_request=result.info_request,
        audit_comment=result.note or result.reason,
    )
