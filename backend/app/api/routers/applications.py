from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Path, Response, status

from app.api.deps import AnyUser, ClientUser, DbSession
from app.api.responses import CLIENT_ERRORS, R401, R403, R404, R409
from app.domain.pipeline import run_pipeline
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
from app.services import applications as service

router = APIRouter(prefix="/applications", tags=["applications"])

ApplicationId = Annotated[int, Path(ge=1, description="Идентификатор заявки")]


@router.get(
    "",
    response_model=list[ApplicationSummary],
    summary="Мои заявки",
    responses={**R401, **R403},
)
def listMyApplications(user: ClientUser, session: DbSession) -> list[ApplicationSummary]:
    """Заявки компании клиента, новые сверху. По списку клиент находит свой черновик."""
    return service.list_my_applications(session, user)


@router.post(
    "",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать черновик заявки",
    responses={**CLIENT_ERRORS},
)
def createApplication(body: ApplicationCreate, user: ClientUser, session: DbSession) -> ApplicationOut:
    """Создаёт заявку в статусе `DRAFT`: обязателен только `productCode`, остальное можно прислать позже."""
    return service.create_draft(session, user, body)


@router.get(
    "/{application_id}",
    response_model=ApplicationOut,
    summary="Заявка: статус, анкета, решение, оффер",
    responses={**R401, **R404},
)
def getApplication(application_id: ApplicationId, user: AnyUser, session: DbSession) -> ApplicationOut:
    """Заявка с историей переходов, открытыми запросами данных, решением и оффером.

    Решение для клиента — исход и причина простым языком, без баллов. Клиент видит только заявки своей
    компании (чужая — 404), андеррайтер — любые.
    """
    return service.get_application(session, user, application_id)


@router.patch(
    "/{application_id}",
    response_model=ApplicationOut,
    summary="Обновить черновик",
    responses={**CLIENT_ERRORS, **R404, **R409},
)
def updateApplication(
    application_id: ApplicationId, body: ApplicationUpdate, user: ClientUser, session: DbSession
) -> ApplicationOut:
    """Сохраняет поля анкеты и шаг мастера (`draftStep`). Только в статусе `DRAFT`, иначе 409 `INVALID_TRANSITION`."""
    return service.update_draft(session, user, application_id, body)


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
    session: DbSession,
    response: Response,
    background: BackgroundTasks,
) -> ApplicationOut:
    """Проверяет обязательные поля (`requestedAmount`, `termMonths`, `purpose`) и диапазоны продукта,
    переводит заявку `DRAFT → SUBMITTED` и запускает конвейер обработки. Ответ 202: дальше заявка идёт сама.

    Другой ключ на уже поданную заявку или тот же ключ на другую заявку — 409 `IDEMPOTENCY_CONFLICT`.
    """
    result, is_new = service.submit_application(session, user, application_id, idempotency_key)
    if is_new:
        background.add_task(run_pipeline, application_id)
    else:
        response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/{application_id}/timeline",
    response_model=TimelineOut,
    summary="Таймлайн статуса",
    responses={**R401, **R404},
)
def getApplicationTimeline(application_id: ApplicationId, user: AnyUser, session: DbSession) -> TimelineOut:
    """Этапы с состоянием `done` / `current` / `upcoming`, флагом `actionRequired` и историей переходов."""
    return service.get_timeline(session, user, application_id)


@router.patch(
    "/{application_id}/missing-info",
    response_model=ApplicationOut,
    summary="Дозаполнить запрошенные данные",
    responses={**CLIENT_ERRORS, **R404, **R409},
)
def answerMissingInfo(
    application_id: ApplicationId,
    body: MissingInfoAnswer,
    user: ClientUser,
    session: DbSession,
    background: BackgroundTasks,
) -> ApplicationOut:
    """Принимает только поля из открытого запроса данных (прочие — 422). Запрос становится `ANSWERED`,
    заявка `NEEDS_INFO → CHECKING`, конвейер запускается заново."""
    result = service.answer_missing_info(session, user, application_id, body)
    background.add_task(run_pipeline, application_id)
    return result


@router.post(
    "/{application_id}/offer/accept",
    response_model=AcceptOfferResponse,
    summary="Принять оффер или контроффер",
    responses={**R401, **R403, **R404, **R409},
)
def acceptOffer(application_id: ApplicationId, user: ClientUser, session: DbSession) -> AcceptOfferResponse:
    """`APPROVED` / `COUNTER_OFFER` → `OFFER_ACCEPTED` → `SIGNING`. В ответе подсказка с демо-кодом подписи."""
    return service.accept_offer(session, user, application_id)


@router.post(
    "/{application_id}/offer/decline",
    response_model=ApplicationOut,
    summary="Отказаться от оффера",
    responses={**R401, **R403, **R404, **R409},
)
def declineOffer(application_id: ApplicationId, user: ClientUser, session: DbSession) -> ApplicationOut:
    """`APPROVED` / `COUNTER_OFFER` → `DECLINED_BY_CLIENT`, оффер получает статус `DECLINED`."""
    return service.decline_offer(session, user, application_id)


@router.post(
    "/{application_id}/sign",
    response_model=ApplicationOut,
    summary="Подписать договор кодом (симуляция)",
    responses={**CLIENT_ERRORS, **R404, **R409},
)
def signApplication(
    application_id: ApplicationId, body: SignRequest, user: ClientUser, session: DbSession
) -> ApplicationOut:
    """Код совпал с `DEMO_SIGN_CODE` → `SIGNING → ISSUED`, оффер `SIGNED`. Неверный код — 422 по полю `code`."""
    return service.sign_application(session, user, application_id, body.code)
