from fastapi import APIRouter, Request

from app.api.deps import AnyUser, DbSession
from app.api.responses import R401, R422, R429
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Вход по логину и паролю",
    responses={**R401, **R422, **R429},
)
def login(body: LoginRequest, session: DbSession, request: Request) -> LoginResponse:
    """Возвращает JWT и данные пользователя. Неверный логин или пароль — 401 `INVALID_CREDENTIALS`.

    5 неудачных попыток за 5 минут для связки логин + IP дают 429 `TOO_MANY_REQUESTS` с `Retry-After`."""
    client_ip = request.client.host if request.client else "unknown"
    return auth_service.login(session, body, client_ip)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Текущий пользователь",
    responses={**R401},
)
def getCurrentUser(user: AnyUser, session: DbSession) -> UserOut:
    """Данные пользователя, которому принадлежит токен."""
    return auth_service.current_user(session, user)
