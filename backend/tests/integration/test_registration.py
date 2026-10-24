"""Регистрация по ИНН и сценарии живых моков по 9-й цифре (10-значный ИНН) / 10-й цифре (12-значный)."""

from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import AppUser, Company
from app.domain.clock import MOSCOW
from app.domain.inn import with_checksum
from app.services.auth import reset_login_limiter
from tests.integration.conftest import Flow

pytestmark = pytest.mark.live_integrations

REGISTER = "/api/v1/auth/register"
OOO_INNS = {d: with_checksum(f"77020000{d}") for d in range(10)}
IP_INNS = {d: with_checksum(f"770200000{d}") for d in range(10)}
# Те же сценарии по цифре, но другие ИНН: в одной БД ИНН уникален, а сценарные тесты занимают 7702...
SPARE_OOO = {d: with_checksum(f"77030000{d}") for d in range(10)}
DIFF_OOO = {d: with_checksum(f"77040000{d}") for d in range(10)}
SPARE_IP = {d: with_checksum(f"770300000{d}") for d in range(10)}

# цифра -> (сумма заявки, статус после подачи, правило решения)
SCENARIOS = {
    0: (1_000_000, "REJECTED", "OVERDUE"),
    1: (1_000_000, "APPROVED", "WITHIN_LIMIT"),
    2: (2_000_000, "APPROVED", "WITHIN_LIMIT"),
    3: (3_000_000, "APPROVED", "WITHIN_LIMIT"),
    4: (10_000_000, "COUNTER_OFFER", "ABOVE_LIMIT"),
    5: (3_000_000, "MANUAL_REVIEW", "BORDERLINE_SCORE"),
    6: (2_000_000, "NEEDS_INFO", "MISSING_FINANCIALS"),
    7: (1_000_000, "MANUAL_REVIEW", "EXTERNAL_UNAVAILABLE"),
    8: (1_000_000, "REJECTED", "INACTIVE_COMPANY"),
    9: (1_000_000, "MANUAL_REVIEW", "EXTERNAL_UNAVAILABLE"),
}


@pytest.fixture(autouse=True)
def _fresh_limiter_and_today(monkeypatch):
    """Лимит регистрации общий на IP; возраст «9 месяцев» в моках считается от настоящей даты, а не от AS_OF_DATE тестов."""
    reset_login_limiter()
    monkeypatch.setattr("app.domain.decision.engine.as_of_date", lambda: datetime.now(MOSCOW).date())
    yield
    reset_login_limiter()


def register(client, login, inn, password="secret123"):
    return client.post(REGISTER, json={"login": login, "password": password, "inn": inn})


def auth(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_register_returns_login_response_and_profile_from_egrul(client, db):
    inn = SPARE_OOO[2]
    r = register(client, "reg_profile", inn)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] > 0
    assert body["user"]["role"] == "CLIENT"
    assert body["user"]["companyId"]

    company = client.get("/api/v1/companies/me", headers=auth(r)).json()
    assert company["inn"] == inn
    assert company["legalForm"] == "OOO"
    assert company["name"] == f"ООО «Синтетика {inn}»"
    assert len(company["ogrn"]) == 13
    assert company["registrationDate"] == "2014-09-02"
    assert company["legalAddress"]
    assert client.get("/api/v1/auth/me", headers=auth(r)).json()["name"] == company["name"]

    login = client.post("/api/v1/auth/login", json={"login": "reg_profile", "password": "secret123"})
    assert login.status_code == 200
    assert login.json()["user"]["companyId"] == body["user"]["companyId"]
    user = db.scalar(select(AppUser).where(AppUser.login_code == "reg_profile"))
    assert user.password_hash_cval.startswith("$2")


def test_register_individual_entrepreneur_by_twelve_digit_inn(client):
    inn = SPARE_IP[3]
    r = register(client, "reg_ip", inn)
    assert r.status_code == 201, r.text
    company = client.get("/api/v1/companies/me", headers=auth(r)).json()
    assert company["legalForm"] == "IP"
    assert company["name"] == f"ИП Синтетика {inn}"
    assert len(company["ogrn"]) == 15


def test_register_inactive_company_is_allowed(client):
    assert register(client, "reg_inactive", SPARE_OOO[8]).status_code == 201


def test_login_taken(client):
    assert register(client, "reg_taken", SPARE_OOO[1]).status_code == 201
    r = register(client, "reg_taken", SPARE_OOO[2])
    assert r.status_code == 409
    assert r.json()["code"] == "LOGIN_TAKEN"
    assert r.json()["errors"][0]["field"] == "login"
    assert register(client, "client_fast", SPARE_OOO[2]).json()["code"] == "LOGIN_TAKEN"


