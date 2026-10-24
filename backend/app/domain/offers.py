"""Расчёт оффера: аннуитетный платёж."""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext

CENT = Decimal("0.01")


def monthly_payment(amount: Decimal, annual_rate_pct: Decimal, months: int) -> Decimal:
    """Аннуитетный платёж P = S·r / (1 − (1 + r)^−n), где r = ставка / 12 / 100, n — срок в месяцах."""
    if months <= 0:
        raise ValueError("Срок должен быть положительным")
    with localcontext() as ctx:
        ctx.prec = 40
        r = Decimal(annual_rate_pct) / Decimal(12) / Decimal(100)
        if r == 0:
            payment = Decimal(amount) / months
        else:
            payment = Decimal(amount) * r / (1 - (1 + r) ** -months)
        return payment.quantize(CENT, rounding=ROUND_HALF_UP)


def principal_for_payment(payment: Decimal, annual_rate_pct: Decimal, months: int) -> Decimal:
    """Тело аннуитета, обратное к monthly_payment: S = P·(1 − (1 + r)^−n) / r, округление вниз до копеек."""
    if months <= 0:
        raise ValueError("Срок должен быть положительным")
    with localcontext() as ctx:
        ctx.prec = 40
        r = Decimal(annual_rate_pct) / Decimal(12) / Decimal(100)
        if r == 0:
            principal = Decimal(payment) * months
        else:
            principal = Decimal(payment) * (1 - (1 + r) ** -months) / r
        return principal.quantize(CENT, rounding=ROUND_DOWN)
