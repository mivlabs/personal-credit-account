"""Bounded local HTTP integrations; each attempt is persisted in the caller's transaction."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.db.models import ExternalCheck
from app.domain.enums import CheckSource, CheckStatus
from app.integrations.base import ExternalData, SourceResult


class EgrulPayload(BaseModel):
    active: bool
    registrationDate: date
    industry: str
    name: str | None = None
    ogrn: str | None = None
    legalAddress: str | None = None


class FnsPayload(BaseModel):
    annualRevenue: Decimal | None = Field(default=None, ge=0)


class BkiPayload(BaseModel):
    debtAmount: Decimal | None = Field(default=None, ge=0)
    overdueDays: int = Field(ge=0)


MAX_ATTEMPTS = 3
ATTEMPT_TIMEOUT = 0.8

PAYLOADS = {CheckSource.EGRUL: EgrulPayload, CheckSource.FNS: FnsPayload, CheckSource.BKI: BkiPayload}


@dataclass
class _Attempt:
    status: CheckStatus
    payload: dict | None
    started: datetime
    finished: datetime


class HttpExternalChecks:
    """Три источника опрашиваются параллельно в потоках, общий бюджет времени ограничивает и ретраи.

    Потоки только ходят по HTTP и возвращают результаты; записи external_check создаются потом
    в основной сессии вызывающего (сессия SQLAlchemy между потоками не передаётся).
    """

    def __init__(self, session=None):
        self.session = session
        settings = get_settings()
        self.base_url = settings.mocks_base_url.rstrip("/")
        self.budget = settings.external_checks_budget_seconds

    def _call(self, source: CheckSource, inn: str, deadline: float) -> list[_Attempt]:
        attempts: list[_Attempt] = []
        for attempt in range(MAX_ATTEMPTS):
            remaining = deadline - time.monotonic()
            if attempts and remaining <= 0.05:
                break
            timeout = min(ATTEMPT_TIMEOUT, max(remaining, 0.05))
            started = datetime.now(UTC)
            retry = False
            status, payload = CheckStatus.OK, None
            try:
                request = Request(
                    f"{self.base_url}/{source.value.lower()}/{inn}", headers={"Accept": "application/json"}
                )
                with urlopen(request, timeout=timeout) as response:
                    raw = response.read(65537)
                    if len(raw) > 65536:
                        raise ValueError("Response exceeds limit")
                    payload = PAYLOADS[source].model_validate(json.loads(raw)).model_dump(mode="json")
            except HTTPError as exc:
                status, retry = CheckStatus.ERROR, exc.code >= 500
                payload = {"error": f"HTTP {exc.code}"}
            except (URLError, TimeoutError, OSError, HTTPException):
                status, retry = CheckStatus.TIMEOUT, True
                payload = {"error": "External service unavailable"}
            except (ValueError, ValidationError):
                status = CheckStatus.ERROR
                payload = {"error": "Invalid external response"}
            attempts.append(_Attempt(status, payload, started, datetime.now(UTC)))
            if status == CheckStatus.OK or not retry or attempt == MAX_ATTEMPTS - 1:
                break
        return attempts

    def _record(
        self, source: CheckSource, application_id: int | None, attempts: list[_Attempt]
    ) -> SourceResult:
        if self.session is not None and application_id is not None:
            for a in attempts:
                self.session.add(
                    ExternalCheck(
                        application_id=application_id,
                        source_code=source.value,
                        check_status_code=a.status.value,
                        response_cval=json.dumps(a.payload, ensure_ascii=False),
                        request_dttm=a.started,
                        response_dttm=a.finished,
                    )
                )
        last = attempts[-1]
        return SourceResult(source, last.status, last.payload if last.status == CheckStatus.OK else None)

    def fetch(self, source: CheckSource, inn: str, application_id: int | None = None) -> SourceResult:
        attempts = self._call(source, inn, time.monotonic() + self.budget)
        return self._record(source, application_id, attempts)

    def fetch_all(self, application_id, company) -> ExternalData:
        deadline = time.monotonic() + self.budget
        sources = list(CheckSource)
        with ThreadPoolExecutor(max_workers=len(sources)) as pool:
            futures = {s: pool.submit(self._call, s, company.inn_code, deadline) for s in sources}
            attempts = {s: f.result() for s, f in futures.items()}
        return ExternalData({s: self._record(s, application_id, attempts[s]) for s in sources})