def test_inn_taken(client):
    assert register(client, "reg_inn_first", SPARE_IP[1]).status_code == 201
    r = register(client, "reg_inn_second", SPARE_IP[1])
    assert r.status_code == 409
    assert r.json()["code"] == "INN_TAKEN"
    assert r.json()["errors"][0]["field"] == "inn"
    # ИНН seed-компании тоже занят
    assert register(client, "reg_inn_seed", "7701000002").json()["code"] == "INN_TAKEN"


def test_invalid_inn_login_and_password_report_all_fields(client):
    r = register(client, "Bad Login!", "7702000051", password="short")
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    by_field = {e["field"]: e for e in body["errors"]}
    assert set(by_field) == {"login", "password", "inn"}
    assert by_field["inn"]["message"] == "Неверная контрольная сумма ИНН"
    assert "8" in by_field["password"]["message"]


@pytest.mark.parametrize(
    ("inn", "message"),
    [
        ("77020000a4", "ИНН состоит только из цифр"),
        ("77020000", "ИНН содержит 10 цифр (организация) или 12 цифр (ИП)"),
    ],
)
def test_inn_format_messages(client, inn, message):
    r = register(client, "reg_bad_inn", inn)
    assert r.status_code == 422
    error = r.json()["errors"][0]
    assert error["field"] == "inn"
    assert error["message"] == message


def test_missing_fields_are_reported(client):
    r = client.post(REGISTER, json={"login": "only_login"})
    assert r.status_code == 422
    assert {e["field"] for e in r.json()["errors"]} == {"password", "inn"}


def test_egrul_unavailable_creates_nothing(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "mocks_base_url", "http://127.0.0.1:9")
    inn = SPARE_OOO[4]
    r = register(client, "reg_no_egrul", inn)
    assert r.status_code == 503
    assert r.json()["code"] == "EGRUL_UNAVAILABLE"
    assert db.scalar(select(func.count()).select_from(Company).where(Company.inn_code == inn)) == 0
    assert (
        db.scalar(select(func.count()).select_from(AppUser).where(AppUser.login_code == "reg_no_egrul")) == 0
    )


def test_register_is_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "register_max_attempts", 3)
    for i in range(3):
        assert register(client, f"reg_rate_{i}", "bad").status_code == 422
    r = register(client, "reg_rate_x", SPARE_OOO[4])
    assert r.status_code == 429
    assert r.json()["code"] == "TOO_MANY_REQUESTS"
    assert int(r.headers["Retry-After"]) > 0


@pytest.mark.parametrize("inns", [OOO_INNS, IP_INNS], ids=["ooo-9th-digit", "ip-10th-digit"])
@pytest.mark.parametrize("digit", range(10))
def test_scenario_by_digit(client, underwriter, inns, digit):
    amount, expected, rule = SCENARIOS[digit]
    reg = register(client, f"scn_{len(inns[digit])}_{digit}", inns[digit])
    assert reg.status_code == 201, reg.text
    flow = Flow(client, auth(reg))
    draft = flow.draft(requestedAmount=amount, termMonths=12, purpose="Проверка на своём ИНН")
    assert flow.submit(draft["id"]).status_code == 202
    application = flow.get(draft["id"])
    assert application["status"] == expected
    screen = client.get(f"/api/v1/underwriter/applications/{application['id']}", headers=underwriter).json()
    assert screen["decisions"][0]["snapshot"]["ruleCode"] == rule

    if expected == "NEEDS_INFO":
        r = client.patch(
            f"/api/v1/applications/{application['id']}/missing-info",
            headers=flow.headers,
            json={"revenueAmount": 12_000_000},
        )
        assert r.status_code == 200, r.text
        assert flow.get(application["id"])["status"] == "APPROVED"


def test_approved_digits_differ_in_limit_and_rate(client, underwriter):
    seen = set()
    for digit in (1, 2, 3):
        reg = register(client, f"scn_diff_{digit}", DIFF_OOO[digit])
        flow = Flow(client, auth(reg))
        draft = flow.draft(requestedAmount=1_000_000, termMonths=12, purpose="Проверка")
        flow.submit(draft["id"])
        a = flow.get(draft["id"])
        assert a["status"] == "APPROVED"
        snapshot = client.get(f"/api/v1/underwriter/applications/{a['id']}", headers=underwriter).json()[
            "decisions"
        ][0]["snapshot"]
        seen.add((str(snapshot["limit"]), str(snapshot["rate"])))
    assert len(seen) == 3
