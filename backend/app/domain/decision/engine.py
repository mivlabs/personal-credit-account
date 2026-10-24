"""Pure scoring and policy plus a thin adapter for the existing application contract."""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_DOWN, Decimal

from app.domain.clock import age_in_months, as_of_date
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
    inputs: dict = field(default_factory=dict)


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
    # Значения анкеты и источников отдельно: подтверждённый источник приоритетнее анкеты
    revenue_client: Decimal | None = None
    debt_client: Decimal | None = None
    revenue_source: Decimal | None = None
    debt_source: Decimal | None = None
    revenue_declared_only: bool = False


DATA_MISMATCH_EXPLANATION = (
    "Значение в анкете расходится с данными ФНС/БКИ больше допустимого порога; источник приоритетнее анкеты"
)


def diverges(client: Decimal, source: Decimal, threshold_pct: Decimal) -> bool:
    if source == 0:
        return client != 0
    return abs(client - source) / abs(source) * 100 > threshold_pct


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
    mismatches = [
        (name, client, source)
        for name, client, source in (
            ("выручка", data.revenue_client, data.revenue_source),
            ("долг", data.debt_client, data.debt_source),
        )
        if client is not None and source is not None and diverges(client, source, config.data_mismatch_pct)
    ]
    if mismatches:
        details = "; ".join(f"{n}: в анкете {c}, по данным источника {s}" for n, c, s in mismatches)
        return DecisionResult(
            DecisionOutcome.MANUAL_REVIEW,
            None,
            [FactorResult("DATA_MISMATCH", details, 0, DATA_MISMATCH_EXPLANATION)],
            reason="Данные анкеты расходятся с подтверждёнными данными: заявку проверит специалист",
            note=f"DATA_MISMATCH (порог {config.data_mismatch_pct}%): {details}",
            rule_code="DATA_MISMATCH",
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
        "AGE_MONTHS": "Срок деятельности компании на дату расчёта (AS_OF_DATE)",
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
    )
    if data.revenue_declared_only:
        limit *= config.client_declared_limit_factor
    limit = limit.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
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


def decide(
    application, external_data: ExternalData, config: DecisionConfig, as_of: date | None = None
) -> DecisionResult:
    def source(code):
        result = external_data.results.get(code)
        return result.data or {} if result else {}

    egrul, fns, bki = (source(s) for s in (CheckSource.EGRUL, CheckSource.FNS, CheckSource.BKI))
    registered = egrul.get("registrationDate")
    age = None
    if registered:
        registered = date.fromisoformat(registered)
        age = age_in_months(registered, as_of or as_of_date())

    def amount(value):
        return Decimal(str(value)) if value is not None else None

    # Подтверждённый источник приоритетнее анкеты; значение клиента нужно только при пустом источнике.
    revenue_source = amount(fns.get("annualRevenue"))
    debt_source = amount(bki.get("debtAmount"))
    revenue = revenue_source if revenue_source is not None else application.revenue_amt
    debt = debt_source if debt_source is not None else application.debt_amt

    def status_of(code):
        result = external_data.results.get(code)
        return result.status.value if result else "NOT_REQUESTED"

    def inp(value, source, source_value=None, client_value=None):
        if value is not None and source_value is None and client_value is not None:
            # источник пуст: используется значение клиента
            return {"value": str(value), "source": "CLIENT", "status": "PROVIDED"}
        item = {
            "value": None if value is None else str(value),
            "source": source.value,
            "status": status_of(source),
        }
        if client_value is not None and source_value is not None:
            item["declaredValue"] = str(client_value)  # значение из анкеты для сравнения
        return item

    inputs = {
        "requestedAmount": {
            "value": str(application.requested_amt),
            "source": "CLIENT",
            "status": "PROVIDED",
        },
        "annualRevenue": inp(revenue, CheckSource.FNS, revenue_source, application.revenue_amt),
        "debtAmount": inp(debt, CheckSource.BKI, debt_source, application.debt_amt),
        "overdueDays": inp(bki.get("overdueDays"), CheckSource.BKI),
        "registrationDate": inp(egrul.get("registrationDate"), CheckSource.EGRUL),
        "active": inp(egrul.get("active"), CheckSource.EGRUL),
        "industry": inp(egrul.get("industry"), CheckSource.EGRUL),
    }
    result = evaluate(
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
            revenue_client=application.revenue_amt,
            debt_client=application.debt_amt,
            revenue_source=revenue_source,
            debt_source=debt_source,
            revenue_declared_only=revenue_source is None and application.revenue_amt is not None,
        ),
        config,
    )
    return replace(result, inputs=inputs)
