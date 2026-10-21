from typing import Annotated

from fastapi import APIRouter, Header, Path, status

from app.api.deps import AnyUser, ClientUser
from app.api.responses import CLIENT_ERRORS, R401, R403, R404, R409
from app.core.errors import NotImplementedProblem
from app.schemas.application import (
    AcceptOfferResponse,
    ApplicationCreate,
    ApplicationOut,
    ApplicationSummary,
    ApplicationUpdate,
    MissingInfoAnswer,
    SignRequest,
    TimelineOut,
)

router = APIRouter(prefix="/applications", tags=["applications"])

ApplicationId = Annotated[int, Path(ge=1, description="Идентификатор заявки")]


@router.get(
    "",
    response_model=list[ApplicationSummary],
    summary="Мои заявки",
    responses={**R401, **R403},
)
def listMyApplications(user: ClientUser) -> list[ApplicationSummary]:
    """Заявки компании клиента, новые сверху. По списку клиент находит свой черновик."""
    raise NotImplementedProblem()


@router.post(
    "",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать черновик заявки",
    responses={**CLIENT_ERRORS},
)
def createApplication(body: ApplicationCreate, user: ClientUser) -> ApplicationOut:
    """Создаёт заявку в статусе `DRAFT`: обязателен только `productCode`, остальное можно прислать позже."""
    raise NotImplementedProblem()


@router.get(
    "/{application_id}",
    response_model=ApplicationOut,
    summary="Заявка: статус, анкета, решение, оффер",
    responses={**R401, **R404},
)
def getApplication(application_id: ApplicationId, user: AnyUser) -> ApplicationOut:
    """Заявка с историей переходов, открытыми запросами данных, решением и оффером.

    Решение для клиента — исход и причина простым языком, без баллов. Клиент видит только заявки своей
    компании (чужая — 404), андеррайтер — любые.
    """
    raise NotImplementedProblem()


@router.patch(
    "/{application_id}",
    response_model=ApplicationOut,
    summary="Обновить черновик",
    responses={**CLIENT_ERRORS, **R404, **R409},
)
def updateApplication(
    application_id: ApplicationId, body: ApplicationUpdate, user: ClientUser
) -> ApplicationOut:
    """Сохраняет поля анкеты и шаг мастера (`draftStep`). Только в статусе `DRAFT`, иначе 409 `INVALID_TRANSITION`."""
    raise NotImplementedProblem()


@router.post(
    "/{application_id}/submit",
    response_model=ApplicationOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Подать заявку",
    responses={
        200: {
            "model": ApplicationOut,
            "description": "Повтор с тем же `Idempotency-Key`: возвращена та же заявка",
        },
        **CLIENT_ERRORS,
        **R404,
        **R409,
    },
)
def submitApplication(
    application_id: ApplicationId,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=64,
            description="Уникальный ключ подачи (например, UUID). Повтор с тем же ключом не создаёт ничего нового",
        ),
    ],
    user: ClientUser,
) -> ApplicationOut:
    """Проверяет обязательные поля (`requestedAmount`, `termMonths`, `purpose`) и диапазоны продукта,
    переводит заявку `DRAFT → SUBMITTED` и запускает конвейер обработки. Ответ 202: дальше заявка идёт сама.

    Другой ключ на уже поданную заявку или тот же ключ на другую заявку — 409 `IDEMPOTENCY_CONFLICT`.
    """
    raise NotImplementedProblem()


@router.get(
    "/{application_id}/timeline",
    response_model=TimelineOut,
    summary="Таймлайн статуса",
    responses={**R401, **R404},
)
def getApplicationTimeline(application_id: ApplicationId, user: AnyUser) -> TimelineOut:
    """Этапы с состоянием `done` / `current` / `upcoming`, флагом `actionRequired` и историей переходов."""
    raise NotImplementedProblem()


@router.patch(
    "/{application_id}/missing-info",
    response_model=ApplicationOut,
    summary="Дозаполнить запрошенные данные",
    responses={**CLIENT_ERRORS, **R404, **R409},
)
def answerMissingInfo(
    application_id: ApplicationId, body: MissingInfoAnswer, user: ClientUser
) -> ApplicationOut:
    """Принимает только поля из открытого запроса данных (прочие — 422). Запрос становится `ANSWERED`,
    заявка `NEEDS_INFO → CHECKING`, конвейер запускается заново."""
    raise NotImplementedProblem()


@router.post(
    "/{application_id}/offer/accept",
    response_model=AcceptOfferResponse,
    summary="Принять оффер или контроффер",
    responses={**R401, **R403, **R404, **R409},
)
def acceptOffer(application_id: ApplicationId, user: ClientUser) -> AcceptOfferResponse:
    """`APPROVED` / `COUNTER_OFFER` → `OFFER_ACCEPTED` → `SIGNING`. В ответе подсказка с демо-кодом подписи."""
    raise NotImplementedProblem()


@router.post(
    "/{application_id}/offer/decline",
    response_model=ApplicationOut,
    summary="Отказаться от оффера",
    responses={**R401, **R403, **R404, **R409},
)
def declineOffer(application_id: ApplicationId, user: ClientUser) -> ApplicationOut:
    """`APPROVED` / `COUNTER_OFFER` → `DECLINED_BY_CLIENT`, оффер получает статус `DECLINED`."""
    raise NotImplementedProblem()


@router.post(
    "/{application_id}/sign",
    response_model=ApplicationOut,
    summary="Подписать договор кодом (симуляция)",
    responses={**CLIENT_ERRORS, **R404, **R409},
)
def signApplication(application_id: ApplicationId, body: SignRequest, user: ClientUser) -> ApplicationOut:
    """Код совпал с `DEMO_SIGN_CODE` → `SIGNING → ISSUED`, оффер `SIGNED`. Неверный код — 422 по полю `code`."""
    raise NotImplementedProblem()
