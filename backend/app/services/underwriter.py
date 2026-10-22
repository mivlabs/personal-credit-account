"""Сценарии андеррайтера: очередь, экран заявки, ручное решение, аудит."""

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core.errors import InvalidTransitionError, ValidationProblem, field_error
from app.db.models import (
    AppUser,
    CreditDecision,
    ExternalCheck,
    LoanApplication,
    LoanApplicationAud,
)
from app.domain.decision.engine import InfoRequestSpec
from app.domain.decision.service import record_decision
from app.domain.enums import (
    STATUS_NAMES,
    ApplicationStatus,
    DecisionOutcome,
    DecisionType,
    ManualOutcome,
)
from app.schemas.application import ApplicationOut
from app.schemas.underwriter import (
    AuditEntryOut,
    DecisionDetailOut,
    DecisionFactorOut,
    DecisionRequest,
    ExternalCheckOut,
    QueueItem,
    QueueOut,
    UnderwriterApplicationOut,
)
from app.services.access import load_application
from app.services.mappers import application_out, audit_rows, company_out, status_name
from app.services.validation import fmt_rub, range_errors

S = ApplicationStatus

_DEFAULT_QUEUE_REASON = "Требуется решение специалиста"

_DEFAULT_CLIENT_REASON = {
    ManualOutcome.APPROVED: "Заявка одобрена специалистом банка",
    ManualOutcome.COUNTER_OFFER: "Специалист банка предложил другие условия",
    ManualOutcome.REJECTED: "К сожалению, по заявке принято отрицательное решение",
}


def _entered_manual_review():
    """Подзапрос: id последней записи аудита о входе заявки в MANUAL_REVIEW."""
    return (
        select(
            LoanApplicationAud.application_id,
            func.max(LoanApplicationAud.audit_id).label("aud_id"),
        )
        .where(LoanApplicationAud.to_status_code == S.MANUAL_REVIEW.value)
        .group_by(LoanApplicationAud.application_id)
        .subquery()
    )


def get_queue(session: Session, limit: int, offset: int) -> QueueOut:
    entered = _entered_manual_review()
    rows = session.execute(
        select(LoanApplication, LoanApplicationAud)
        .join(entered, entered.c.application_id == LoanApplication.application_id)
        .join(LoanApplicationAud, LoanApplicationAud.audit_id == entered.c.aud_id)
        .where(LoanApplication.status_code == S.MANUAL_REVIEW.value)
        .order_by(LoanApplicationAud.create_dttm, LoanApplicationAud.audit_id)  # старые сверху
        .limit(limit)
        .offset(offset)
    ).all()
    total = session.scalar(
        select(func.count())
        .select_from(LoanApplication)
        .where(LoanApplication.status_code == S.MANUAL_REVIEW.value)
    )

    ids = [app.application_id for app, _ in rows]
    scores: dict[int, int | None] = {}
    if ids:
        for d in session.scalars(
            select(CreditDecision)
            .where(CreditDecision.application_id.in_(ids))
            .order_by(CreditDecision.decision_id)
        ):
            scores[d.application_id] = d.score_qnt  # последнее решение перекрывает предыдущие

    now = datetime.now(UTC)
    items = [
        QueueItem(
            application_id=app.application_id,
            company_name=app.company.company_name,
            product_code=app.product.product_code,
            product_name=app.product.product_name,
            requested_amount=app.requested_amt,
            score=scores.get(app.application_id),
            submitted_at=app.submit_dttm or app.create_dttm,
            waiting_seconds=max(0, int((now - aud.create_dttm).total_seconds())),
            queue_reason=aud.event_desc or _DEFAULT_QUEUE_REASON,
        )
        for app, aud in rows
    ]
    return QueueOut(items=items, total=total or 0, limit=limit, offset=offset)


def _parse_json(raw: str | None):
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return {"raw": raw}
    return value if isinstance(value, dict) else {"value": value}


