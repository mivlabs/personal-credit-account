from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError

import pytest

from app.domain.enums import CheckSource, CheckStatus
from app.integrations.http import HttpExternalChecks


@pytest.mark.parametrize(
    ("error", "expected", "attempts"),
    [
        (URLError("offline"), CheckStatus.TIMEOUT, 3),
        (TimeoutError(), CheckStatus.TIMEOUT, 3),
        (RemoteDisconnected(), CheckStatus.TIMEOUT, 3),
        (HTTPError("http://local", 503, "unavailable", {}, None), CheckStatus.ERROR, 3),
        (HTTPError("http://local", 404, "missing", {}, None), CheckStatus.ERROR, 1),
    ],
)
def test_http_retry_budget_and_business_errors(monkeypatch, error, expected, attempts):
    calls = []

    def fail(request, timeout):
        calls.append((request.full_url, timeout))
        raise error

    monkeypatch.setattr("app.integrations.http.urlopen", fail)
    result = HttpExternalChecks().fetch(CheckSource.BKI, "7701000006")
    assert result.status == expected and result.data is None
    assert len(calls) == attempts and all(timeout == 0.8 for _, timeout in calls)
