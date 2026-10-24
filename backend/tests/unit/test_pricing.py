from datetime import date
from decimal import Decimal as D

import pytest

from app.core.config import get_settings
from app.domain.decision.config import load_decision_config
from app.domain.pricing import compute_rate, rate_from

PRODUCTS = ["WORKING_CAPITAL", "EQUIPMENT", "OVERDRAFT"]


@pytest.mark.parametrize("product", PRODUCTS)
@pytest.mark.parametrize("score", [None, 40, 84, 85, 100])
def test_total_is_key_plus_spread_plus_surcharge(product, score):
    c = load_decision_config()
    b = compute_rate(product, score, c)
    assert b.total == b.key_rate + b.product_spread + b.risk_surcharge
    assert b.key_rate == c.key_rate_pct and b.product_spread == c.product_spreads[product]
    expected = c.risk_surcharge_pct if score is None or score < c.low_risk_threshold else D(0)
    assert b.risk_surcharge == expected


def test_rate_from_has_no_surcharge():
    c = load_decision_config()
    for product in PRODUCTS:
        assert rate_from(product, c).total == c.key_rate_pct + c.product_spreads[product]


def test_key_rate_is_cbr_not_demo():
    c = load_decision_config()
    assert c.key_rate_pct == D("14.0") and c.key_rate_date == date(2026, 10, 23)
    assert "Банк России" in c.key_rate_source


def test_env_override_of_key_rate(monkeypatch):
    monkeypatch.setenv("KEY_RATE_PCT", "18.5")
    monkeypatch.setenv("KEY_RATE_DATE", "2026-10-30")
    get_settings.cache_clear()
    load_decision_config.cache_clear()
    try:
        c = load_decision_config()
        assert c.key_rate_pct == D("18.5") and c.key_rate_date == date(2026, 10, 30)
        assert compute_rate("EQUIPMENT", 90, c).total == D("19.4")
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        load_decision_config.cache_clear()
    assert load_decision_config().key_rate_pct == D("14.0")
