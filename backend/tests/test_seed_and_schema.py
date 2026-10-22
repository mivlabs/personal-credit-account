from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.base import Base
from app.db.models import AppUser, Company, DimApplicationStatus, DimCreditProduct, DimUserRole
from app.db.session import get_engine, get_sessionmaker
from app.domain.enums import FINAL_STATUSES, ApplicationStatus
from app.seed.run import run_seed


def counts(db: Session) -> dict[str, int]:
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (DimUserRole, DimApplicationStatus, DimCreditProduct, Company, AppUser)
    }


def test_seed_content(db: Session):
    assert counts(db) == {
        "dim_user_role": 2,
        "dim_application_status": 14,
        "dim_credit_product": 3,
        "company": 6,
        "app_user": 7,
    }
    finals = set(
        db.scalars(select(DimApplicationStatus.status_code).where(DimApplicationStatus.final_bool.is_(True)))
    )
    assert finals == {s.value for s in FINAL_STATUSES}
    assert {s.status_code for s in db.scalars(select(DimApplicationStatus))} == {
        s.value for s in ApplicationStatus
    }

    logins = {u.login_code: u for u in db.scalars(select(AppUser))}
    assert set(logins) == {
        "client_fast",
        "client_counter",
        "client_manual",
        "client_info",
        "client_reject",
        "client_timeout",
        "underwriter",
    }
    assert all(verify_password("demo1234", u.password_hash_cval) for u in logins.values())
    assert logins["underwriter"].company_id is None and logins["underwriter"].role_code == "UNDERWRITER"


def test_seed_is_idempotent_and_does_not_touch_existing_accounts(db: Session):
    before = counts(db)
    user = db.scalar(select(AppUser).where(AppUser.login_code == "client_fast"))
    old_hash = user.password_hash_cval

    for _ in range(2):
        with get_sessionmaker()() as session, session.begin():
            run_seed(session)

    assert counts(db) == before
    db.refresh(user)
    assert user.password_hash_cval == old_hash


def test_demo_company_inns_are_stable_and_valid(db: Session):
    inns = {c.legal_form_code: [] for c in db.scalars(select(Company))}
    for c in db.scalars(select(Company).order_by(Company.company_id)):
        inns[c.legal_form_code].append(c.inn_code)
    assert inns["IP"] == ["770100000001"]
    assert inns["OOO"] == ["7701000002", "7701000003", "7701000004", "7701000005", "7701000006"]


def test_models_match_migrations():
    """Модели и схема БД после миграций не разошлись (аналог `alembic check`)."""
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_schema_has_twelve_tables_and_expected_indexes():
    insp = inspect(get_engine())
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert len(tables) == 12
    aud_indexes = {tuple(i["column_names"]) for i in insp.get_indexes("loan_application_aud")}
    assert ("application_id", "create_dttm") in aud_indexes
    assert ("status_code",) in {tuple(i["column_names"]) for i in insp.get_indexes("loan_application")}
    assert any(
        u["column_names"] == ["idempotency_key_code"] for u in insp.get_unique_constraints("loan_application")
    )
    assert any(u["column_names"] == ["decision_id"] for u in insp.get_unique_constraints("loan_offer"))
