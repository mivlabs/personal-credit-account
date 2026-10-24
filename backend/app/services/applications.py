"""Сценарии клиента: черновик, подача, дозаполнение, оффер, подписание, таймлайн."""

import hmac

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core import clock
from app.core.config import get_settings
from app.core.errors import (
    IdempotencyConflictError,
    InvalidTransitionError,
    ValidationProblem,
    field_error,
)
from app.db.models import DimCreditProduct, Disbursement, LoanApplication, LoanOffer
from app.domain.enums import (
    STATUS_NAMES,
    ApplicationField,
    ApplicationStatus,
    InfoRequestStatus,
    OfferStatus,
)
from app.domain.fields import FIELD_ATTR, SCHEMA_ATTR
from app.domain.pipeline import process_pipeline
from app.domain.state_machine import Actor, record_creation, transition
from app.domain.timeline import build_stages
from app.schemas.application import (
    AcceptOfferResponse,
    ApplicationCreate,
    ApplicationOut,
    ApplicationSummary,
    ApplicationUpdate,
    MissingInfoAnswer,
    TimelineOut,
    TimelineStage,
)
from app.services.access import load_application
from app.services.expiry import ensure_not_expired
from app.services.mappers import (
    application_out,
    application_summary,
    audit_rows,
    history_items,
    latest_offer,
    open_info_requests,
    parse_fields,
    status_name,
)
from app.services.validation import fmt_rub, range_errors, submit_errors

S = ApplicationStatus


def _commit(session: Session) -> None:
    if session.info.get("defer_commit"):
        session.flush()
    else:
        session.commit()


# Поля схемы дозаполнения/обновления, которые мапятся на колонки заявки
_DRAFT_ATTRS = {
    "requested_amount": "requested_amt",
    "term_months": "term_qnt",
    "purpose": "purpose_desc",
    "revenue_amount": "revenue_amt",
    "debt_amount": "debt_amt",
    "draft_step": "draft_step_qnt",
}


def list_my_applications(
    session: Session,
    user: AuthUser,
    status: ApplicationStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ApplicationSummary]:
    rows = session.scalars(
        select(LoanApplication)
        .where(LoanApplication.company_id == user.company_id)
        .where(LoanApplication.status_code == status.value if status else True)
        .order_by(desc(LoanApplication.application_id))
        .limit(limit)
        .offset(offset)
    ).unique()
    return [application_summary(a) for a in rows]


def get_application(session: Session, user: AuthUser, application_id: int) -> ApplicationOut:
    return application_out(session, load_application(session, application_id, user), user.role.value)


def create_draft(session: Session, user: AuthUser, body: ApplicationCreate) -> ApplicationOut:
    product = session.scalar(
        select(DimCreditProduct).where(
            DimCreditProduct.product_code == body.product_code.value,
            DimCreditProduct.active_bool.is_(True),
        )
    )
    if product is None:
        raise ValidationProblem(
            "Такого продукта нет в каталоге",
            errors=[field_error("productCode", "Продукт недоступен", "UNKNOWN_PRODUCT")],
        )
    app = LoanApplication(
        company_id=user.company_id,
        product_id=product.product_id,
        status_code=S.DRAFT.value,
        requested_amt=body.requested_amount,
        term_qnt=body.term_months,
        purpose_desc=body.purpose,
        revenue_amt=body.revenue_amount,
        debt_amt=body.debt_amount,
        draft_step_qnt=body.draft_step,
    )
    session.add(app)
    session.flush()
    record_creation(session, app, user.id)
    _commit(session)
    return application_out(session, app)


def update_draft(
    session: Session, user: AuthUser, application_id: int, body: ApplicationUpdate
) -> ApplicationOut:
    app = load_application(session, application_id, user, lock=True)
    if app.status_code != S.DRAFT.value:
        raise InvalidTransitionError(
            f"Заявку можно изменять только в статусе «{STATUS_NAMES[S.DRAFT]}», "
            f"сейчас: «{status_name(app.status_code)}»"
        )
    for schema_attr, model_attr in _DRAFT_ATTRS.items():
        if schema_attr in body.model_fields_set:
            setattr(app, model_attr, getattr(body, schema_attr))
    _commit(session)
    return application_out(session, app)


