from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.api.responses import R503
from app.core.errors import ServiceUnavailableError
from app.schemas.system import HealthOut

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Проверка работоспособности",
    responses={**R503},
)
def getHealth(session: DbSession) -> HealthOut:
    """Без префикса `/api/v1` и без авторизации; проверяет соединение с БД. Для healthcheck в compose."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError("База данных недоступна") from exc
    return HealthOut(status="ok", database="ok")
