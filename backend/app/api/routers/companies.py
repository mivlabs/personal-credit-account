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

    Сохранённый профиль обновляется из локального ЕГРЮЛ отдельной командой POST /companies/me/enrich.
    """
    return catalog.get_my_company(session, user)


@router.post("/me/enrich", response_model=CompanyOut, summary="Обновить профиль из ЕГРЮЛ")
def enrichMyCompany(user: ClientUser, session: DbSession) -> CompanyOut:
    return catalog.enrich_my_company(session, user)
