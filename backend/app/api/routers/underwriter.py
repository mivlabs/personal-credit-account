from typing import Annotated

from fastapi import APIRouter, Body, Path, Query

from app.api.deps import UnderwriterUser
from app.api.responses import R401, R403, R404, R409, R422
from app.core.errors import NotImplementedProblem
from app.schemas.application import ApplicationOut
from app.schemas.underwriter import (
    DECISION_REQUEST_EXAMPLES,
    AuditEntryOut,
    DecisionRequest,
    QueueOut,
    UnderwriterApplicationOut,
)

router = APIRouter(prefix="/underwriter", tags=["underwriter"])
# Аудит лежит под /applications, но относится к панели банка
audit_router = APIRouter(prefix="/applications", tags=["underwriter"])

ApplicationId = Annotated[int, Path(ge=1, description="Идентификатор заявки")]


@audit_router.get(
    "/{application_id}/audit",
    response_model=list[AuditEntryOut],
    summary="Аудит заявки",
    responses={**R401, **R403, **R404},
)
def getApplicationAudit(application_id: ApplicationId, user: UnderwriterUser) -> list[AuditEntryOut]:
    """Все переходы статуса: кто, когда, из какого статуса в какой, комментарий. От старых к новым."""
    raise NotImplementedProblem()


@router.get(
    "/queue",
    response_model=QueueOut,
    summary="Очередь ручной проверки",
    responses={**R401, **R403, **R422},
)
def getUnderwriterQueue(
    user: UnderwriterUser,
    limit: Annotated[int, Query(ge=1, le=100, description="Размер страницы")] = 20,
    offset: Annotated[int, Query(ge=0, description="Сколько записей пропустить")] = 0,
) -> QueueOut:
    """Заявки в статусе `MANUAL_REVIEW`, по времени ожидания: самые старые сверху."""
    raise NotImplementedProblem()


@router.get(
    "/applications/{application_id}",
    response_model=UnderwriterApplicationOut,
    summary="Заявка для андеррайтера",
    responses={**R401, **R403, **R404},
)
def getUnderwriterApplication(
    application_id: ApplicationId, user: UnderwriterUser
) -> UnderwriterApplicationOut:
    """Анкета, профиль компании, ответы ЕГРЮЛ / ФНС / БКИ, балл и все факторы, история решений: на одном экране."""
    raise NotImplementedProblem()


@router.post(
    "/applications/{application_id}/decision",
    response_model=ApplicationOut,
    summary="Принять ручное решение",
    responses={**R401, **R403, **R404, **R409, **R422},
)
def makeUnderwriterDecision(
    application_id: ApplicationId,
    body: Annotated[DecisionRequest, Body(openapi_examples=DECISION_REQUEST_EXAMPLES)],
    user: UnderwriterUser,
) -> ApplicationOut:
    """Исходы: `APPROVED`, `COUNTER_OFFER`, `NEEDS_INFO`, `REJECTED`. Комментарий обязателен (иначе 422);
    для `COUNTER_OFFER` обязателен `offerAmount`, для `NEEDS_INFO` — `infoRequest`.
    Допустимо только для заявок в `MANUAL_REVIEW`, иначе 409 `INVALID_TRANSITION`."""
    raise NotImplementedProblem()
