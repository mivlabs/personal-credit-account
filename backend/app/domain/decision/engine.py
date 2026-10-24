"""Pure scoring and policy plus a thin adapter for the existing application contract."""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, Decimal

from app.domain.decision.config import DecisionConfig
from app.domain.enums import ApplicationField, CheckSource, DecisionOutcome
from app.integrations.base import ExternalData


@dataclass(frozen=True)
class FactorResult:
    code: str
    value: str | None
    points: int
    explanation: str = ""


@dataclass(frozen=True)
class InfoRequestSpec:
    description: str
    fields: list[ApplicationField]


@dataclass(frozen=True)
class DecisionResult:
    outcome: DecisionOutcome
    score: int | None
    factors: list[FactorResult] = field(default_factory=list)
    reason: str = ""
    offer_amt: Decimal | None = None
    info_request: InfoRequestSpec | None = None
    note: str | None = None
    limit: Decimal | None = None
    rule_code: str = ""


@dataclass(frozen=True)
class DecisionInput:
    active: bool | None
    age_months: int | None
    revenue: Decimal | None
    debt: Decimal | None
    overdue_days: int | None
    industry: str | None
    requested: Decimal
    product_min: Decimal
    product_max: Decimal
    failed_sources: tuple[str, ...] = ()


def band_points(value, bands) -> int:
    return next((points for upper, points in bands if value <= upper), bands[-1][1])


def apply_policy(
    score: int, requested: Decimal, limit: Decimal, minimum: Decimal, config: DecisionConfig
) -> tuple[DecisionOutcome, str]:
    if score < config.reject_threshold:
        return DecisionOutcome.REJECTED, "LOW_SCORE"
    if score < config.approve_threshold:
        return DecisionOutcome.MANUAL_REVIEW, "BORDERLINE_SCORE"
    if limit < minimum:
        return DecisionOutcome.REJECTED, "LIMIT_BELOW_MINIMUM"
    if requested > limit:
        return DecisionOutcome.COUNTER_OFFER, "ABOVE_LIMIT"
    return DecisionOutcome.APPROVED, "WITHIN_LIMIT"


def evaluate(data: DecisionInput, config: DecisionConfig) -> DecisionResult:
    stop = None
    if data.active is False:
        stop = ("INACTIVE_COMPANY", "Компания прекратила деятельность")
    elif data.age_months is not None and data.age_months < config.min_company_age_months:
        stop = ("YOUNG_COMPANY", "Для кредита бизнес должен работать не менее 6 месяцев")
    elif data.overdue_days is not None and data.overdue_days > config.max_overdue_days:
        stop = ("OVERDUE", "В кредитной истории есть просрочка более 90 дней")
    if stop:
        return DecisionResult(DecisionOutcome.REJECTED, None, reason=stop[1], rule_code=stop[0])
    if data.failed_sources or any(
        v is None for v in (data.active, data.age_months, data.overdue_days, data.industry)
    ):
        return DecisionResult(
            DecisionOutcome.MANUAL_REVIEW,
            None,
            reason="Данные проверит специалист банка",
            note="Не удалось получить полные данные внешних проверок: " + ", ".join(data.failed_sources),
            rule_code="EXTERNAL_UNAVAILABLE",
        )
    missing = [
        f
        for f, v in (
            (ApplicationField.REVENUE_AMOUNT, data.revenue),
            (ApplicationField.DEBT_AMOUNT, data.debt),
        )
        if v is None
    ]
    if missing:
        return DecisionResult(
            DecisionOutcome.NEEDS_INFO,
            None,
            reason="Укажите недостающие финансовые показатели",
            info_request=InfoRequestSpec(
                "Укажите годовую выручку и текущий остаток задолженности по запрошенным полям", missing
            ),
            rule_code="MISSING_FINANCIALS",
        )
    ratio = (
        data.debt / data.revenue if data.revenue else (Decimal(0) if not data.debt else Decimal("Infinity"))
    )
    factors = [
        FactorResult("AGE_MONTHS", str(data.age_months), band_points(data.age_months, config.age_bands)),
        FactorResult(
            "ANNUAL_REVENUE_RUB", str(data.revenue), band_points(data.revenue, config.revenue_bands)
        ),
        FactorResult("DEBT_TO_ANNUAL_REVENUE", str(ratio), band_points(ratio, config.debt_bands)),
        FactorResult(
            "OVERDUE_DAYS", str(data.overdue_days), band_points(data.overdue_days, config.overdue_bands)
        ),
        FactorResult(
            "INDUSTRY",
            data.industry,
            config.industry_points.get(data.industry, config.industry_points["other"]),
        ),
    ]
    explanations = {
        "AGE_MONTHS": "Срок деятельности компании на дату демо-снимка",
        "ANNUAL_REVENUE_RUB": "Выручка за полный год, в рублях",
        "DEBT_TO_ANNUAL_REVENUE": "Остаток долга, делённый на годовую выручку; меньшее значение даёт больше баллов",
        "OVERDUE_DAYS": "Число дней просрочки по синтетической кредитной истории",
        "INDUSTRY": "Демонстрационная отраслевая оценка из конфигурации",
    }
    factors = [FactorResult(f.code, f.value, f.points, explanations[f.code]) for f in factors]
    score = sum(f.points for f in factors)
    limit = max(
        Decimal(0),
        min(
            data.product_max, data.revenue * config.revenue_limit_share - data.debt * config.debt_limit_share
        ),
    ).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    outcome, rule = apply_policy(score, data.requested, limit, data.product_min, config)
    reasons = {
        "LOW_SCORE": "Финансовые показатели и кредитная история пока не позволяют одобрить кредит",
        "BORDERLINE_SCORE": "Для оценки заявки требуется решение специалиста банка",
        "LIMIT_BELOW_MINIMUM": "Доступная сумма ниже минимальной суммы этого продукта",
        "ABOVE_LIMIT": "Предлагаем меньшую сумму с учётом годовой выручки и текущего долга",
        "WITHIN_LIMIT": "Выручка, долговая нагрузка и кредитная история позволяют одобрить запрошенную сумму",
    }
    return DecisionResult(
        outcome,
        score,
        factors,
        reasons[rule],
        limit if outcome == DecisionOutcome.COUNTER_OFFER else None,
        note=f"{rule}; балл {score}; доступная сумма {limit} ₽",
        limit=limit,
        rule_code=rule,
    )


def decide(application, external_data: ExternalData, config: DecisionConfig) -> DecisionResult:
    def source(code):
        result = external_data.results.get(code)
        return result.data or {} if result else {}

    egrul, fns, bki = (source(s) for s in (CheckSource.EGRUL, CheckSource.FNS, CheckSource.BKI))
    registered = egrul.get("registrationDate")
    age = None
    if registered:
        registered = date.fromisoformat(registered)
        snapshot = config.snapshot_date
        age = (
            (snapshot.year - registered.year) * 12
            + snapshot.month
            - registered.month
            - (snapshot.day < registered.day)
        )

    def amount(value):
        return Decimal(str(value)) if value is not None else None

    # Explicit application values, including answers to information requests, have priority.
    revenue = (
        application.revenue_amt if application.revenue_amt is not None else amount(fns.get("annualRevenue"))
    )
    debt = application.debt_amt if application.debt_amt is not None else amount(bki.get("debtAmount"))
    return evaluate(
        DecisionInput(
            egrul.get("active"),
            age,
            revenue,
            debt,
            bki.get("overdueDays"),
            egrul.get("industry"),
            application.requested_amt,
            application.product.min_amt,
            application.product.max_amt,
            tuple(external_data.failed_sources),
        ),
        config,
    )
