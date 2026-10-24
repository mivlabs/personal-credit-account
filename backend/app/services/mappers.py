"""ORM → схемы API."""

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import (
    Company,
    CreditDecision,
    DimCreditProduct,
    InfoRequest,
    LoanApplication,
    LoanApplicationAud,
    LoanOffer,
)
from app.domain.decision.config import load_decision_config
from app.domain.decision.snapshot import explain
from app.domain.enums import (
    STATUS_NAMES,
    ApplicationField,
    ApplicationStatus,
    InfoRequestStatus,
)
from app.domain.pricing import RateBreakdown, rate_from
from app.domain.timeline import ACTION_REQUIRED_STATUSES
from app.schemas.application import (
    ApplicationOut,
    ApplicationSummary,
    ClientDecisionOut,
    DecisionExplanationOut,
    InfoRequestOut,
    OfferOut,
    StatusHistoryItem,
)
from app.schemas.company import CompanyOut
from app.schemas.product import ProductOut, RateBreakdownOut

S = ApplicationStatus

# Решение и причина показываются клиенту, только когда заявка уже прошла оценку
_DECISION_VISIBLE = frozenset(
    {
        S.NEEDS_INFO,
        S.MANUAL_REVIEW,
        S.APPROVED,
        S.COUNTER_OFFER,
        S.REJECTED,
        S.OFFER_ACCEPTED,
        S.SIGNING,
        S.ISSUED,
        S.DECLINED_BY_CLIENT,
    }
)


def status_name(code: str) -> str:
    return STATUS_NAMES[ApplicationStatus(code)]


def rate_breakdown_out(b: RateBreakdown) -> RateBreakdownOut:
    return RateBreakdownOut(
        key_rate=b.key_rate,
        key_rate_date=b.key_rate_date,
        key_rate_source=b.key_rate_source,
        product_spread=b.product_spread,
        risk_surcharge=b.risk_surcharge,
        total=b.total,
    )


def product_out(p: DimCreditProduct) -> ProductOut:
    # Ставка каталога — «от X %» из той же функции, что и ставка оффера
    breakdown = rate_from(p.product_code, load_decision_config())
    return ProductOut(
        code=p.product_code,
        name=p.product_name,
        min_amount=p.min_amt,
        max_amount=p.max_amt,
        min_term_months=p.min_term_qnt,
        max_term_months=p.max_term_qnt,
        rate=breakdown.total,
        rate_from=breakdown.total,
        rate_breakdown=rate_breakdown_out(breakdown),
        requirements=p.requirement_desc,
    )


def company_out(c: Company) -> CompanyOut:
    return CompanyOut(
        id=c.company_id,
        inn=c.inn_code,
        ogrn=c.ogrn_code,
        name=c.company_name,
        legal_form=c.legal_form_code,
        registration_date=c.registration_dt,
        legal_address=c.legal_address_desc,
    )


def history_items(rows: list[LoanApplicationAud]) -> list[StatusHistoryItem]:
    return [
        StatusHistoryItem(
            from_status=r.from_status_code,
            to_status=r.to_status_code,
            to_status_name=status_name(r.to_status_code),
            at=r.create_dttm,
        )
        for r in rows
    ]


def parse_fields(raw: str) -> list[ApplicationField]:
    try:
        return [ApplicationField(v) for v in json.loads(raw)]
    except (ValueError, TypeError):
        return []


def info_request_out(r: InfoRequest) -> InfoRequestOut:
    return InfoRequestOut(
        id=r.request_id,
        description=r.request_desc,
        fields=parse_fields(r.field_list_cval),
        status=r.request_status_code,
        created_at=r.create_dttm,
        answered_at=r.answer_dttm,
        due_at=r.due_dttm,
    )


def offer_breakdown(total: Decimal, product_code: str) -> RateBreakdownOut | None:
    """Разложение ставки оффера на параметрах политики; None, если ставка не сходится с политикой."""
    config = load_decision_config()
    base = rate_from(product_code, config)
    surcharge = total - base.total
    if surcharge not in (Decimal(0), config.risk_surcharge_pct):
        return None
    return rate_breakdown_out(replace(base, risk_surcharge=surcharge, total=total))


def breakdown_from_snapshot(rate: dict) -> RateBreakdownOut:
    return RateBreakdownOut(
        key_rate=Decimal(rate["keyRate"]),
        key_rate_date=date.fromisoformat(rate["keyRateDate"]),
        key_rate_source=rate["keyRateSource"],
        product_spread=Decimal(rate["productSpread"]),
        risk_surcharge=Decimal(rate["riskSurcharge"]),
        total=Decimal(rate["total"]),
    )


def offer_out(o: LoanOffer, product_code: str = "WORKING_CAPITAL", snapshot: dict | None = None) -> OfferOut:
    return OfferOut(
        id=o.offer_id,
        amount=o.offer_amt,
        term_months=o.term_qnt,
        rate=o.rate_nval,
        # Разложение берём из снимка решения, чтобы оно не зависело от текущего конфига
        rate_breakdown=(
            breakdown_from_snapshot(snapshot["rate"])
            if snapshot and snapshot.get("rate")
            else offer_breakdown(o.rate_nval, product_code)
        ),
        monthly_payment=None if product_code == "OVERDRAFT" else o.monthly_payment_amt,
        status=o.offer_status_code,
        accepted_at=o.accept_dttm,
        signed_at=o.sign_dttm,
        valid_until=o.valid_until_dttm,
    )


