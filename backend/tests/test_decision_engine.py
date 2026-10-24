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
