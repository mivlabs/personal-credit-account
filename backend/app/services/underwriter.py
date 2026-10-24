"""Сценарии андеррайтера: очередь, экран заявки, ручное решение, аудит."""

import json
from datetime import UTC, datetime
from decimal import Decimal

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
from app.domain.clock import as_of_date
from app.domain.decision.config import load_decision_config
from app.domain.decision.engine import InfoRequestSpec
from app.domain.decision.service import record_decision
from app.domain.decision.snapshot import build_manual_snapshot
from app.domain.enums import (
    STATUS_NAMES,
    ApplicationStatus,
    DecisionOutcome,
    DecisionType,
    ManualOutcome,
)
from app.domain.pipeline import process_pipeline
from app.domain.pricing import compute_rate
from app.domain.state_machine import Actor, transition
from app.schemas.application import ApplicationOut
from app.schemas.underwriter import (
    AuditEntryOut,
    DecisionDetailOut,
    DecisionFactorOut,
    DecisionRequest,
    ExternalCheckOut,
    QueueItem,
    QueueOut,
    RecheckRequest,
    UnderwriterApplicationOut,
)
from app.services.access import load_application
from app.services.mappers import (
    application_out,
    audit_rows,
    company_out,
    latest_auto_snapshot,
    status_name,
)
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


def get_queue(
    session: Session, limit: int, offset: int, status: ApplicationStatus | None = S.MANUAL_REVIEW
) -> QueueOut:
    entered = _entered_manual_review()
    rows = session.execute(
        select(LoanApplication, LoanApplicationAud)
        .outerjoin(entered, entered.c.application_id == LoanApplication.application_id)
        .outerjoin(LoanApplicationAud, LoanApplicationAud.audit_id == entered.c.aud_id)
        .where(LoanApplication.status_code == status.value if status else True)
        .order_by(
            func.coalesce(LoanApplicationAud.create_dttm, LoanApplication.create_dttm),
            LoanApplication.application_id,
        )  # старые сверху
        .limit(limit)
        .offset(offset)
    ).all()
    total = session.scalar(
        select(func.count())
        .select_from(LoanApplication)
        .where(LoanApplication.status_code == status.value if status else True)
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
            status=app.status_code,
            status_name=status_name(app.status_code),
            company_name=app.company.company_name,
            product_code=app.product.product_code,
            product_name=app.product.product_name,
            requested_amount=app.requested_amt,
            score=scores.get(app.application_id),
            submitted_at=app.submit_dttm or app.create_dttm,
            waiting_seconds=max(
                0, int((now - (aud.create_dttm if aud else app.create_dttm)).total_seconds())
            ),
            queue_reason=(aud.event_desc if aud else None) or status_name(app.status_code),
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


def _factor_fields(raw):
    try:
        parsed = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict) and "value" in parsed:
        return {"value": parsed["value"], "explanation": parsed.get("explanation", "")}
    return {"value": raw, "explanation": ""}


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
        application=application_out(session, app, "UNDERWRITER"),
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
                snapshot=d.decision_snapshot,
                factors=[
                    DecisionFactorOut(code=f.factor_code, points=f.point_qnt, **_factor_fields(f.factor_cval))
                    for f in d.factors
                ],
            )
            for d in decisions
        ],
        queue_reason=queue_reason,
        auto_limit=_auto_limit(latest_auto_snapshot(session, application_id)),
    )


def _auto_limit(snapshot: dict | None) -> Decimal | None:
    limit = (snapshot or {}).get("limit")
    return Decimal(limit["value"]) if limit else None


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

    # Лимит берётся из последнего AUTO-снимка; без него (источник недоступен) решение не блокируем
    auto_limit = _auto_limit(latest_auto_snapshot(session, application_id))
    limit_exceeded = False
    if auto_limit is not None:
        checked = (
            app.requested_amt
            if outcome == ManualOutcome.APPROVED
            else body.offer_amount
            if outcome == ManualOutcome.COUNTER_OFFER
            else None
        )
        limit_exceeded = checked is not None and checked > auto_limit
        if limit_exceeded and not body.override_limit:
            errors.append(
                field_error(
                    "overrideLimit",
                    f"Сумма {fmt_rub(checked)} ₽ превышает расчётный лимит {fmt_rub(auto_limit)} ₽: "
                    "подтвердите решение выше лимита (overrideLimit: true) или уменьшите сумму",
                    "LIMIT_EXCEEDED",
                )
            )
    if errors:
        raise ValidationProblem("Решение нельзя сохранить: исправьте отмеченные поля", errors=errors)

    if outcome == ManualOutcome.NEEDS_INFO:
        reason = body.client_reason or body.info_request.description
        info = InfoRequestSpec(body.info_request.description, list(body.info_request.fields))
    else:
        reason = body.client_reason or _DEFAULT_CLIENT_REASON[outcome]
        info = None

    config = load_decision_config()
    # Ставка есть только у решений с оффером; балла у ручного решения нет, поэтому надбавка применяется
    rate = (
        compute_rate(app.product.product_code, None, config)
        if outcome in (ManualOutcome.APPROVED, ManualOutcome.COUNTER_OFFER)
        else None
    )
    offer_amount = body.offer_amount if outcome == ManualOutcome.COUNTER_OFFER else None
    snapshot = build_manual_snapshot(
        config=config,
        as_of=as_of_date(),
        user_id=user.id,
        user_name=session.scalar(select(AppUser.user_name).where(AppUser.user_id == user.id)),
        outcome=outcome.value,
        comment=body.comment,
        offer_amount=offer_amount,
        rate=rate,
        auto_limit=auto_limit,
        limit_exceeded=limit_exceeded,
        override_limit=body.override_limit,
    )
    audit_comment = body.comment
    if limit_exceeded:
        audit_comment = (
            f"{body.comment} [Решение выше расчётного лимита {fmt_rub(auto_limit)} ₽ принято с overrideLimit]"
        )
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
        snapshot=snapshot,
        offer_rate=rate.total if rate else None,
        offer_amount=offer_amount,
        offer_term_months=body.offer_term_months if outcome == ManualOutcome.COUNTER_OFFER else None,
        info_request=info,
        audit_comment=audit_comment,
    )
    session.commit()
    return application_out(session, app, user.role.value)


def recheck(session: Session, user: AuthUser, application_id: int, body: RecheckRequest) -> ApplicationOut:
    """MANUAL_REVIEW → EXTERNAL_CHECK и конвейер заново: новые external_check и новое AUTO-решение."""
    app = load_application(session, application_id, user, lock=True)
    if app.status_code != S.MANUAL_REVIEW.value:
        raise InvalidTransitionError(
            f"Повторная проверка возможна в статусе «{STATUS_NAMES[S.MANUAL_REVIEW]}», "
            f"сейчас: «{status_name(app.status_code)}»"
        )
    transition(
        session,
        app,
        S.EXTERNAL_CHECK,
        user.id,
        f"Повторная проверка источников: {body.comment}",
        actor=Actor.UNDERWRITER,
    )
    process_pipeline(session, app)
    session.commit()
    return application_out(session, app, user.role.value)


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