def submit_application(
    session: Session, user: AuthUser, application_id: int, idempotency_key: str
) -> tuple[ApplicationOut, bool]:
    """Подача заявки. Возвращает (заявка, создан_новый_переход): False — повтор с тем же ключом."""
    app = load_application(session, application_id, user, lock=True)

    if app.status_code != S.DRAFT.value:
        if app.idempotency_key_code == idempotency_key:
            return application_out(session, app), False
        raise IdempotencyConflictError("Заявка уже подана (с другим ключом идемпотентности)")

    errors = submit_errors(app)
    if errors:
        raise ValidationProblem("Заявку нельзя подать: исправьте отмеченные поля", errors=errors)

    used_elsewhere = session.scalar(
        select(LoanApplication.application_id).where(
            LoanApplication.idempotency_key_code == idempotency_key,
            LoanApplication.application_id != app.application_id,
        )
    )
    if used_elsewhere is not None:
        raise IdempotencyConflictError("Этот ключ идемпотентности уже использован для другой заявки")

    app.idempotency_key_code = idempotency_key
    app.submit_dttm = clock.now()
    transition(session, app, S.SUBMITTED, user.id, "Заявка подана клиентом", actor=Actor.CLIENT)
    process_pipeline(session, app)
    try:
        _commit(session)
    except IntegrityError as exc:
        session.rollback()
        raise IdempotencyConflictError("Этот ключ идемпотентности уже использован") from exc
    return application_out(session, app), True


def get_timeline(session: Session, user: AuthUser, application_id: int) -> TimelineOut:
    app = load_application(session, application_id, user)
    rows = audit_rows(session, app.application_id)
    status = S(app.status_code)
    stages = build_stages(status, [(S(r.to_status_code), r.create_dttm) for r in rows])
    return TimelineOut(
        application_id=app.application_id,
        current_status=status,
        current_status_name=STATUS_NAMES[status],
        stages=[TimelineStage(**s) for s in stages],
        history=history_items(rows),
    )


def answer_missing_info(
    session: Session, user: AuthUser, application_id: int, body: MissingInfoAnswer
) -> ApplicationOut:
    """Клиент дозаполняет только запрошенные поля: NEEDS_INFO → CHECKING, конвейер стартует заново."""
    app = load_application(session, application_id, user, lock=True)
    if app.status_code != S.NEEDS_INFO.value:
        raise InvalidTransitionError(
            f"Дозаполнить данные можно в статусе «{STATUS_NAMES[S.NEEDS_INFO]}», "
            f"сейчас: «{status_name(app.status_code)}»"
        )

    ensure_not_expired(session, app)
    requests = open_info_requests(session, application_id)
    requested = {f for r in requests for f in parse_fields(r.field_list_cval)}

    errors = []
    provided = {}
    for field, schema_attr in SCHEMA_ATTR.items():
        in_body = schema_attr in body.model_fields_set
        value = getattr(body, schema_attr)
        if in_body and field not in requested:
            errors.append(field_error(field.value, "Это поле банк не запрашивал", "NOT_REQUESTED"))
        elif field in requested and (not in_body or value is None or value == ""):
            errors.append(field_error(field.value, "Заполните это поле", "REQUIRED"))
        elif field in requested:
            provided[field] = value
    if "draft_step" in body.model_fields_set:
        errors.append(field_error("draftStep", "Это поле банк не запрашивал", "NOT_REQUESTED"))

    errors += range_errors(
        app.product,
        amount=provided.get(ApplicationField.REQUESTED_AMOUNT),
        term=provided.get(ApplicationField.TERM_MONTHS),
    )
    if errors:
        raise ValidationProblem("Заполните только запрошенные поля", errors=errors)

    for field, value in provided.items():
        setattr(app, FIELD_ATTR[field], value)
    now = clock.now()
    for r in requests:
        r.request_status_code = InfoRequestStatus.ANSWERED.value
        r.answer_dttm = now
    transition(session, app, S.CHECKING, user.id, "Клиент дозаполнил запрошенные данные", actor=Actor.CLIENT)
    process_pipeline(session, app)
    _commit(session)
    return application_out(session, app)


def _sent_offer(session: Session, app: LoanApplication) -> LoanOffer:
    offer = latest_offer(session, app.application_id)
    if offer is None:
        raise InvalidTransitionError("У заявки нет оффера")
    return offer


