from fastapi import APIRouter

from app.api.deps import ClientUser
from app.api.responses import R401, R403
from app.core.errors import NotImplementedProblem
from app.schemas.product import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get(
    "",
    response_model=list[ProductOut],
    summary="Каталог кредитных продуктов",
    responses={**R401, **R403},
)
def listProducts(user: ClientUser) -> list[ProductOut]:
    """Активные продукты с диапазонами суммы и срока, базовой ставкой и требованиями."""
    raise NotImplementedProblem()
