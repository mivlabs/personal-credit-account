"""Конфигурация кредитной политики. В четверг значения приходят из конфига Миши (YAML), сегодня — по умолчанию."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionConfig:
    approve_threshold: int = 70  # балл ≥ порога: одобрение или контроффер
    reject_threshold: int = 40  # балл < порога: отказ; между порогами — ручная проверка
    min_company_age_months: int = 6  # стоп-фактор: бизнесу меньше
    max_overdue_days: int = 90  # стоп-фактор: просрочка больше


def load_decision_config() -> DecisionConfig:
    return DecisionConfig()
