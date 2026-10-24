import pytest

from app.domain.enums import CheckSource, CheckStatus
from app.integrations.http import HttpExternalChecks


@pytest.mark.live_integrations
def test_slow_source_is_timeout_within_budget():
    """Медленный БКИ (стаб 7701000099, задержка 2 с) не растягивает опрос за бюджет; остальные источники OK."""
    import time
    from types import SimpleNamespace

    from app.core.config import get_settings

    budget = get_settings().external_checks_budget_seconds
    started = time.monotonic()
    data = HttpExternalChecks().fetch_all(1, SimpleNamespace(inn_code="7701000099"))
    elapsed = time.monotonic() - started
    assert elapsed <= budget + 0.5
    assert data.results[CheckSource.BKI].status == CheckStatus.TIMEOUT
    assert data.results[CheckSource.EGRUL].status == CheckStatus.OK
    assert data.results[CheckSource.FNS].status == CheckStatus.OK
