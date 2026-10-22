"""Расчёт оффера: аннуитетный платёж."""

from decimal import ROUND_HALF_UP, Decimal, localcontext

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
