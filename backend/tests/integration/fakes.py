"""Фейковые внешние проверки: пишут external_check как настоящий клиент, но без сети."""

import json
from datetime import UTC, datetime

from app.db.models import ExternalCheck
from app.domain.enums import CheckSource, CheckStatus
from app.integrations.base import ExternalData, SourceResult


def egrul(registered="2016-03-14", industry="services"):
    return {"active": True, "registrationDate": registered, "industry": industry}


GOOD = {"EGRUL": egrul(), "FNS": {"annualRevenue": "12000000"}, "BKI": {"debtAmount": "0", "overdueDays": 0}}
# балл 50 (ручная проверка), лимит 0
BORDERLINE = {
    "EGRUL": egrul("2026-01-23", "construction"),
    "FNS": {"annualRevenue": "6000000"},
    "BKI": {"debtAmount": "3000000", "overdueDays": 30},
}
# балл 50 (ручная проверка), лимит 3 млн
BORDERLINE_LIMIT = {
    "EGRUL": egrul("2026-01-23", "other"),
    "FNS": {"annualRevenue": "12000000"},
    "BKI": {"debtAmount": "3000000", "overdueDays": 60},
}


class FakeChecks:
    payloads: dict = GOOD
    # источники, которые отвечают ошибкой (как БКИ 503 у client_timeout)
    failing: frozenset = frozenset()

    def __init__(self, session=None):
        self.session = session

    def fetch_all(self, application_id, company):
        results = {}
        for source in CheckSource:
            now = datetime.now(UTC)
            if source.value in self.failing:
                status, data, stored = CheckStatus.TIMEOUT, None, {"error": "External service unavailable"}
            else:
                status, data = CheckStatus.OK, self.payloads[source.value]
                stored = data
            self.session.add(
                ExternalCheck(
                    application_id=application_id,
                    source_code=source.value,
                    check_status_code=status.value,
                    response_cval=json.dumps(stored),
                    request_dttm=now,
                    response_dttm=now,
                )
            )
            results[source] = SourceResult(source, status, data)
        return ExternalData(results)


def submit(flow, amount=3_000_000, **extra) -> dict:
    draft = flow.draft(**{"requestedAmount": amount, "termMonths": 24, "purpose": "Тест", **extra})
    assert flow.submit(draft["id"]).status_code == 202
    return flow.get(draft["id"])


def screen(client, underwriter, app_id) -> dict:
    return client.get(f"/api/v1/underwriter/applications/{app_id}", headers=underwriter).json()
