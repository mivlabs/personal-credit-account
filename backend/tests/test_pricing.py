from datetime import date
from decimal import Decimal as D

import pytest

from app.core.config import get_settings
from app.domain.decision.config import load_decision_config
from app.domain.pricing import compute_rate, rate_from
from tests.conftest import Flow

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
    assert c.key_rate_pct == D("14.0") and c.key_rate_date == date(2026, 9, 11)
    assert "Банк России" in c.key_rate_source


def test_catalog_shows_rate_from_with_breakdown(client, fast):
    products = client.get("/api/v1/products", headers=fast).json()
    c = load_decision_config()
    assert {p["code"] for p in products} == set(PRODUCTS)
    for p in products:
        expected = rate_from(p["code"], c)
        assert p["rateFrom"] == p["rate"] == float(expected.total)
        assert p["rateBreakdown"]["keyRate"] == float(c.key_rate_pct)
        assert p["rateBreakdown"]["riskSurcharge"] == 0


def test_manual_offer_rate_matches_policy_and_catalog(client, fast, underwriter, flow: Flow):
    app = flow.submitted()
    r = client.post(
        f"/api/v1/underwriter/applications/{app['id']}/decision",
        headers=underwriter,
        json={"outcome": "APPROVED", "comment": "ок"},
    )
    assert r.status_code == 200, r.text
    offer = r.json()["offer"]
    c = load_decision_config()
    # без балла надбавка применяется, как у автоматического решения с баллом ниже порога
    auto_like = compute_rate("WORKING_CAPITAL", c.low_risk_threshold - 1, c)
    assert offer["rate"] == float(auto_like.total)
    b = offer["rateBreakdown"]
    assert b["total"] == b["keyRate"] + b["productSpread"] + b["riskSurcharge"]
    catalog = next(
        p for p in client.get("/api/v1/products", headers=fast).json() if p["code"] == "WORKING_CAPITAL"
    )
    assert offer["rate"] == catalog["rateFrom"] + float(c.risk_surcharge_pct)


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
