"""Каталог продуктов и профиль компании."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core.errors import NotFoundError
from app.db.models import Company, DimCreditProduct
from app.schemas.company import CompanyOut
from app.schemas.product import ProductOut
from app.services.mappers import company_out, product_out


def list_products(session: Session) -> list[ProductOut]:
    rows = session.scalars(
        select(DimCreditProduct)
        .where(DimCreditProduct.active_bool.is_(True))
        .order_by(DimCreditProduct.product_id)
    )
    return [product_out(p) for p in rows]


def get_my_company(session: Session, user: AuthUser) -> CompanyOut:
    """Сохранённый профиль компании; обновление по явной команде enrich_my_company."""
    company = session.get(Company, user.company_id)
    if company is None:
        raise NotFoundError("Компания не найдена")
    return company_out(company)


def enrich_my_company(session: Session, user: AuthUser) -> CompanyOut:
    from datetime import date

    from app.core.errors import ServiceUnavailableError
    from app.domain.enums import CheckSource, CheckStatus
    from app.integrations.http import HttpExternalChecks

    company = session.get(Company, user.company_id, with_for_update=True)
    if company is None:
        raise NotFoundError("Компания не найдена")
    result = HttpExternalChecks().fetch(CheckSource.EGRUL, company.inn_code)
    if result.status != CheckStatus.OK:
        raise ServiceUnavailableError("Профиль компании временно недоступен. Повторите позже")
    data = result.data
    company.registration_dt = date.fromisoformat(data["registrationDate"])
    for key, attr in (
        ("name", "company_name"),
        ("ogrn", "ogrn_code"),
        ("legalAddress", "legal_address_desc"),
    ):
        if data.get(key):
            setattr(company, attr, data[key])
    session.commit()
    return company_out(company)
