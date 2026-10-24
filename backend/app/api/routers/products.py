from fastapi import APIRouter

from app.api.deps import ClientUser, DbSession
from app.api.responses import R401, R403, R422
from app.schemas.product import ProductOut, RecommendationRequest, RecommendationsOut
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


@router.post(
    "/recommendations",
    response_model=RecommendationsOut,
    summary="Подбор продукта по цели",
    responses={**R401, **R403, **R422},
)
def recommendProducts(
    body: RecommendationRequest, user: ClientUser, session: DbSession
) -> RecommendationsOut:
    """Продукты по убыванию соответствия цели, сумме и сроку, с причинами оценки. Без LLM, правила в `recommendation.yaml`."""
    return catalog.recommend_products(session, body)
