import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, InvalidTransitionError
from app.db.models import Company, DimCreditProduct, LoanApplication, LoanApplicationAud
from app.domain.enums import ApplicationStatus
from app.domain.state_machine import (
    TRANSITIONS,
    Actor,
    record_creation,
    targets_from,
    transition,
)

S = ApplicationStatus
ALL = list(ApplicationStatus)


def make_application(db: Session, status: ApplicationStatus) -> LoanApplication:
    company = db.scalar(select(Company).where(Company.inn_code == "770100000001"))
    product = db.scalar(select(DimCreditProduct).where(DimCreditProduct.product_code == "EQUIPMENT"))
    app = LoanApplication(
        company_id=company.company_id,
        product_id=product.product_id,
        status_code=status.value,
        requested_amt=1_000_000,
        term_qnt=24,
    )
    db.add(app)
    db.flush()
    return app


def audit_of(db: Session, app: LoanApplication) -> list[LoanApplicationAud]:
    return list(
        db.scalars(
            select(LoanApplicationAud)
            .where(LoanApplicationAud.application_id == app.application_id)
            .order_by(LoanApplicationAud.audit_id)
        )
    )


@pytest.mark.parametrize("rule", TRANSITIONS, ids=lambda t: f"{t.source}->{t.target}")
def test_allowed_transition_changes_status_and_writes_audit(db: Session, rule):
    app = make_application(db, rule.source)

    row = transition(db, app, rule.target, None, "проверка", actor=rule.actor)

    assert app.status_code == rule.target.value
    assert (row.from_status_code, row.to_status_code) == (rule.source.value, rule.target.value)
    assert [(a.from_status_code, a.to_status_code, a.event_desc) for a in audit_of(db, app)] == [
        (rule.source.value, rule.target.value, "проверка")
    ]


def test_every_forbidden_transition_is_rejected_without_side_effects(db: Session):
    for source in ALL:
        app = make_application(db, source)
        allowed = set(targets_from(source))
        for target in ALL:
            if target in allowed:
                continue
            with pytest.raises(InvalidTransitionError):
                transition(db, app, target, None, "нельзя")
            assert app.status_code == source.value
        assert audit_of(db, app) == []


def test_wrong_actor_is_forbidden(db: Session):
    app = make_application(db, S.MANUAL_REVIEW)
    with pytest.raises(ForbiddenError):
        transition(db, app, S.APPROVED, None, "клиент не решает", actor=Actor.CLIENT)
    assert app.status_code == S.MANUAL_REVIEW.value


def test_stale_in_memory_status_is_rejected(db: Session):
    app = make_application(db, S.DRAFT)
    db.execute(
        update(LoanApplication)
        .where(LoanApplication.application_id == app.application_id)
        .values(status_code="SUBMITTED")
        .execution_options(synchronize_session=False)  # объект в памяти остаётся со старым статусом
    )
    assert app.status_code == "DRAFT"
    with pytest.raises(InvalidTransitionError, match="уже изменился"):
        transition(db, app, S.SUBMITTED, None, "гонка")


def test_draft_creation_is_audited_with_null_from_status(db: Session):
    app = make_application(db, S.DRAFT)
    row = record_creation(db, app, None)
    assert row.from_status_code is None
    assert row.to_status_code == S.DRAFT.value


def test_audit_rows_cannot_be_updated_deleted_or_truncated(db: Session):
    app = make_application(db, S.DRAFT)
    record_creation(db, app, None)

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(update(LoanApplicationAud).values(event_desc="подмена"))
    db.rollback()

    app = make_application(db, S.DRAFT)
    record_creation(db, app, None)
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM loan_application_aud"))
    db.rollback()

    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("TRUNCATE loan_application_aud"))
