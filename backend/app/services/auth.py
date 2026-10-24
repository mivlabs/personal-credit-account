import math
import threading
import time
from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core.config import get_settings
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import AppUser
from app.domain.enums import ErrorCode
from app.schemas.auth import LoginRequest, LoginResponse, UserOut

# Хэш-пустышка: проверяем пароль даже для несуществующего логина, чтобы время ответа не выдавало, есть ли такой логин
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def user_out(u: AppUser) -> UserOut:
    return UserOut(id=u.user_id, name=u.user_name, role=u.role_code, company_id=u.company_id)


# Ограничение одного процесса: счётчики неудачных попыток живут в памяти (логин + IP)
_failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_failures_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def reset_login_limiter() -> None:
    with _failures_lock:
        _failures.clear()


def _check_not_blocked(key: tuple[str, str]) -> None:
    settings = get_settings()
    with _failures_lock:
        attempts = _failures.get(key)
        if not attempts:
            return
        now = _now()
        while attempts and now - attempts[0] >= settings.login_window_seconds:
            attempts.popleft()
        if not attempts:
            del _failures[key]
        elif len(attempts) >= settings.login_max_failures:
            retry_after = max(1, math.ceil(settings.login_window_seconds - (now - attempts[0])))
            raise TooManyRequestsError(
                "Слишком много неудачных попыток входа, повторите позже", retry_after=retry_after
            )


def _register_failure(key: tuple[str, str]) -> None:
    with _failures_lock:
        _failures[key].append(_now())


def login(session: Session, body: LoginRequest, client_ip: str = "unknown") -> LoginResponse:
    key = (body.login, client_ip)
    _check_not_blocked(key)
    user = session.scalar(select(AppUser).where(AppUser.login_code == body.login))
    password_ok = verify_password(body.password, user.password_hash_cval if user else _DUMMY_HASH)
    if user is None or not password_ok:
        _register_failure(key)
        raise UnauthorizedError("Неверный логин или пароль", code=ErrorCode.INVALID_CREDENTIALS)

    with _failures_lock:
        _failures.pop(key, None)
    token, ttl = create_access_token(
        {
            "sub": str(user.user_id),
            "role": user.role_code,
            "companyId": user.company_id,
            "name": user.user_name,
        }
    )
    return LoginResponse(access_token=token, token_type="Bearer", expires_in=ttl, user=user_out(user))


def current_user(session: Session, auth: AuthUser) -> UserOut:
    user = session.get(AppUser, auth.id)
    if user is None:
        raise UnauthorizedError("Пользователь не найден, войдите снова")
    return user_out(user)