def get_underwriter_application(
    session: Session, user: AuthUser, application_id: int
) -> UnderwriterApplicationOut:
    app = load_application(session, application_id, user)

    checks = session.scalars(
        select(ExternalCheck)
        .where(ExternalCheck.application_id == application_id)
        .order_by(ExternalCheck.check_id)
    ).all()

    decisions = session.scalars(
        select(CreditDecision)
        .where(CreditDecision.application_id == application_id)
        .order_by(CreditDecision.decision_id.desc())
    ).all()
    user_ids = {d.user_id for d in decisions if d.user_id is not None}
    names = (
        dict(
            session.execute(
                select(AppUser.user_id, AppUser.user_name).where(AppUser.user_id.in_(user_ids))
            ).all()
        )
        if user_ids
        else {}
    )

    queue_reason = None
    if app.status_code == S.MANUAL_REVIEW.value:
        queue_reason = _DEFAULT_QUEUE_REASON
        for row in reversed(audit_rows(session, application_id)):
            if row.to_status_code == S.MANUAL_REVIEW.value:
                queue_reason = row.event_desc or _DEFAULT_QUEUE_REASON
                break

    return UnderwriterApplicationOut(
        application=application_out(session, app),
        company=company_out(app.company),
        external_checks=[
            ExternalCheckOut(
                id=c.check_id,
                source=c.source_code,
                status=c.check_status_code,
                response=_parse_json(c.response_cval),
                requested_at=c.request_dttm,
                responded_at=c.response_dttm,
            )
            for c in checks
        ],
        decisions=[
            DecisionDetailOut(
                id=d.decision_id,
                type=d.decision_type_code,
                outcome=d.outcome_code,
                score=d.score_qnt,
                reason=d.reason_desc,
                comment=d.comment_desc,
                decided_by=names.get(d.user_id),
                created_at=d.create_dttm,
                factors=[
                    DecisionFactorOut(code=f.factor_code, value=f.factor_cval, points=f.point_qnt)
                    for f in d.factors
                ],
            )
            for d in decisions
        ],
        queue_reason=queue_reason,
    )


def make_decision(
    session: Session, user: AuthUser, application_id: int, body: DecisionRequest
) -> ApplicationOut:
    app = load_application(session, application_id, user, lock=True)
    if app.status_code != S.MANUAL_REVIEW.value:
        raise InvalidTransitionError(
            f"Ручное решение возможно в статусе «{STATUS_NAMES[S.MANUAL_REVIEW]}», "
            f"сейчас: «{status_name(app.status_code)}»"
        )

    errors = []
    outcome = body.outcome
    if outcome == ManualOutcome.COUNTER_OFFER:
        if body.offer_amount is None:
            errors.append(field_error("offerAmount", "Для встречного предложения укажите сумму", "REQUIRED"))
        else:
            if app.requested_amt is not None and body.offer_amount >= app.requested_amt:
                errors.append(
                    field_error(
                        "offerAmount",
                        f"Встречная сумма должна быть меньше запрошенной ({fmt_rub(app.requested_amt)} ₽)",
                        "NOT_LESS_THAN_REQUESTED",
                    )
                )
            errors += [
                {**e, "field": "offerAmount"}
                for e in range_errors(app.product, amount=body.offer_amount, term=None)
            ]
        errors += [
            {**e, "field": "offerTermMonths"}
            for e in range_errors(app.product, amount=None, term=body.offer_term_months)
        ]
    if outcome == ManualOutcome.NEEDS_INFO and body.info_request is None:
        errors.append(field_error("infoRequest", "Укажите, какие данные нужно дозаполнить", "REQUIRED"))
    if errors:
        raise ValidationProblem("Решение нельзя сохранить: исправьте отмеченные поля", errors=errors)

    if outcome == ManualOutcome.NEEDS_INFO:
        reason = body.client_reason or body.info_request.description
        info = InfoRequestSpec(body.info_request.description, list(body.info_request.fields))
    else:
        reason = body.client_reason or _DEFAULT_CLIENT_REASON[outcome]
        info = None

    record_decision(
        session,
        app,
        decision_type=DecisionType.MANUAL,
        user_id=user.id,
        outcome=DecisionOutcome(outcome.value),
        score=None,
        factors=[],
        reason=reason,
        comment=body.comment,
        offer_amount=body.offer_amount if outcome == ManualOutcome.COUNTER_OFFER else None,
        offer_term_months=body.offer_term_months if outcome == ManualOutcome.COUNTER_OFFER else None,
        info_request=info,
        audit_comment=body.comment,
    )
    session.commit()
    return application_out(session, app)


def get_audit(session: Session, user: AuthUser, application_id: int) -> list[AuditEntryOut]:
    load_application(session, application_id, user)
    rows = session.execute(
        select(LoanApplicationAud, AppUser.user_name)
        .outerjoin(AppUser, AppUser.user_id == LoanApplicationAud.user_id)
        .where(LoanApplicationAud.application_id == application_id)
        .order_by(LoanApplicationAud.audit_id)
    ).all()
    return [
        AuditEntryOut(
            id=a.audit_id,
            user_id=a.user_id,
            user_name=name,
            from_status=a.from_status_code,
            to_status=a.to_status_code,
            comment=a.event_desc,
            created_at=a.create_dttm,
        )
        for a, name in rows
    ]
