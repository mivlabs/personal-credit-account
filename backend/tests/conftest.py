"""Тесты идут против настоящего PostgreSQL.

Для каждого прогона пересоздаётся отдельная БД `credit_test` на том же сервере, что и основная (из DATABASE_URL
или TEST_DATABASE_URL): миграции накатываются Alembic, затем идёт настоящий seed. Тесты не очищают таблицы
(аудит неизменяем даже для TRUNCATE), поэтому каждый тест создаёт собственные заявки.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DB_NAME = "credit_test"
DEMO_PASSWORD = "demo1234"


def _prepare_database() -> str:
    base_url = make_url(
        os.environ.get("TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql+psycopg://credit:credit@localhost:5432/credit"
    )
    admin = create_engine(
        base_url.set(database=base_url.database or "postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin.dispose()
    return base_url.set(database=TEST_DB_NAME).render_as_string(hide_password=False)


# Настройки читаются один раз (lru_cache), поэтому окружение готовим до импорта приложения
os.environ["DATABASE_URL"] = _prepare_database()
os.environ["PIPELINE_STEP_DELAY_SECONDS"] = "0"
os.environ["LOG_LEVEL"] = "WARNING"
# Возраст компаний считается от фиксированной даты, чтобы пороги были детерминированы
os.environ["AS_OF_DATE"] = "2026-10-23"
os.environ.setdefault("DEMO_SIGN_CODE", "123456")

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.run import run_seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    with get_sessionmaker()() as session, session.begin():
        run_seed(session)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # BackgroundTasks в TestClient выполняются до возврата ответа: конвейер завершён к моменту проверки
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
        session.rollback()


def login_headers(client: TestClient, login: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"login": login, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture(scope="session")
def fast(client: TestClient) -> dict[str, str]:
    return login_headers(client, "client_fast")


@pytest.fixture(scope="session")
def other_client(client: TestClient) -> dict[str, str]:
    return login_headers(client, "client_counter")


@pytest.fixture(scope="session")
def underwriter(client: TestClient) -> dict[str, str]:
    return login_headers(client, "underwriter")


class Flow:
    """Помощник для сценариев: создаёт и подаёт заявки через API."""

    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client = client
        self.headers = headers

    def draft(self, **fields) -> dict:
        body = {"productCode": "WORKING_CAPITAL", **fields}
        r = self.client.post("/api/v1/applications", json=body, headers=self.headers)
        assert r.status_code == 201, r.text
        return r.json()

    def filled_draft(self, **overrides) -> dict:
        fields = {
            "requestedAmount": 3_000_000,
            "termMonths": 12,
            "purpose": "Пополнение оборотных средств",
            "revenueAmount": 12_000_000,
            "debtAmount": 500_000,
        }
        return self.draft(**{**fields, **overrides})

    def submit(self, application_id: int, key: str | None = None):
        return self.client.post(
            f"/api/v1/applications/{application_id}/submit",
            headers={**self.headers, "Idempotency-Key": key or uuid.uuid4().hex},
        )

    def submitted(self, **overrides) -> dict:
        """Черновик → подача; возвращает заявку после конвейера (MANUAL_REVIEW)."""
        draft = self.filled_draft(**overrides)
        r = self.submit(draft["id"])
        assert r.status_code == 202, r.text
        return self.get(draft["id"])

    def get(self, application_id: int) -> dict:
        r = self.client.get(f"/api/v1/applications/{application_id}", headers=self.headers)
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def flow(client: TestClient, fast: dict[str, str]) -> Flow:
    return Flow(client, fast)


@pytest.fixture(autouse=True)
def legacy_manual_integrations(request, monkeypatch):
    """Existing orchestration tests isolate external checks; live scenarios use WireMock."""
    if request.node.get_closest_marker("live_integrations"):
        return
    from app.integrations.base import NoopExternalChecks

    monkeypatch.setattr(
        "app.domain.pipeline.get_external_checks_client", lambda session=None: NoopExternalChecks()
    )


@pytest.fixture
def external(monkeypatch):
    """Подменяет внешние проверки конвейера фейком: external(payloads, failing=("BKI",))."""
    from tests.fakes import FakeChecks

    def use(payloads, failing=()):
        monkeypatch.setattr(FakeChecks, "payloads", payloads)
        monkeypatch.setattr(FakeChecks, "failing", frozenset(failing))
        monkeypatch.setattr("app.domain.pipeline.get_external_checks_client", FakeChecks)

    return use


@pytest.fixture
def travel(monkeypatch):
    """Сдвигает «сейчас» бизнес-кода вперёд: travel(days=40)."""
    from datetime import timedelta

    from app.core import clock

    real = clock.now

    def go(days: float) -> None:
        monkeypatch.setattr(clock, "now", lambda: real() + timedelta(days=days))

    return go
