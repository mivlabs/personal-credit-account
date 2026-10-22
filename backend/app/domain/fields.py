"""Поля анкеты: имя в API ↔ атрибут модели ↔ атрибут схемы."""

from app.domain.enums import ApplicationField

F = ApplicationField

# имя в API (camelCase) → колонка loan_application
FIELD_ATTR: dict[ApplicationField, str] = {
    F.REQUESTED_AMOUNT: "requested_amt",
    F.TERM_MONTHS: "term_qnt",
    F.PURPOSE: "purpose_desc",
    F.REVENUE_AMOUNT: "revenue_amt",
    F.DEBT_AMOUNT: "debt_amt",
}

# имя в API → атрибут Pydantic-схемы (snake_case)
SCHEMA_ATTR: dict[ApplicationField, str] = {
    F.REQUESTED_AMOUNT: "requested_amount",
    F.TERM_MONTHS: "term_months",
    F.PURPOSE: "purpose",
    F.REVENUE_AMOUNT: "revenue_amount",
    F.DEBT_AMOUNT: "debt_amount",
}

# Обязательные поля для подачи заявки
REQUIRED_FOR_SUBMIT: tuple[ApplicationField, ...] = (
    F.REQUESTED_AMOUNT,
    F.TERM_MONTHS,
    F.PURPOSE,
)
