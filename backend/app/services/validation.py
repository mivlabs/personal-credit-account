"""Проверки анкеты относительно продукта: диапазоны суммы и срока, обязательные поля."""

from decimal import Decimal
from typing import Any

from app.core.errors import field_error
from app.db.models import DimCreditProduct, LoanApplication
from app.domain.enums import ApplicationField
from app.domain.fields import FIELD_ATTR, REQUIRED_FOR_SUBMIT

F = ApplicationField


def fmt_rub(value: Decimal | int) -> str:
    """300000 → «300 000»."""
    return f"{int(value):,}".replace(",", " ")


def range_errors(
    product: DimCreditProduct,
    *,
    amount: Decimal | None,
    term: int | None,
    check_amount: bool = True,
    check_term: bool = True,
) -> list[dict[str, Any]]:
    errors = []
    if check_amount and amount is not None and not (product.min_amt <= amount <= product.max_amt):
        errors.append(
            field_error(
                F.REQUESTED_AMOUNT.value,
                f"Сумма для продукта «{product.product_name}» должна быть от "
                f"{fmt_rub(product.min_amt)} до {fmt_rub(product.max_amt)} ₽",
                "OUT_OF_RANGE",
            )
        )
    if check_term and term is not None and not (product.min_term_qnt <= term <= product.max_term_qnt):
        errors.append(
            field_error(
                F.TERM_MONTHS.value,
                f"Срок для продукта «{product.product_name}» должен быть от "
                f"{product.min_term_qnt} до {product.max_term_qnt} мес.",
                "OUT_OF_RANGE",
            )
        )
    return errors


def submit_errors(app: LoanApplication) -> list[dict[str, Any]]:
    """Что мешает подать заявку: пустые обязательные поля и значения вне диапазона продукта."""
    errors = []
    for f in REQUIRED_FOR_SUBMIT:
        value = getattr(app, FIELD_ATTR[f])
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(field_error(f.value, "Обязательное поле: заполните его перед подачей", "REQUIRED"))
    errors += range_errors(app.product, amount=app.requested_amt, term=app.term_qnt)
    return errors
