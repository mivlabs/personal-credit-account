from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.domain.enums import UserRole

bearer_scheme = HTTPBearer(
    scheme_name="bearerAuth",
    bearerFormat="JWT",
    auto_error=False,
    description="JWT из `POST /auth/login`: `Authorization: Bearer <token>`",
)


@dataclass(frozen=True)
class AuthUser:
    """Пользователь из claims токена (без обращения к БД на каждый запрос)."""

    id: int
    name: str
    role: UserRole
    company_id: int | None


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Войдите в кабинет, чтобы продолжить")
    try:
        claims = decode_access_token(credentials.credentials)
        return AuthUser(
            id=int(claims["sub"]),
            name=str(claims.get("name", "")),
            role=UserRole(claims["role"]),
            company_id=claims.get("companyId"),
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise UnauthorizedError("Сессия недействительна или истекла, войдите снова") from exc


def require_client(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if user.role != UserRole.CLIENT or user.company_id is None:
        raise ForbiddenError("Действие доступно только клиенту")
    return user


def require_underwriter(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if user.role != UserRole.UNDERWRITER:
        raise ForbiddenError("Действие доступно только андеррайтеру")
    return user


DbSession = Annotated[Session, Depends(get_db)]
AnyUser = Annotated[AuthUser, Depends(get_current_user)]
ClientUser = Annotated[AuthUser, Depends(require_client)]
UnderwriterUser = Annotated[AuthUser, Depends(require_underwriter)]
