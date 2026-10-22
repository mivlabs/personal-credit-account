from fastapi import APIRouter

from app.api.deps import AnyUser, DbSession
from app.api.responses import R401, R422
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Вход по логину и паролю",
    responses={**R401, **R422},
)
def login(body: LoginRequest, session: DbSession) -> LoginResponse:
    """Возвращает JWT и данные пользователя. Неверный логин или пароль — 401 `INVALID_CREDENTIALS`."""
    return auth_service.login(session, body)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Текущий пользователь",
    responses={**R401},
)
def getCurrentUser(user: AnyUser, session: DbSession) -> UserOut:
    """Данные пользователя, которому принадлежит токен."""
    return auth_service.current_user(session, user)
