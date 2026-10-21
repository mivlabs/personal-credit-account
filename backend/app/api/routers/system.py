from fastapi import APIRouter

from app.api.responses import R503
from app.core.errors import NotImplementedProblem
from app.schemas.system import HealthOut

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Проверка работоспособности",
    responses={**R503},
)
def getHealth() -> HealthOut:
    """Без префикса `/api/v1` и без авторизации; проверяет соединение с БД. Для healthcheck в compose."""
    raise NotImplementedProblem()
