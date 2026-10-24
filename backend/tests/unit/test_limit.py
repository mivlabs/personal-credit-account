"""Лимит = минимум ограничений: платёжная нагрузка / оборот овердрафта, доля выручки, максимум продукта."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.domain.decision.config import load_decision_config
from app.domain.decision.engine import DecisionInput, compute_limit, evaluate
from app.domain.decision.snapshot import build_auto_snapshot, explain
from app.domain.enums import DecisionOutcome as O
from app.domain.offers import monthly_payment, principal_for_payment

CONFIG = load_decision_config()
BASE = DecisionInput(
    True, 120, D("12000000"), D("0"), 0, "services", D("10000000"), D("300000"), D("10000000"), term_months=12
)
OVERDRAFT = replace(
    BASE, product_code="OVERDRAFT", requested=D("1000000"), product_min=D("100000"), product_max=D("5000000")
)


def limit_of(data, score=100):
    return compute_limit(data, score, CONFIG)


@pytest.mark.parametrize(("rate", "months"), [("16.5", 12), ("17.5", 36), ("0", 24)])
def test_principal_is_inverse_of_annuity(rate, months):
    payment = monthly_payment(D("2500000"), D(rate), months)
    principal = principal_for_payment(payment, D(rate), months)
    assert abs(principal - D("2500000")) < D("1")  # ошибка только от округления платежа до копеек


def test_longer_term_gives_larger_limit():
    short, long_ = limit_of(BASE), limit_of(replace(BASE, term_months=24))
    assert short.binding == "PAYMENT_LOAD"
    assert short.value < long_.value
    assert limit_of(replace(BASE, term_months=6)).value < short.value


def test_overdraft_limit_does_not_depend_on_term():
    values = {limit_of(replace(OVERDRAFT, term_months=m)).value for m in (1, 6, 12)}
    assert values == {D("400000.00")}  # 12 млн / 12 × 0,40
    assert limit_of(OVERDRAFT).binding == "OVERDRAFT_TURNOVER"
    assert limit_of(OVERDRAFT).payment_load is None


def test_binding_constraint_for_each_case():
    assert limit_of(BASE).binding == "PAYMENT_LOAD"
    assert limit_of(replace(BASE, term_months=36)).binding == "REVENUE_SHARE"  # 6 млн < тело аннуитета
    assert limit_of(OVERDRAFT).binding == "OVERDRAFT_TURNOVER"
    rich = replace(BASE, revenue=D("60000000"), term_months=36)
    assert limit_of(rich).binding == "PRODUCT_MAX" and limit_of(rich).value == D("10000000.00")
    rich_overdraft = replace(OVERDRAFT, revenue=D("300000000"), product_max=D("5000000"))
    assert limit_of(rich_overdraft).binding == "PRODUCT_MAX"


def test_high_debt_lowers_limit_through_debt_payment():
    clean, indebted = limit_of(BASE), limit_of(replace(BASE, debt=D("3000000")))
    assert indebted.debt_payment == D("3000000") * CONFIG.debt_service_monthly_share == D("120000.00")
    assert indebted.max_payment == clean.max_payment - D("120000")
    assert indebted.schedule_limit < clean.schedule_limit
    assert indebted.value < clean.value


def test_negative_max_payment_gives_zero_limit_and_explanation():
    config = CONFIG.model_copy(
        update={"debt_limit_share": D("0.1")}
    )  # чтобы долговая доля не обнулила лимит раньше
    data = replace(BASE, debt=D("11000000"))  # платежи по долгу 440 тыс. > допустимых 400 тыс.
    calc = compute_limit(data, 100, config)
    assert calc.max_payment < 0 and calc.value == D("0.00") and calc.binding == "PAYMENT_LOAD"

    result = evaluate(data, config)
    assert result.outcome == O.REJECTED and result.rule_code == "LIMIT_BELOW_MINIMUM"
    inputs = {
        "annualRevenue": {"value": "12000000", "source": "FNS"},
        "debtAmount": {"value": "11000000", "source": "BKI"},
    }
    snapshot = build_auto_snapshot(
        result=replace(result, inputs=inputs),
        config=config,
        as_of=config.snapshot_date,
        product_max=data.product_max,
        external_checks=[],
        rate=None,
    )
    assert snapshot["limit"]["binding"] == "PAYMENT_LOAD" and snapshot["limit"]["value"] == "0.00"
    text = explain(snapshot)["limit"]["text"]
    assert "платёжной нагрузкой" in text and "платежи по текущему долгу уже превышают" in text


def test_counter_offer_amount_fits_payment_load():
    result = evaluate(BASE, CONFIG)
    assert result.outcome == O.COUNTER_OFFER and result.rule_code == "ABOVE_LIMIT"
    assert result.offer_amt == result.limit_detail.value < BASE.requested
    # при предложенной сумме нагрузка укладывается в порог, при запрошенной нет
    offered = replace(BASE, requested=result.offer_amt)
    assert limit_of(offered).payment_load <= CONFIG.max_payment_load < result.limit_detail.payment_load


def test_snapshot_limit_block_and_client_text():
    result = evaluate(BASE, CONFIG)
    inputs = {
        "annualRevenue": {"value": "12000000", "source": "FNS"},
        "debtAmount": {"value": "0", "source": "BKI"},
    }
    snapshot = build_auto_snapshot(
        result=replace(result, inputs=inputs),
        config=CONFIG,
        as_of=CONFIG.snapshot_date,
        product_max=BASE.product_max,
        external_checks=[],
        rate=None,
    )
    limit = snapshot["limit"]
    assert limit["binding"] == "PAYMENT_LOAD" and limit["value"] == str(result.limit)
    assert limit["maxPaymentLoad"] == str(CONFIG.max_payment_load)
    assert D(limit["paymentLoad"]) > CONFIG.max_payment_load
    assert {"paymentLoadLimit", "maxPayment", "shareLimit", "revenueShare", "productMax"} <= set(
        limit["components"]
    )
    text = explain(snapshot)["limit"]["text"]
    assert "при запрошенной сумме платежи заняли бы" in text and "при допустимых 40%" in text
