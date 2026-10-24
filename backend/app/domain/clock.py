"""Дата расчёта: AS_OF_DATE из окружения или сегодня по Москве."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings

MOSCOW = ZoneInfo("Europe/Moscow")


def as_of_date() -> date:
    """От этой даты считается возраст компании. snapshot_date политики — только дата версии."""
    return get_settings().as_of_date or datetime.now(MOSCOW).date()


def age_in_months(registered: date, as_of: date) -> int:
    """Полные месяцы между датой регистрации и датой расчёта."""
    return (as_of.year - registered.year) * 12 + as_of.month - registered.month - (as_of.day < registered.day)
