from decimal import Decimal

import pytest

from app.domain.offers import monthly_payment


@pytest.mark.parametrize(
    ("amount", "rate", "months", "expected"),
    [
        ("1000000", "12", 12, "88848.79"),  # классический аннуитет: 1 млн, 12% годовых, 12 мес.
        ("1500000", "16.9", 24, "74091.34"),
        ("600000", "0", 12, "50000.00"),  # нулевая ставка: ровно S / n
        ("100000", "21", 1, "101750.00"),  # на один месяц: тело + месячные проценты
    ],
)
def test_monthly_payment_matches_annuity_formula(amount, rate, months, expected):
    assert monthly_payment(Decimal(amount), Decimal(rate), months) == Decimal(expected)


def test_total_payments_exceed_principal_for_positive_rate():
    payment = monthly_payment(Decimal("3000000"), Decimal("18.5"), 36)
    assert payment * 36 > Decimal("3000000")


def test_non_positive_term_is_rejected():
    with pytest.raises(ValueError):
        monthly_payment(Decimal("100000"), Decimal("10"), 0)
