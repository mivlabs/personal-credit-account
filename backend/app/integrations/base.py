"""External check contracts and persisted result loading."""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, ExternalCheck
from app.domain.enums import CheckSource, CheckStatus


@dataclass
class SourceResult:
    source: CheckSource
    status: CheckStatus
    data: dict[str, Any] | None = None


@dataclass
class ExternalData:
    """Ответы внешних сервисов по заявке. Пустой словарь — проверки не выполнялись."""

    results: dict[CheckSource, SourceResult] = field(default_factory=dict)

    @property
    def failed_sources(self) -> list[CheckSource]:
        return [s for s, r in self.results.items() if r.status != CheckStatus.OK]


class ExternalChecksClient(Protocol):
    def fetch_all(self, application_id: int, company: Company) -> ExternalData: ...


class NoopExternalChecks:
    """Заглушка: внешние проверки отключены."""

    enabled = False

    def fetch_all(self, application_id: int, company: Company) -> ExternalData:
        return ExternalData()


def get_external_checks_client(session=None) -> ExternalChecksClient:
    from app.integrations.http import HttpExternalChecks

    return HttpExternalChecks(session)


def load_external_data(session: Session, application_id: int) -> ExternalData:
    """Собирает ответы внешних сервисов из external_check; при ретраях побеждает последняя попытка."""
    rows = session.scalars(
        select(ExternalCheck)
        .where(ExternalCheck.application_id == application_id)
        .order_by(ExternalCheck.check_id)
    ).all()
    data = ExternalData()
    for row in rows:
        source = CheckSource(row.source_code)
        data.results[source] = SourceResult(
            source=source,
            status=CheckStatus(row.check_status_code),
            data=json.loads(row.response_cval) if row.response_cval else None,
        )
    return data
