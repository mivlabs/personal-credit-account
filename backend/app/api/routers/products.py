from fastapi import APIRouter

from app.api.deps import ClientUser, DbSession
from app.api.responses import R401, R403
from app.schemas.product import ProductOut
from app.services import catalog

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=list[ProductOut],
    summary="Каталог кредитных продуктов",
    responses={**R401, **R403},
)
def listProducts(user: ClientUser, session: DbSession) -> list[ProductOut]:
    """Активные продукты с диапазонами суммы и срока, базовой ставкой и требованиями."""
    return catalog.list_products(session)
