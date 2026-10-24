"""Структурированный снимок решения (credit_decision.decision_snapshot) и его клиентская версия."""

from datetime import date
from decimal import Decimal

from app.domain.decision.config import DecisionConfig
from app.domain.decision.engine import DecisionResult
from app.domain.pricing import RateBreakdown

LIMIT_FORMULA_SCHEDULE = (
    "min(тело аннуитета для допустимого платежа при запрошенном сроке; "
    "годовая выручка × доля выручки − долг × доля долга; максимум продукта), не меньше 0; "
    "допустимый платёж = месячная выручка × предельная нагрузка − оценка платежей по текущему долгу"
)
LIMIT_FORMULA_OVERDRAFT = (
    "min(месячная выручка × доля оборота; "
    "годовая выручка × доля выручки − долг × доля долга; максимум продукта), не меньше 0"
)

BINDING_TEXTS = {
    "PAYMENT_LOAD": "платёжной нагрузкой",
    "OVERDRAFT_TURNOVER": "оборотом по овердрафту",
    "REVENUE_SHARE": "долей годовой выручки за вычетом долга",
    "PRODUCT_MAX": "максимальной суммой продукта",
}

FACTOR_LABELS = {
    "AGE_MONTHS": "Срок деятельности компании",
    "ANNUAL_REVENUE_RUB": "Годовая выручка",
    "DEBT_TO_ANNUAL_REVENUE": "Долговая нагрузка (долг к годовой выручке)",
    "OVERDUE_DAYS": "Просрочки в кредитной истории",
    "INDUSTRY": "Отрасль",
    "DATA_MISMATCH": "Расхождение анкеты с источником",
}

INPUT_LABELS = {
    "requestedAmount": "Запрошенная сумма",
    "annualRevenue": "Годовая выручка",
    "debtAmount": "Текущий долг",
    "overdueDays": "Дней просрочки",
    "registrationDate": "Дата регистрации",
    "active": "Компания действует",
    "industry": "Отрасль",
}

SOURCE_NAMES = {
    "CLIENT": "со слов клиента",
    "EGRUL": "ЕГРЮЛ",
    "FNS": "ФНС",
    "BKI": "бюро кредитных историй",
}

RULE_TEXTS = {
    "INACTIVE_COMPANY": "Компания прекратила деятельность: автоматическое решение невозможно",
    "YOUNG_COMPANY": "Бизнес работает меньше минимального срока: кредит пока недоступен",
    "OVERDUE": "В кредитной истории есть просрочка выше допустимой",
    "EXTERNAL_UNAVAILABLE": "Не удалось получить все данные из внешних источников: заявку проверит специалист",
    "MISSING_FINANCIALS": "Не хватает финансовых показателей: нужно, чтобы вы их указали",
    "DATA_MISMATCH": "Данные в анкете расходятся с подтверждёнными данными: заявку проверит специалист",
    "LOW_SCORE": "Оценка заявки ниже порога отказа",
    "BORDERLINE_SCORE": "Оценка заявки в промежуточной зоне: решение примет специалист банка",
    "LIMIT_BELOW_MINIMUM": "Оценка достаточная, но доступная сумма ниже минимальной суммы продукта",
    "ABOVE_LIMIT": "Оценка достаточная, но запрошенная сумма выше доступной: предлагаем меньшую",
    "WITHIN_LIMIT": "Оценка достаточная, запрошенная сумма в пределах доступной",
    "MANUAL": "Решение принято специалистом банка",
}


def factor_max_points(code: str, config: DecisionConfig) -> int:
    bands = {
        "AGE_MONTHS": config.age_bands,
        "ANNUAL_REVENUE_RUB": config.revenue_bands,
        "DEBT_TO_ANNUAL_REVENUE": config.debt_bands,
        "OVERDUE_DAYS": config.overdue_bands,
    }.get(code)
    if bands is not None:
        return max(points for _, points in bands)
    if code == "DATA_MISMATCH":
        return 0
    return max(config.industry_points.values())


