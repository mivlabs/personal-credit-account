from app.domain.decision.config import load_decision_config
from app.domain.pricing import compute_rate, rate_from
from tests.integration.conftest import Flow

PRODUCTS = ["WORKING_CAPITAL", "EQUIPMENT", "OVERDRAFT"]


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