def accept_offer(session: Session, user: AuthUser, application_id: int) -> AcceptOfferResponse:
    app = load_application(session, application_id, user, lock=True)
    if app.status_code not in (S.APPROVED.value, S.COUNTER_OFFER.value):
        raise InvalidTransitionError(
            f"Принять предложение можно в статусах «{STATUS_NAMES[S.APPROVED]}» и "
            f"«{STATUS_NAMES[S.COUNTER_OFFER]}», сейчас: «{status_name(app.status_code)}»"
        )
    ensure_not_expired(session, app)
    offer = _sent_offer(session, app)
    offer.offer_status_code = OfferStatus.ACCEPTED.value
    offer.accept_dttm = clock.now()
    transition(session, app, S.OFFER_ACCEPTED, user.id, "Клиент принял предложение", actor=Actor.CLIENT)
    transition(session, app, S.SIGNING, None, "Договор подготовлен к подписанию", actor=Actor.SYSTEM)
    _commit(session)
    code = get_settings().demo_sign_code
    return AcceptOfferResponse(
        application=application_out(session, app),
        sign_hint=f"Демо-режим: для подписания введите код {code}",
    )


def decline_offer(session: Session, user: AuthUser, application_id: int) -> ApplicationOut:
    app = load_application(session, application_id, user, lock=True)
    if app.status_code not in (S.APPROVED.value, S.COUNTER_OFFER.value):
        raise InvalidTransitionError(
            f"Отказаться от предложения можно в статусах «{STATUS_NAMES[S.APPROVED]}» и "
            f"«{STATUS_NAMES[S.COUNTER_OFFER]}», сейчас: «{status_name(app.status_code)}»"
        )
    ensure_not_expired(session, app)
    offer = _sent_offer(session, app)
    offer.offer_status_code = OfferStatus.DECLINED.value
    transition(
        session, app, S.DECLINED_BY_CLIENT, user.id, "Клиент отказался от предложения", actor=Actor.CLIENT
    )
    _commit(session)
    return application_out(session, app)


def withdraw_application(
    session: Session, user: AuthUser, application_id: int, reason: str | None
) -> ApplicationOut:
    """Клиент отзывает заявку до решения: DRAFT, NEEDS_INFO или MANUAL_REVIEW → WITHDRAWN."""
    app = load_application(session, application_id, user, lock=True)
    allowed = (S.DRAFT, S.NEEDS_INFO, S.MANUAL_REVIEW)
    if app.status_code not in {s.value for s in allowed}:
        raise InvalidTransitionError(
            "Отозвать заявку можно в статусах "
            + ", ".join(f"«{STATUS_NAMES[s]}»" for s in allowed)
            + f"; сейчас: «{status_name(app.status_code)}»"
        )
    comment = "Клиент отозвал заявку" + (f": {reason.strip()}" if reason and reason.strip() else "")
    transition(session, app, S.WITHDRAWN, user.id, comment, actor=Actor.CLIENT)
    _commit(session)
    return application_out(session, app)


def sign_application(session: Session, user: AuthUser, application_id: int, code: str) -> ApplicationOut:
    app = load_application(session, application_id, user, lock=True)
    if app.status_code != S.SIGNING.value:
        raise InvalidTransitionError(
            f"Подписать договор можно в статусе «{STATUS_NAMES[S.SIGNING]}», "
            f"сейчас: «{status_name(app.status_code)}»"
        )
    ensure_not_expired(
        session, app
    )  # в SIGNING срок не истекает: проверка защищает на случай новых переходов
    expected = get_settings().demo_sign_code
    if not hmac.compare_digest(code.encode(), expected.encode()):
        raise ValidationProblem(
            "Неверный код подписи",
            errors=[field_error("code", "Неверный код подтверждения", "INVALID_SIGN_CODE")],
        )
    offer = _sent_offer(session, app)
    offer.offer_status_code = OfferStatus.SIGNED.value
    offer.sign_dttm = clock.now()
    session.add(
        Disbursement(application_id=app.application_id, offer_id=offer.offer_id, amount_amt=offer.offer_amt)
    )
    transition(
        session,
        app,
        S.ISSUED,
        user.id,
        f"Договор подписан, кредит выдан: {fmt_rub(offer.offer_amt)} ₽ на {offer.term_qnt} мес.",
        actor=Actor.CLIENT,
    )
    _commit(session)
    return application_out(session, app)
