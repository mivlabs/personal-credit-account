import logging
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
DEMO_JWT_SECRET = "change-me-in-production-please-32+chars"
MIN_SECRET_LENGTH = 32
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


@lru_cache
def get_jwt_secret() -> str:
    """Секрет подписи JWT. Слабый или демо-секрет заменяется случайным, сохранённым в файле на volume."""
    settings = get_settings()
    configured = settings.jwt_secret
    if configured and configured != DEMO_JWT_SECRET and len(configured) >= MIN_SECRET_LENGTH:
        return configured
    path = Path(settings.jwt_secret_file)
    try:
        stored = path.read_text(encoding="ascii").strip()
        if len(stored) >= MIN_SECRET_LENGTH:
            logger.warning("JWT_SECRET не задан или слаб: используется секрет из файла %s", path)
            return stored
    except OSError:
        pass
    secret = secrets.token_urlsafe(48)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secret, encoding="ascii")
        path.chmod(0o600)
        logger.warning("JWT_SECRET не задан или слаб: создан случайный секрет и сохранён в %s", path)
    except OSError:
        logger.warning(
            "JWT_SECRET не задан или слаб: создан случайный секрет только в памяти (файл %s недоступен), "
            "токены перестанут действовать после перезапуска",
            path,
        )
    return secret


def create_access_token(claims: dict[str, Any]) -> tuple[str, int]:
    """Возвращает (JWT, время жизни в секундах)."""
    settings = get_settings()
    ttl = timedelta(minutes=settings.jwt_ttl_minutes)
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Бросает jwt.PyJWTError при неверной подписи или истёкшем сроке."""
    return jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
