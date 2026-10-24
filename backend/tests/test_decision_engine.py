from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.domain.decision.config import load_decision_config
from app.domain.decision.engine import DecisionInput, apply_policy, evaluate
from app.domain.enums import DecisionOutcome as O

BASE = DecisionInput(
    True, 120, D("12000000"), D("0"), 0, "services", D("1500000"), D("300000"), D("10000000")
)


@pytest.mark.parametrize(
    ("score", "outcome"), [(39, O.REJECTED), (40, O.MANUAL_REVIEW), (69, O.MANUAL_REVIEW), (70, O.APPROVED)]
)
def test_policy_boundaries(score, outcome):
    assert apply_policy(score, D("1000000"), D("6000000"), D("300000"), load_decision_config())[0] == outcome


@pytest.mark.parametrize(
    ("changes", "outcome"),
    [
        ({}, O.APPROVED),
        ({"requested": D("10000000")}, O.COUNTER_OFFER),
        (
            {
                "age_months": 9,
                "revenue": D("6000000"),
                "debt": D("3000000"),
                "overdue_days": 30,
                "industry": "construction",
            },
            O.MANUAL_REVIEW,
        ),
        ({"revenue": None}, O.NEEDS_INFO),
        ({"overdue_days": 120}, O.REJECTED),
    ],
)
def test_five_outcomes(changes, outcome):
    r = evaluate(replace(BASE, **changes), load_decision_config())
    assert r.outcome == outcome and r.rule_code
    if r.score is not None:
        assert sum(f.points for f in r.factors) == r.score


@pytest.mark.parametrize("changes", [{"active": False}, {"age_months": 5}, {"overdue_days": 91}])
def test_stop_precedes_missing_data_and_outage(changes):
    r = evaluate(replace(BASE, revenue=None, failed_sources=("FNS",), **changes), load_decision_config())
    assert r.outcome == O.REJECTED and r.score is None


def test_missing_is_not_zero_and_zero_revenue_does_not_crash():
    c = load_decision_config()
    assert evaluate(replace(BASE, revenue=None), c).outcome == O.NEEDS_INFO
    r = evaluate(replace(BASE, revenue=D(0), debt=D(100)), c)
    assert r.outcome == O.MANUAL_REVIEW and r.limit == D(0)


def test_limit_and_minimum():
    c = load_decision_config()
    r = evaluate(replace(BASE, requested=D("10000000")), c)
    assert r.offer_amt == D("6000000.00")
    r = evaluate(replace(BASE, revenue=D("500000"), debt=D(0)), c)
    assert r.outcome == O.REJECTED and r.rule_code == "LIMIT_BELOW_MINIMUM"


def test_configuration_rejects_invalid_thresholds_and_bands():
    c = load_decision_config()
    with pytest.raises(ValueError):
        type(c).model_validate({**c.model_dump(), "reject_threshold": 80})
    with pytest.raises(ValueError):
        type(c).model_validate({**c.model_dump(), "age_bands": [(24, 20), (12, 15)]})


def test_age_is_counted_from_as_of_date_not_policy_snapshot(monkeypatch):
    from datetime import date
    from types import SimpleNamespace

    from app.core.config import get_settings
    from app.domain.clock import age_in_months, as_of_date
    from app.domain.decision.engine import decide
    from app.domain.enums import CheckSource, CheckStatus
    from app.integrations.base import ExternalData, SourceResult

    assert age_in_months(date(2026, 1, 23), date(2026, 10, 22)) == 8
    assert age_in_months(date(2026, 1, 23), date(2026, 10, 23)) == 9

    def run(as_of_env):
        monkeypatch.setenv("AS_OF_DATE", as_of_env)
        get_settings.cache_clear()
        data = ExternalData(
            {
                CheckSource.EGRUL: SourceResult(
                    CheckSource.EGRUL,
                    CheckStatus.OK,
                    {"active": True, "registrationDate": "2026-05-01", "industry": "services"},
                ),
                CheckSource.FNS: SourceResult(CheckSource.FNS, CheckStatus.OK, {"annualRevenue": "12000000"}),
                CheckSource.BKI: SourceResult(
                    CheckSource.BKI, CheckStatus.OK, {"debtAmount": "0", "overdueDays": 0}
                ),
            }
        )
        app = SimpleNamespace(
            revenue_amt=None,
            debt_amt=None,
            requested_amt=D("1000000"),
            product=SimpleNamespace(min_amt=D("300000"), max_amt=D("10000000")),
        )
        return decide(app, data, load_decision_config())

    try:
        # 2026-05-01 → на 2026-10-23 полных 5 месяцев (моложе 6): стоп-фактор; на 2026-11-02 уже 6
        assert run("2026-10-23").rule_code == "YOUNG_COMPANY"
        assert run("2026-11-02").rule_code != "YOUNG_COMPANY"
    finally:
        monkeypatch.setenv("AS_OF_DATE", "2026-10-23")
        get_settings.cache_clear()
    assert as_of_date() == date(2026, 10, 23)


def test_as_of_date_defaults_to_moscow_today(monkeypatch):
    from datetime import datetime

    from app.core.config import get_settings
    from app.domain.clock import MOSCOW, as_of_date

    monkeypatch.delenv("AS_OF_DATE")
    get_settings.cache_clear()
    try:
        assert as_of_date() == datetime.now(MOSCOW).date()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_engine_mismatch_threshold_and_declared_factor():
    c = load_decision_config()
    base = replace(BASE, revenue_source=D("12000000"), debt_source=D("0"))
    # ровно 20% — ещё не расхождение, строго больше — расхождение
    assert evaluate(replace(base, revenue_client=D("14400000")), c).rule_code == "WITHIN_LIMIT"
    r = evaluate(replace(base, revenue_client=D("14400001")), c)
    assert r.outcome == O.MANUAL_REVIEW and r.rule_code == "DATA_MISMATCH"
    assert [f.code for f in r.factors] == ["DATA_MISMATCH"] and r.score is None
    # источник с нулём: любое ненулевое значение клиента — расхождение
    zero = replace(base, debt_source=D("0"), debt_client=D("1"))
    assert evaluate(zero, c).rule_code == "DATA_MISMATCH"
    declared = evaluate(replace(BASE, revenue_declared_only=True), c)
    assert declared.limit == D("3000000.00")