def _limit_block(result: DecisionResult, config: DecisionConfig, product_max: Decimal) -> dict | None:
    calc = result.limit_detail
    if result.limit is None or calc is None:
        return None
    revenue = Decimal(result.inputs["annualRevenue"]["value"])
    debt = Decimal(result.inputs["debtAmount"]["value"])
    components = {
        "revenueShare": str(revenue * config.revenue_limit_share),
        "debtShare": str(debt * config.debt_limit_share),
        "shareLimit": str(calc.share_limit),
        "productMax": str(product_max),
        "termMonths": str(calc.term_months),
        "rate": str(calc.rate_pct),
        "monthlyRevenue": str(calc.monthly_revenue.quantize(Decimal("0.01"))),
        "debtPayment": str(calc.debt_payment.quantize(Decimal("0.01"))),
    }
    if calc.turnover_limit is not None:
        formula = LIMIT_FORMULA_OVERDRAFT
        components["turnoverLimit"] = str(calc.turnover_limit.quantize(Decimal("0.01")))
    else:
        formula = LIMIT_FORMULA_SCHEDULE
        components["maxPayment"] = str(calc.max_payment.quantize(Decimal("0.01")))
        components["paymentLoadLimit"] = str(calc.schedule_limit)
    if calc.declared_factor is not None:
        # выручка только со слов клиента: лимит урезается
        components["clientDeclaredFactor"] = str(calc.declared_factor)
        formula += " × коэффициент для выручки со слов клиента"
    return {
        "value": str(result.limit),
        "formula": formula,
        "binding": calc.binding,
        "components": components,
        "paymentLoad": None
        if calc.payment_load is None
        else str(calc.payment_load.quantize(Decimal("0.0001"))),
        "maxPaymentLoad": None if calc.turnover_limit is not None else str(config.max_payment_load),
    }


def build_auto_snapshot(
    *,
    result: DecisionResult,
    config: DecisionConfig,
    as_of: date,
    product_max: Decimal,
    external_checks: list[dict],
    rate: RateBreakdown | None,
) -> dict:
    return {
        "type": "AUTO",
        "policyVersion": config.version,
        "asOfDate": as_of.isoformat(),
        "inputs": result.inputs,
        "externalChecks": external_checks,
        "factors": [
            {
                "code": f.code,
                "label": FACTOR_LABELS[f.code],
                "value": f.value,
                "points": f.points,
                "maxPoints": factor_max_points(f.code, config),
                "explanation": f.explanation,
            }
            for f in result.factors
        ],
        "score": result.score,
        "thresholds": {"approve": config.approve_threshold, "reject": config.reject_threshold},
        "ruleCode": result.rule_code,
        "limit": _limit_block(result, config, product_max),
        "rate": rate.to_json() if rate else None,
    }


def build_manual_snapshot(
    *,
    config: DecisionConfig,
    as_of: date,
    user_id: int,
    user_name: str | None,
    outcome: str,
    comment: str,
    offer_amount: Decimal | None,
    rate: RateBreakdown | None,
    auto_limit: Decimal | None,
    limit_exceeded: bool,
    override_limit: bool,
) -> dict:
    return {
        "type": "MANUAL",
        "policyVersion": config.version,
        "asOfDate": as_of.isoformat(),
        "ruleCode": "MANUAL",
        "outcome": outcome,
        "decidedBy": {"id": user_id, "name": user_name},
        "comment": comment,
        "offerAmount": str(offer_amount) if offer_amount is not None else None,
        "rate": rate.to_json() if rate else None,
        "autoLimit": str(auto_limit) if auto_limit is not None else None,
        "limitExceeded": limit_exceeded,
        "overrideLimit": override_limit,
        "limitUnknown": auto_limit is None,
    }


def _percent(share: str) -> str:
    return f"{Decimal(share) * 100:.0f}%"


