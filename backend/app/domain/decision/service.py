"""Запись решения по заявке: общая для автоматического и ручного решения.

В одной транзакции: credit_decision, факторы, оффер (для одобрения и контроффера), запрос данных
(для NEEDS_INFO) и переход статуса через стейт-машину.
"""

import json
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import CreditDecision, DecisionFactor, InfoRequest, LoanApplication, LoanOffer
from app.domain.decision.config import load_decision_config
from app.domain.decision.engine import DecisionResult, FactorResult, InfoRequestSpec
from app.domain.enums import (
    ApplicationStatus,
    DecisionOutcome,
    DecisionType,
    InfoRequestStatus,
    OfferStatus,
)
from app.domain.offers import monthly_payment
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
) -> CreditDecision:
    decision = CreditDecision(
        application_id=application.application_id,
        user_id=user_id,
        decision_type_code=decision_type.value,
        outcome_code=outcome.value,
        score_qnt=score,
        reason_desc=reason,
        comment_desc=comment,
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
        rate = offer_rate if offer_rate is not None else application.product.rate_nval
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


def record_auto_decision(
    session: Session, application: LoanApplication, result: DecisionResult
) -> CreditDecision:
    config = load_decision_config()
    return record_decision(
        session,
        application,
        decision_type=DecisionType.AUTO,
        user_id=None,
        outcome=result.outcome,
        score=result.score,
        factors=result.factors,
        reason=result.reason,
        comment=json.dumps(
            {
                "rules": config.model_dump(mode="json"),
                "externalData": session.info.get("decision_external_snapshot", {}),
                "provenance": {
                    "annualRevenue": "client" if application.revenue_amt is not None else "FNS",
                    "debtAmount": "client" if application.debt_amt is not None else "BKI",
                },
                "ruleCode": result.rule_code,
                "limit": str(result.limit) if result.limit is not None else None,
                "inputs": {
                    "requestedAmount": str(application.requested_amt),
                    "annualRevenue": str(application.revenue_amt)
                    if application.revenue_amt is not None
                    else None,
                    "debtAmount": str(application.debt_amt) if application.debt_amt is not None else None,
                },
            },
            ensure_ascii=False,
        ),
        offer_rate=(
            config.base_rate_pct
            + config.product_spreads[application.product.product_code]
            + (
                config.risk_surcharge_pct
                if result.score is not None and result.score < config.low_risk_threshold
                else Decimal(0)
            )
        ),
        offer_amount=result.offer_amt,
        info_request=result.info_request,
        audit_comment=result.note or result.reason,
    )
