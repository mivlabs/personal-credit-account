"""ORM → схемы API."""

import json

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
from app.domain.enums import (
    STATUS_NAMES,
    ApplicationField,
    ApplicationStatus,
    InfoRequestStatus,
)
from app.domain.timeline import ACTION_REQUIRED_STATUSES
from app.schemas.application import (
    ApplicationOut,
    ApplicationSummary,
    ClientDecisionOut,
    InfoRequestOut,
    OfferOut,
    StatusHistoryItem,
)
from app.schemas.company import CompanyOut
from app.schemas.product import ProductOut

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


def product_out(p: DimCreditProduct) -> ProductOut:
    return ProductOut(
        code=p.product_code,
        name=p.product_name,
        min_amount=p.min_amt,
        max_amount=p.max_amt,
        min_term_months=p.min_term_qnt,
        max_term_months=p.max_term_qnt,
        rate=p.rate_nval,
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
    )


def offer_out(o: LoanOffer) -> OfferOut:
    return OfferOut(
        id=o.offer_id,
        amount=o.offer_amt,
        term_months=o.term_qnt,
        rate=o.rate_nval,
        monthly_payment=o.monthly_payment_amt,
        status=o.offer_status_code,
        accepted_at=o.accept_dttm,
        signed_at=o.sign_dttm,
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


def application_out(session: Session, app: LoanApplication) -> ApplicationOut:
    # Триггеры БД и коммиты меняют строку «за спиной» объекта: перечитываем актуальное состояние
    session.refresh(app)
    status = ApplicationStatus(app.status_code)

    decision = latest_decision(session, app.application_id) if status in _DECISION_VISIBLE else None
    offer = latest_offer(session, app.application_id)

    return ApplicationOut(
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
        open_info_requests=[info_request_out(r) for r in open_info_requests(session, app.application_id)],
        decision=(
            ClientDecisionOut(
                outcome=decision.outcome_code, reason=decision.reason_desc, decided_at=decision.create_dttm
            )
            if decision
            else None
        ),
        offer=offer_out(offer) if offer else None,
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