def _limit_text(limit: dict) -> str:
    c = limit["components"]
    binding = limit.get("binding")
    text = (
        f"Доступная сумма {limit['value']} ₽: не больше {c['productMax']} ₽ (максимум продукта); "
        f"{c['revenueShare']} ₽ от годовой выручки за вычетом {c['debtShare']} ₽ текущего долга"
    )
    if "turnoverLimit" in c:
        text += f"; не больше {c['turnoverLimit']} ₽ от месячного оборота"
    elif "paymentLoadLimit" in c:
        text += (
            f"; не больше {c['paymentLoadLimit']} ₽ по платёжной нагрузке "
            f"(срок {c['termMonths']} мес., ставка {c['rate']}%)"
        )
    if "clientDeclaredFactor" in c:
        text += f"; выручка указана вами и не подтверждена ФНС, поэтому лимит умножен на {c['clientDeclaredFactor']}"
    if binding in BINDING_TEXTS:
        text += f". Сумма ограничена {BINDING_TEXTS[binding]}"
    if limit.get("paymentLoad") is not None and limit.get("maxPaymentLoad") is not None:
        load, max_load = Decimal(limit["paymentLoad"]), Decimal(limit["maxPaymentLoad"])
        if binding == "PAYMENT_LOAD" or load > max_load:
            text += (
                f": при запрошенной сумме платежи заняли бы {_percent(limit['paymentLoad'])} "
                f"месячной выручки при допустимых {_percent(limit['maxPaymentLoad'])}"
            )
        if Decimal(c.get("maxPayment", "0")) < 0:
            text += "; платежи по текущему долгу уже превышают допустимую нагрузку"
    return text


def _impact(points: int, max_points: int) -> tuple[str, str]:
    if max_points and points / max_points >= 0.6:
        return "STRENGTH", "сильная сторона"
    return "WEAKNESS", "снижает оценку"


def explain(snapshot: dict | None, auto_snapshot: dict | None = None) -> dict | None:
    """Человеческая версия снимка для клиента: без конфига и без внутреннего комментария андеррайтера.

    Для ручного решения входы, факторы и лимит берутся из последнего AUTO-снимка (auto_snapshot).
    """
    if not snapshot:
        return None
    base = snapshot if snapshot.get("type") != "MANUAL" else (auto_snapshot or {})
    inputs = [
        {
            "code": code,
            "label": INPUT_LABELS[code],
            "value": item["value"],
            "source": item["source"],
            "sourceName": SOURCE_NAMES.get(item["source"], item["source"]),
        }
        for code, item in (base.get("inputs") or {}).items()
        if code in INPUT_LABELS and item.get("value") is not None
    ]
    factors = []
    for f in base.get("factors") or []:
        impact, impact_label = _impact(f["points"], f["maxPoints"])
        factors.append(
            {
                "code": f["code"],
                "label": f["label"],
                "value": f["value"],
                "points": f["points"],
                "maxPoints": f["maxPoints"],
                "impact": impact,
                "impactLabel": impact_label,
                "explanation": f["explanation"],
            }
        )
    limit = base.get("limit")
    limit_out = None
    if limit:
        limit_out = {
            "value": limit["value"],
            "text": _limit_text(limit),
            "components": limit["components"],
            "binding": limit.get("binding"),
            "paymentLoad": limit.get("paymentLoad"),
            "maxPaymentLoad": limit.get("maxPaymentLoad"),
        }
    return {
        "ruleCode": snapshot["ruleCode"],
        "ruleText": RULE_TEXTS.get(snapshot["ruleCode"], snapshot["ruleCode"]),
        "decidedBySpecialist": snapshot.get("type") == "MANUAL",
        "score": base.get("score"),
        "thresholds": base.get("thresholds"),
        "inputs": inputs,
        "factors": factors,
        "limit": limit_out,
        "rate": snapshot.get("rate"),
        "asOfDate": snapshot["asOfDate"],
        "policyVersion": snapshot["policyVersion"],
    }
