"""Подбор продукта по цели (US-10): детерминированные правила из recommendation.yaml."""

import pytest

from app.domain.enums import PurposeCategory
from app.domain.recommendation import load_recommendation_config

URL = "/api/v1/products/recommendations"


def recommend(client, headers, **body):
    r = client.post(URL, headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize(
    ("purpose", "expected"),
    [
        ("WORKING_CAPITAL_TOPUP", "WORKING_CAPITAL"),
        ("GOODS_PURCHASE", "WORKING_CAPITAL"),
        ("EQUIPMENT_PURCHASE", "EQUIPMENT"),
        ("CASH_GAP", "OVERDRAFT"),
        ("SEASONAL", "WORKING_CAPITAL"),
        ("EXPANSION", "EQUIPMENT"),
        ("OTHER", "WORKING_CAPITAL"),
    ],
)
def test_each_purpose_recommends_expected_product(client, fast, purpose, expected):
    body = recommend(client, fast, purposeCategory=purpose)
    items = body["items"]
    assert [i["product"]["code"] for i in items][0] == expected
    assert items[0]["recommended"] is True
    assert sum(i["recommended"] for i in items) == 1
    scores = [i["matchScore"] for i in items]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 100 for s in scores)
    assert all(i["reasons"] for i in items)
    assert body["rulesVersion"] and body["purposeLabel"]


def test_rate_from_matches_catalog(client, fast):
    catalog = {p["code"]: p["rateFrom"] for p in client.get("/api/v1/products", headers=fast).json()}
    for item in recommend(client, fast, purposeCategory="OTHER")["items"]:
        assert item["rateFrom"] == catalog[item["product"]["code"]] == item["product"]["rateFrom"]


def test_amount_above_max_is_penalised_and_explained(client, fast):
    items = recommend(client, fast, purposeCategory="WORKING_CAPITAL_TOPUP", amount=40_000_000)["items"]
    wc = next(i for i in items if i["product"]["code"] == "WORKING_CAPITAL")
    assert wc["matchScore"] == 50 and wc["recommended"] is False
    assert any("выше максимума" in r and "40 млн" in r for r in wc["reasons"])
    assert not any(i["recommended"] for i in items)  # лучший продукт вне диапазона не рекомендуется


def test_amount_below_min(client, fast):
    items = recommend(client, fast, purposeCategory="EQUIPMENT_PURCHASE", amount=100_000)["items"]
    eq = next(i for i in items if i["product"]["code"] == "EQUIPMENT")
    assert eq["matchScore"] == 75 and any("ниже минимума" in r for r in eq["reasons"])
    assert eq["recommended"] is False


def test_term_in_range_is_explained(client, fast):
    items = recommend(client, fast, purposeCategory="CASH_GAP", amount=1_000_000, termMonths=6)["items"]
    od = items[0]
    assert od["product"]["code"] == "OVERDRAFT" and od["recommended"] is True
    assert any("срок 6 мес. подходит" in r for r in od["reasons"])
    assert any("входит в диапазон" in r for r in od["reasons"])


def test_term_above_max_switches_recommendation(client, fast):
    items = recommend(client, fast, purposeCategory="CASH_GAP", termMonths=24)["items"]
    od = next(i for i in items if i["product"]["code"] == "OVERDRAFT")
    assert any("больше максимума" in r for r in od["reasons"]) and od["recommended"] is False
    assert items[0]["product"]["code"] == "WORKING_CAPITAL" and items[0]["recommended"] is False


def test_term_below_min_and_atypical(client, fast):
    items = recommend(client, fast, purposeCategory="EQUIPMENT_PURCHASE", termMonths=6)["items"]
    eq = next(i for i in items if i["product"]["code"] == "EQUIPMENT")
    assert any("меньше минимума" in r for r in eq["reasons"]) and eq["matchScore"] == 75
    atypical = recommend(client, fast, purposeCategory="SEASONAL", termMonths=24)["items"][0]
    assert atypical["matchScore"] == 75 and any("обычно берут" in r for r in atypical["reasons"])


def test_deterministic(client, fast):
    args = {"purposeCategory": "SEASONAL", "amount": 2_000_000, "termMonths": 9}
    assert recommend(client, fast, **args) == recommend(client, fast, **args)


@pytest.mark.parametrize(
    "body",
    [
        {"purposeCategory": "UNKNOWN"},
        {"purposeCategory": "OTHER", "amount": -5},
        {"purposeCategory": "OTHER", "termMonths": 0},
        {},
    ],
)
def test_validation(client, fast, body):
    r = client.post(URL, headers=fast, json=body)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION_ERROR"


def test_requires_client_role(client, underwriter):
    assert client.post(URL, json={"purposeCategory": "OTHER"}).status_code == 401
    assert client.post(URL, headers=underwriter, json={"purposeCategory": "OTHER"}).status_code == 403


def test_rules_cover_every_category():
    assert set(load_recommendation_config().purposes) == set(PurposeCategory)
