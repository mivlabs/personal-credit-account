"""Данные seed: справочники и демо-аккаунты (только синтетика).

Справочники синхронизируются с кодом при каждом старте (это конфигурация).
Компании и пользователи только добавляются: существующие строки не трогаем.
ИНН закреплены в docs/test-accounts.md: на них завязаны стабы WireMock, не менять без договорённости.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.enums import (
    FINAL_STATUSES,
    STATUS_NAMES,
    ApplicationStatus,
    LegalForm,
    ProductCode,
    UserRole,
)

DEMO_PASSWORD = "demo1234"

ROLES: dict[UserRole, str] = {
    UserRole.CLIENT: "Клиент",
    UserRole.UNDERWRITER: "Андеррайтер",
}

STATUSES: list[tuple[str, str, bool]] = [
    (status.value, STATUS_NAMES[status], status in FINAL_STATUSES) for status in ApplicationStatus
]


@dataclass(frozen=True)
class ProductSeed:
    code: ProductCode
    name: str
    min_amt: Decimal
    max_amt: Decimal
    min_term: int
    max_term: int
    rate: Decimal
    requirement: str


# Цифры условные, скоринг-карта и политика — в конфиге решения
PRODUCTS: list[ProductSeed] = [
    ProductSeed(
        ProductCode.WORKING_CAPITAL,
        "Оборотный кредит",
        Decimal("300000"),
        Decimal("10000000"),
        3,
        36,
        Decimal("18.5"),
        "Бизнесу не менее 6 месяцев, нет просрочки свыше 90 дней",
    ),
    ProductSeed(
        ProductCode.EQUIPMENT,
        "Кредит на оборудование",
        Decimal("500000"),
        Decimal("30000000"),
        12,
        60,
        Decimal("16.9"),
        "Бизнесу не менее 6 месяцев, нет просрочки свыше 90 дней",
    ),
    ProductSeed(
        ProductCode.OVERDRAFT,
        "Овердрафт",
        Decimal("100000"),
        Decimal("5000000"),
        1,
        12,
        Decimal("21"),
        "Бизнесу не менее 6 месяцев, нет просрочки свыше 90 дней",
    ),
]


@dataclass(frozen=True)
class DemoClient:
    login: str
    user_name: str
    inn: str
    ogrn: str
    company_name: str
    legal_form: LegalForm
    registration_dt: date
    address: str


def _months_ago(months: int) -> date:
    # Дата считается от дня первого запуска: стоп-фактор «моложе 6 мес.» не «состарится» к финалу
    return date(2026, 1, 23)


DEMO_CLIENTS: list[DemoClient] = [
    DemoClient(
        "client_fast",
        "Соколов Андрей Викторович",
        "770100000001",
        "321770000000011",
        "ИП Соколов Андрей Викторович",
        LegalForm.IP,
        date(2016, 3, 14),
        "г. Москва, ул. Тверская, д. 12, кв. 34",
    ),
    DemoClient(
        "client_counter",
        "Морозова Ирина Павловна",
        "7701000002",
        "1157700000022",
        "ООО «Вектор Логистик»",
        LegalForm.OOO,
        date(2015, 9, 1),
        "г. Москва, Ленинградский пр-т, д. 39, стр. 2, офис 410",
    ),
    DemoClient(
        "client_manual",
        "Кузнецов Дмитрий Олегович",
        "7701000003",
        "1257700000033",
        "ООО «НовоСтрой Групп»",
        LegalForm.OOO,
        _months_ago(9),
        "г. Санкт-Петербург, Лиговский пр-т, д. 50, офис 12",
    ),
    DemoClient(
        "client_info",
        "Васильева Ольга Сергеевна",
        "7701000004",
        "1177700000044",
        "ООО «Зелёный Двор»",
        LegalForm.OOO,
        date(2017, 6, 20),
        "г. Казань, ул. Баумана, д. 7, офис 3",
    ),
    DemoClient(
        "client_reject",
        "Орлов Павел Николаевич",
        "7701000005",
        "1147700000055",
        "ООО «Старт Трейд»",
        LegalForm.OOO,
        date(2014, 11, 5),
        "г. Екатеринбург, ул. Малышева, д. 36, офис 201",
    ),
    DemoClient(
        "client_timeout",
        "Громов Сергей Игоревич",
        "7701000006",
        "1197700000066",
        "ООО «Дальний Восток Снаб»",
        LegalForm.OOO,
        date(2019, 2, 11),
        "г. Владивосток, ул. Светланская, д. 22, офис 8",
    ),
]

UNDERWRITER_LOGIN = "underwriter"
UNDERWRITER_NAME = "Петрова Елена Андреевна"
