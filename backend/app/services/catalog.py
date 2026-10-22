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
    """Профиль из БД. С четверга, если данных ещё нет, сюда добавится запрос в мок ЕГРЮЛ (контракт тот же)."""
    company = session.get(Company, user.company_id)
    if company is None:
        raise NotFoundError("Компания не найдена")
    return company_out(company)
