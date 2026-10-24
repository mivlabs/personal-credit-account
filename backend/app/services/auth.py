import math
import re
import threading
import time
from collections import defaultdict, deque
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core.config import get_settings
from app.core.errors import (
    EgrulUnavailableError,
    InnTakenError,
    LoginTakenError,
    TooManyRequestsError,
    UnauthorizedError,
    ValidationProblem,
    field_error,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import AppUser, Company
from app.domain.enums import CheckSource, CheckStatus, ErrorCode, LegalForm, UserRole
from app.domain.inn import validate_inn
from app.integrations.http import HttpExternalChecks
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserOut

LOGIN_PATTERN = re.compile(r"[a-z0-9_.-]{3,32}")
MIN_PASSWORD_LENGTH = 8

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


LOGIN_BLOCKED = "Слишком много неудачных попыток входа, повторите позже"
REGISTER_BLOCKED = "Слишком много попыток регистрации, повторите позже"


def _check_not_blocked(key: tuple[str, str], max_attempts: int, message: str) -> None:
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
        elif len(attempts) >= max_attempts:
            retry_after = max(1, math.ceil(settings.login_window_seconds - (now - attempts[0])))
            raise TooManyRequestsError(message, retry_after=retry_after)


def _register_failure(key: tuple[str, str]) -> None:
    with _failures_lock:
        _failures[key].append(_now())


def login(session: Session, body: LoginRequest, client_ip: str = "unknown") -> LoginResponse:
    key = (body.login, client_ip)
    _check_not_blocked(key, get_settings().login_max_failures, LOGIN_BLOCKED)
    user = session.scalar(select(AppUser).where(AppUser.login_code == body.login))
    password_ok = verify_password(body.password, user.password_hash_cval if user else _DUMMY_HASH)
    if user is None or not password_ok:
        _register_failure(key)
        raise UnauthorizedError("Неверный логин или пароль", code=ErrorCode.INVALID_CREDENTIALS)

    with _failures_lock:
        _failures.pop(key, None)
    return _issue_token(user)


def _issue_token(user: AppUser) -> LoginResponse:
    token, ttl = create_access_token(
        {
            "sub": str(user.user_id),
            "role": user.role_code,
            "companyId": user.company_id,
            "name": user.user_name,
        }
    )
    return LoginResponse(access_token=token, token_type="Bearer", expires_in=ttl, user=user_out(user))


def _validate_registration(body: RegisterRequest) -> None:
    errors = []
    if not LOGIN_PATTERN.fullmatch(body.login):
        errors.append(
            field_error("login", "Логин: 3–32 символа, только a-z, 0-9, «_», «.», «-»", "login_format")
        )
    if len(body.password) < MIN_PASSWORD_LENGTH:
        errors.append(
            field_error("password", f"Пароль не короче {MIN_PASSWORD_LENGTH} символов", "password_too_short")
        )
    check = validate_inn(body.inn)
    if not check.valid:
        errors.append(field_error("inn", check.message, f"inn_{check.problem.value.lower()}"))
    if errors:
        raise ValidationProblem("Запрос не прошёл проверку: исправьте отмеченные поля", errors=errors)


def register(session: Session, body: RegisterRequest, client_ip: str = "unknown") -> LoginResponse:
    """Создаёт компанию по данным ЕГРЮЛ и клиента-пользователя; возвращает то же, что вход."""
    key = ("register", client_ip)
    _check_not_blocked(key, get_settings().register_max_attempts, REGISTER_BLOCKED)
    _register_failure(key)  # считаем каждую попытку: регистрация пишет в БД, в отличие от входа

    _validate_registration(body)
    if session.scalar(select(AppUser.user_id).where(AppUser.login_code == body.login)) is not None:
        raise LoginTakenError(
            "Логин уже занят, выберите другой", errors=[field_error("login", "Логин занят")]
        )
    if session.scalar(select(Company.company_id).where(Company.inn_code == body.inn)) is not None:
        raise InnTakenError(
            "Этот ИНН уже привязан к кабинету компании",
            errors=[field_error("inn", "ИНН уже зарегистрирован")],
        )

    result = HttpExternalChecks().fetch(CheckSource.EGRUL, body.inn)
    if result.status != CheckStatus.OK:
        raise EgrulUnavailableError("ЕГРЮЛ временно недоступен. Повторите регистрацию позже")
    data = result.data
    form = LegalForm.IP if len(body.inn) == 12 else LegalForm.OOO
    prefix = "ИП" if form == LegalForm.IP else "ООО"
    company = Company(
        inn_code=body.inn,
        ogrn_code=data.get("ogrn"),
        # ЕГРЮЛ может не прислать наименование: колонка обязательна, подставляем форму и ИНН
        company_name=data.get("name") or f"{prefix} {body.inn}",
        legal_form_code=form.value,
        registration_dt=date.fromisoformat(data["registrationDate"]),
        legal_address_desc=data.get("legalAddress"),
    )
    user = AppUser(
        role_code=UserRole.CLIENT.value,
        login_code=body.login,
        password_hash_cval=hash_password(body.password),
        user_name=company.company_name,
    )
    try:
        session.add(company)
        session.flush()
        user.company_id = company.company_id
        session.add(user)
        session.commit()
    except IntegrityError as exc:
        # Гонка двух регистраций: уникальные индексы остаются последним рубежом
        session.rollback()
        if "inn_code" in str(exc.orig):
            raise InnTakenError(
                "Этот ИНН уже привязан к кабинету компании",
                errors=[field_error("inn", "ИНН уже зарегистрирован")],
            ) from exc
        raise LoginTakenError(
            "Логин уже занят, выберите другой", errors=[field_error("login", "Логин занят")]
        ) from exc
    return _issue_token(user)


def current_user(session: Session, auth: AuthUser) -> UserOut:
    user = session.get(AppUser, auth.id)
    if user is None:
        raise UnauthorizedError("Пользователь не найден, войдите снова")
    return user_out(user)
