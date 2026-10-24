"""Bounded local HTTP integrations; each attempt is persisted in the caller's transaction."""

import json
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


PAYLOADS = {CheckSource.EGRUL: EgrulPayload, CheckSource.FNS: FnsPayload, CheckSource.BKI: BkiPayload}


class HttpExternalChecks:
    def __init__(self, session=None):
        self.session = session
        self.base_url = get_settings().mocks_base_url.rstrip("/")

    def fetch(self, source: CheckSource, inn: str, application_id: int | None = None) -> SourceResult:
        for attempt in range(3):
            started = datetime.now(UTC)
            retry = False
            status, payload = CheckStatus.OK, None
            try:
                request = Request(
                    f"{self.base_url}/{source.value.lower()}/{inn}", headers={"Accept": "application/json"}
                )
                with urlopen(request, timeout=0.8) as response:
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
            if self.session is not None and application_id is not None:
                self.session.add(
                    ExternalCheck(
                        application_id=application_id,
                        source_code=source.value,
                        check_status_code=status.value,
                        response_cval=json.dumps(payload, ensure_ascii=False),
                        request_dttm=started,
                        response_dttm=datetime.now(UTC),
                    )
                )
            result = SourceResult(source, status, payload if status == CheckStatus.OK else None)
            if status == CheckStatus.OK or not retry or attempt == 2:
                return result
        raise AssertionError("unreachable")

    def fetch_all(self, application_id, company) -> ExternalData:
        return ExternalData(
            {source: self.fetch(source, company.inn_code, application_id) for source in CheckSource}
        )
