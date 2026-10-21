from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    # bcrypt учитывает только первые 72 байта; обрезаем явно, чтобы не падать на длинных паролях
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(claims: dict[str, Any]) -> tuple[str, int]:
    """Возвращает (JWT, время жизни в секундах)."""
    settings = get_settings()
    ttl = timedelta(minutes=settings.jwt_ttl_minutes)
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Бросает jwt.PyJWTError при неверной подписи или истёкшем сроке."""
    return jwt.decode(
        token,
        get_settings().jwt_secret,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
