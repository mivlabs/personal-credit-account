from fastapi import APIRouter

from app.api.deps import ClientUser, DbSession
from app.api.responses import R401, R403, R404
from app.schemas.company import CompanyOut
from app.services import catalog

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get(
    "/me",
    response_model=CompanyOut,
    summary="Профиль моей компании",
    responses={**R401, **R403, **R404},
)
def getMyCompany(user: ClientUser, session: DbSession) -> CompanyOut:
    """Данные компании клиента (название, ОГРН, адрес, дата регистрации): клиент не вводит их повторно.

    Если данных ещё нет, бэкенд сам запрашивает их у ЕГРЮЛ по ИНН; контракт ответа от этого не меняется.
    """
    return catalog.get_my_company(session, user)
