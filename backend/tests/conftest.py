"""Общее окружение для unit- и integration-тестов (без БД и сети).

`tests/unit` не требует инфраструктуры. `tests/integration` поднимает проверку Postgres и WireMock
в собственном conftest.py. Настройки читаются один раз (lru_cache), поэтому окружение готовим до импорта приложения.
"""

import os
import tempfile

os.environ["PIPELINE_STEP_DELAY_SECONDS"] = "0"
os.environ["LOG_LEVEL"] = "WARNING"
# Возраст компаний считается от фиксированной даты, чтобы пороги были детерминированы
os.environ["AS_OF_DATE"] = "2026-10-23"
os.environ.setdefault("DEMO_SIGN_CODE", "123456")
# Секрет JWT не задан: сервис создаёт случайный и кладёт во временный файл, а не в /app/data
os.environ["JWT_SECRET"] = ""
os.environ["JWT_SECRET_FILE"] = os.path.join(tempfile.mkdtemp(prefix="jwt-"), "jwt_secret")


def _needs_infrastructure(config) -> bool:
    from pathlib import Path

    unit = Path(__file__).parent / "unit"
    targets = [Path(str(a).split("::")[0]).resolve() for a in config.args] or [Path(__file__).parent]
    return any(unit not in (t, *t.parents) for t in targets)


def pytest_configure(config):
    """Перед интеграционной сессией проверяем Postgres и WireMock; `tests/unit` инфраструктуры не требует."""
    import pytest

    if not _needs_infrastructure(config):
        return
    from urllib.request import urlopen

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import OperationalError

    hint = (
        "Как поднять: docker compose -f docker-compose.yml -f docker-compose.override.example.yml up -d db mocks (и DATABASE_URL=postgresql+psycopg://credit:credit@127.0.0.1:5433/credit, "
        "MOCKS_BASE_URL=http://127.0.0.1:8081), либо всё сразу: docker compose --profile test run --rm tests. "
        "Без инфраструктуры работает: uv run pytest tests/unit"
    )
    mocks = os.environ.get("MOCKS_BASE_URL", "http://localhost:8081").rstrip("/")
    try:
        with urlopen(f"{mocks}/__admin/health", timeout=3) as response:
            if response.status != 200:
                raise OSError(f"HTTP {response.status}")
    except (OSError, ValueError) as exc:
        pytest.exit(f"WireMock недоступен по {mocks}/__admin/health ({exc}). {hint}", returncode=2)
    url = make_url(
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql+psycopg://credit:credit@localhost:5432/credit"
    )
    try:
        with create_engine(url.set(database="postgres"), connect_args={"connect_timeout": 3}).connect():
            pass
    except OperationalError as exc:
        reason = str(exc.orig).splitlines()[0] if exc.orig else "ошибка подключения"
        pytest.exit(f"PostgreSQL недоступен ({reason}). {hint}", returncode=2)