def audit_rows(session: Session, application_id: int) -> list[LoanApplicationAud]:
    return list(
        session.scalars(
            select(LoanApplicationAud)
            .where(LoanApplicationAud.application_id == application_id)
            .order_by(LoanApplicationAud.audit_id)
        )
    )


def latest_decision(session: Session, application_id: int) -> CreditDecision | None:
    return session.scalar(
        select(CreditDecision)
        .where(CreditDecision.application_id == application_id)
        .order_by(desc(CreditDecision.decision_id))
        .limit(1)
    )


def latest_offer(session: Session, application_id: int) -> LoanOffer | None:
    return session.scalar(
        select(LoanOffer)
        .join(CreditDecision, CreditDecision.decision_id == LoanOffer.decision_id)
        .where(CreditDecision.application_id == application_id)
        .order_by(desc(LoanOffer.offer_id))
        .limit(1)
    )


def open_info_requests(session: Session, application_id: int) -> list[InfoRequest]:
    return list(
        session.scalars(
            select(InfoRequest)
            .where(
                InfoRequest.application_id == application_id,
                InfoRequest.request_status_code == InfoRequestStatus.OPEN.value,
            )
            .order_by(InfoRequest.request_id)
        )
    )


def latest_auto_snapshot(session: Session, application_id: int) -> dict | None:
    return session.scalar(
        select(CreditDecision.decision_snapshot)
        .where(
            CreditDecision.application_id == application_id,
            CreditDecision.decision_type_code == "AUTO",
            CreditDecision.decision_snapshot.is_not(None),
        )
        .order_by(desc(CreditDecision.decision_id))
        .limit(1)
    )


def decision_explanation(session: Session, decision: CreditDecision) -> DecisionExplanationOut | None:
    auto = (
        latest_auto_snapshot(session, decision.application_id)
        if decision.decision_type_code == "MANUAL"
        else None
    )
    data = explain(decision.decision_snapshot, auto)
    return DecisionExplanationOut.model_validate(data) if data else None


def application_out(session: Session, app: LoanApplication, role: str = "CLIENT") -> ApplicationOut:
    # Триггеры БД и коммиты меняют строку «за спиной» объекта: перечитываем актуальное состояние
    session.refresh(app)
    status = ApplicationStatus(app.status_code)

    decision = latest_decision(session, app.application_id) if status in _DECISION_VISIBLE else None
    offer = latest_offer(session, app.application_id)
    offer_decision = session.get(CreditDecision, offer.decision_id) if offer else None
    explanation = decision_explanation(session, decision) if decision and decision.decision_snapshot else None

    actions = (
        {
            S.DRAFT: ["edit", "submit", "withdraw"],
            S.NEEDS_INFO: ["answer_info", "withdraw"],
            S.MANUAL_REVIEW: ["withdraw"],
            S.APPROVED: ["accept_offer", "decline_offer"],
            S.COUNTER_OFFER: ["accept_offer", "decline_offer"],
            S.SIGNING: ["sign"],
        }.get(status, [])
        if role == "CLIENT"
        else (["decide", "recheck"] if status == S.MANUAL_REVIEW else [])
    )
    return ApplicationOut(
        available_actions=actions,
        id=app.application_id,
        company_id=app.company_id,
        product=product_out(app.product),
        status=status,
        status_name=STATUS_NAMES[status],
        requested_amount=app.requested_amt,
        term_months=app.term_qnt,
        purpose=app.purpose_desc,
        revenue_amount=app.revenue_amt,
        debt_amount=app.debt_amt,
        draft_step=app.draft_step_qnt,
        submitted_at=app.submit_dttm,
        created_at=app.create_dttm,
        updated_at=app.modify_dttm,
        history=history_items(audit_rows(session, app.application_id)),
        open_info_requests=(
            [info_request_out(r) for r in open_info_requests(session, app.application_id)]
            if status == S.NEEDS_INFO
            else []
        ),
        decision=(
            ClientDecisionOut(
                outcome=decision.outcome_code, reason=decision.reason_desc, decided_at=decision.create_dttm
            )
            if decision
            else None
        ),
        decision_explanation=explanation,
        offer=(
            offer_out(offer, app.product.product_code, offer_decision.decision_snapshot) if offer else None
        ),
    )


def application_summary(app: LoanApplication) -> ApplicationSummary:
    status = ApplicationStatus(app.status_code)
    return ApplicationSummary(
        id=app.application_id,
        product_code=app.product.product_code,
        product_name=app.product.product_name,
        status=status,
        status_name=STATUS_NAMES[status],
        requested_amount=app.requested_amt,
        term_months=app.term_qnt,
        draft_step=app.draft_step_qnt,
        action_required=status in ACTION_REQUIRED_STATUSES,
        created_at=app.create_dttm,
        updated_at=app.modify_dttm,
    )
