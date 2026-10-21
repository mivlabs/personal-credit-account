from fastapi import APIRouter

from app.api.deps import ClientUser
from app.api.responses import R401, R403, R404
from app.core.errors import NotImplementedProblem
from app.schemas.company import CompanyOut

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get(
    "/me",
    response_model=CompanyOut,
    summary="Профиль моей компании",
    responses={**R401, **R403, **R404},
)
def getMyCompany(user: ClientUser) -> CompanyOut:
    """Данные компании клиента (название, ОГРН, адрес, дата регистрации): клиент не вводит их повторно.

    Если данных ещё нет, бэкенд сам запрашивает их у ЕГРЮЛ по ИНН; контракт ответа от этого не меняется.
    """
    raise NotImplementedProblem()
