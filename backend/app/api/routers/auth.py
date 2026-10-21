from fastapi import APIRouter

from app.api.deps import AnyUser
from app.api.responses import R401, R422
from app.core.errors import NotImplementedProblem
from app.schemas.auth import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Вход по логину и паролю",
    responses={**R401, **R422},
)
def login(body: LoginRequest) -> LoginResponse:
    """Возвращает JWT и данные пользователя. Неверный логин или пароль — 401 `INVALID_CREDENTIALS`."""
    raise NotImplementedProblem()


@router.get(
    "/me",
    response_model=UserOut,
    summary="Текущий пользователь",
    responses={**R401},
)
def getCurrentUser(user: AnyUser) -> UserOut:
    """Данные пользователя, которому принадлежит токен."""
    raise NotImplementedProblem()
