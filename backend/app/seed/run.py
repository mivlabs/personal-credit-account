"""Идемпотентный seed: запускается при старте контейнера после миграций.

Запуск из каталога backend: uv run python -m app.seed.run
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.db.models import (
    AppUser,
    Company,
    DimApplicationStatus,
    DimCreditProduct,
    DimUserRole,
)
from app.db.session import get_sessionmaker
from app.domain.decision.config import load_decision_config
from app.domain.enums import UserRole
from app.domain.pricing import rate_from
from app.seed.data import (
    DEMO_CLIENTS,
    DEMO_PASSWORD,
    PRODUCTS,
    ROLES,
    STATUSES,
    UNDERWRITER_LOGIN,
    UNDERWRITER_NAME,
)

logger = logging.getLogger("app.seed")


def _sync_dim(session: Session, model, key, values: dict) -> str:
    """Добавляет строку справочника или обновляет, если значения изменились. Возвращает I / U / '='."""
    row = session.get(model, key)
    if row is None:
        session.add(model(**{**values, "action_ind_code": "I"}))
        return "I"
    changed = {k: v for k, v in values.items() if getattr(row, k) != v}
    if changed:
        for k, v in changed.items():
            setattr(row, k, v)
        row.action_ind_code = "U"
        return "U"
    return "="


def seed_dictionaries(session: Session) -> dict[str, int]:
    stats = {"I": 0, "U": 0, "=": 0}
    for role, name in ROLES.items():
        stats[_sync_dim(session, DimUserRole, role.value, {"role_code": role.value, "role_name": name})] += 1
    for code, name, final in STATUSES:
        values = {"status_code": code, "status_name": name, "final_bool": final}
        stats[_sync_dim(session, DimApplicationStatus, code, values)] += 1

    config = load_decision_config()
    for p in PRODUCTS:
        row = session.scalar(select(DimCreditProduct).where(DimCreditProduct.product_code == p.code.value))
        values = {
            "product_code": p.code.value,
            "product_name": p.name,
            "min_amt": p.min_amt,
            "max_amt": p.max_amt,
            "min_term_qnt": p.min_term,
            "max_term_qnt": p.max_term,
            "rate_nval": rate_from(p.code.value, config).total,
            "requirement_desc": p.requirement,
            "active_bool": True,
        }
        if row is None:
            session.add(DimCreditProduct(**values, action_ind_code="I"))
            stats["I"] += 1
        else:
            changed = {k: v for k, v in values.items() if getattr(row, k) != v}
            for k, v in changed.items():
                setattr(row, k, v)
            if changed:
                row.action_ind_code = "U"
            stats["U" if changed else "="] += 1
    session.flush()
    return stats


def seed_demo_accounts(session: Session) -> dict[str, int]:
    """Компании и пользователи только добавляются: уже существующие не трогаем."""
    created = {"companies": 0, "users": 0}
    password_hash: str | None = None

    def get_hash() -> str:
        nonlocal password_hash
        if password_hash is None:
            password_hash = hash_password(DEMO_PASSWORD)
        return password_hash

    for c in DEMO_CLIENTS:
        company = session.scalar(select(Company).where(Company.inn_code == c.inn))
        if company is None:
            company = Company(
                inn_code=c.inn,
                ogrn_code=c.ogrn,
                company_name=c.company_name,
                legal_form_code=c.legal_form.value,
                registration_dt=c.registration_dt,
                legal_address_desc=c.address,
            )
            session.add(company)
            session.flush()
            created["companies"] += 1
        if session.scalar(select(AppUser.user_id).where(AppUser.login_code == c.login)) is None:
            session.add(
                AppUser(
                    company_id=company.company_id,
                    role_code=UserRole.CLIENT.value,
                    login_code=c.login,
                    password_hash_cval=get_hash(),
                    user_name=c.user_name,
                )
            )
            created["users"] += 1

    if session.scalar(select(AppUser.user_id).where(AppUser.login_code == UNDERWRITER_LOGIN)) is None:
        session.add(
            AppUser(
                company_id=None,
                role_code=UserRole.UNDERWRITER.value,
                login_code=UNDERWRITER_LOGIN,
                password_hash_cval=get_hash(),
                user_name=UNDERWRITER_NAME,
            )
        )
        created["users"] += 1
    session.flush()
    return created


def run_seed(session: Session) -> None:
    dims = seed_dictionaries(session)
    demo = seed_demo_accounts(session)
    logger.info(
        "seed выполнен",
        extra={
            "dim_added": dims["I"],
            "dim_updated": dims["U"],
            "dim_unchanged": dims["="],
            "companies_added": demo["companies"],
            "users_added": demo["users"],
        },
    )


def main() -> None:
    setup_logging(get_settings().log_level)
    with get_sessionmaker()() as session, session.begin():
        run_seed(session)


if __name__ == "__main__":
    main()
