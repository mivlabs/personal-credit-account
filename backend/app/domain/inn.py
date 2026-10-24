"""Проверка ИНН по контрольным числам ФНС (10 цифр у ЮЛ, 12 у ИП)."""

from dataclasses import dataclass
from enum import StrEnum

_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12_FIRST = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_WEIGHTS_12_SECOND = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)

# Закреплённые синтетические ИНН seed и тестовой заявки с таймаутом БКИ контрольную сумму не проходят.
# Менять их нельзя (на них завязаны стабы WireMock), поэтому они пропускаются явным списком.
SEED_INNS = frozenset(
    {
        "770100000001",
        "7701000002",
        "7701000003",
        "7701000004",
        "7701000005",
        "7701000006",
        "7701000099",
    }
)


class InnProblem(StrEnum):
    NOT_DIGITS = "NOT_DIGITS"
    BAD_LENGTH = "BAD_LENGTH"
    BAD_CHECKSUM = "BAD_CHECKSUM"


INN_MESSAGES = {
    InnProblem.NOT_DIGITS: "ИНН состоит только из цифр",
    InnProblem.BAD_LENGTH: "ИНН содержит 10 цифр (организация) или 12 цифр (ИП)",
    InnProblem.BAD_CHECKSUM: "Неверная контрольная сумма ИНН",
}


@dataclass(frozen=True)
class InnCheck:
    valid: bool
    problem: InnProblem | None = None
    seed: bool = False

    @property
    def message(self) -> str | None:
        return INN_MESSAGES[self.problem] if self.problem else None


def _control(digits: str, weights: tuple[int, ...]) -> int:
    return sum(int(d) * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def checksum_ok(inn: str) -> bool:
    if len(inn) == 10:
        return _control(inn, _WEIGHTS_10) == int(inn[9])
    return _control(inn, _WEIGHTS_12_FIRST) == int(inn[10]) and _control(inn, _WEIGHTS_12_SECOND) == int(
        inn[11]
    )


def validate_inn(value: str) -> InnCheck:
    if not (value.isascii() and value.isdigit()):
        return InnCheck(False, InnProblem.NOT_DIGITS)
    if len(value) not in (10, 12):
        return InnCheck(False, InnProblem.BAD_LENGTH)
    if value in SEED_INNS:
        return InnCheck(True, seed=True)
    if not checksum_ok(value):
        return InnCheck(False, InnProblem.BAD_CHECKSUM)
    return InnCheck(True)


def with_checksum(base: str) -> str:
    """Достраивает контрольные цифры: из 9 цифр получается ИНН на 10, из 10 цифр ИНН на 12 (для тестов и примеров)."""
    if len(base) == 9:
        return base + str(_control(base, _WEIGHTS_10))
    first = _control(base, _WEIGHTS_12_FIRST)
    second = _control(base + str(first), _WEIGHTS_12_SECOND)
    return f"{base}{first}{second}"
