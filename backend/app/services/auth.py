from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import AppUser
from app.domain.enums import ErrorCode
from app.schemas.auth import LoginRequest, LoginResponse, UserOut

# Хэш-пустышка: проверяем пароль даже для несуществующего логина, чтобы время ответа не выдавало, есть ли такой логин
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def user_out(u: AppUser) -> UserOut:
    return UserOut(id=u.user_id, name=u.user_name, role=u.role_code, company_id=u.company_id)


def login(session: Session, body: LoginRequest) -> LoginResponse:
    user = session.scalar(select(AppUser).where(AppUser.login_code == body.login))
    password_ok = verify_password(body.password, user.password_hash_cval if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise UnauthorizedError("Неверный логин или пароль", code=ErrorCode.INVALID_CREDENTIALS)

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
