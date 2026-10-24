"""Структурированный снимок решения (credit_decision.decision_snapshot) и его клиентская версия."""

from datetime import date
from decimal import Decimal

from app.domain.decision.config import DecisionConfig
from app.domain.decision.engine import DecisionResult
from app.domain.pricing import RateBreakdown

LIMIT_FORMULA = "min(максимум продукта; годовая выручка × доля выручки − долг × доля долга), не меньше 0"

FACTOR_LABELS = {
    "AGE_MONTHS": "Срок деятельности компании",
    "ANNUAL_REVENUE_RUB": "Годовая выручка",
    "DEBT_TO_ANNUAL_REVENUE": "Долговая нагрузка (долг к годовой выручке)",
    "OVERDUE_DAYS": "Просрочки в кредитной истории",
    "INDUSTRY": "Отрасль",
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
    return max(config.industry_points.values())


def _limit_block(result: DecisionResult, config: DecisionConfig, product_max: Decimal) -> dict | None:
    if result.limit is None:
        return None
    revenue = Decimal(result.inputs["annualRevenue"]["value"])
    debt = Decimal(result.inputs["debtAmount"]["value"])
    return {
        "value": str(result.limit),
        "formula": LIMIT_FORMULA,
        "components": {
            "revenueShare": str(revenue * config.revenue_limit_share),
            "debtShare": str(debt * config.debt_limit_share),
            "productMax": str(product_max),
        },
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
        c = limit["components"]
        limit_out = {
            "value": limit["value"],
            "text": (
                f"Доступная сумма {limit['value']} ₽: не больше {c['productMax']} ₽ (максимум продукта); "
                f"{c['revenueShare']} ₽ от годовой выручки за вычетом {c['debtShare']} ₽ текущего долга"
            ),
            "components": c,
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
