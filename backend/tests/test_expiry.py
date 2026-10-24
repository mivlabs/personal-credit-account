"""Сроки жизни оффера и запроса данных, ленивое истечение и скрипт expire_stale."""

import uuid
from datetime import datetime

import pytest

from app.db.session import get_sessionmaker
from app.services.expiry import expire_all_stale
from tests.fakes import GOOD, submit

NO_REVENUE = {**GOOD, "FNS": {"annualRevenue": None}}


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def days_until(value: str) -> float:
    return (parse(value) - datetime.now(parse(value).tzinfo)).total_seconds() / 86400


def approved(flow, external, amount=1_000_000):
    external(GOOD)
    app = submit(flow, amount)
    assert app["status"] == "APPROVED"
    return app


def needs_info(flow, external):
    external(NO_REVENUE)
    app = submit(flow, 1_000_000)
    assert app["status"] == "NEEDS_INFO"
    return app


def audit(client, headers, app_id):
    return client.get(f"/api/v1/applications/{app_id}/audit", headers=headers).json()


def test_deadlines_are_exposed(flow, external):
    offer = approved(flow, external)["offer"]
    assert 29.9 < days_until(offer["validUntil"]) < 30.1
    request = needs_info(flow, external)["openInfoRequests"][0]
    assert 13.9 < days_until(request["dueAt"]) < 14.1


def test_not_yet_expired_flow_still_works(client, fast, flow, external, travel):
    app = approved(flow, external)
    travel(29)  # оффер действует 30 дней
    r = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=fast)
    assert r.status_code == 200, r.text
    travel(365)  # принятый оффер дальше не истекает: подпись остаётся доступной
    sign = client.post(f"/api/v1/applications/{app['id']}/sign", headers=fast, json={"code": "123456"})
    assert sign.status_code == 200 and sign.json()["status"] == "ISSUED"


@pytest.mark.parametrize("command", ["accept", "decline"])
def test_expired_offer_returns_409_and_closes_application(
    client, fast, underwriter, flow, external, travel, command
):
    app = approved(flow, external)
    travel(31)
    r = client.post(f"/api/v1/applications/{app['id']}/offer/{command}", headers=fast)
    assert r.status_code == 409 and r.json()["code"] == "EXPIRED"
    assert r.headers["content-type"].startswith("application/problem+json")
    # переход не откатился вместе с ошибкой
    assert flow.get(app["id"])["status"] == "EXPIRED"
    last = audit(client, underwriter, app["id"])[-1]
    assert (last["fromStatus"], last["toStatus"], last["userId"]) == ("APPROVED", "EXPIRED", None)
    assert "истёк" in last["comment"]
    again = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=fast)
    assert again.status_code == 409 and again.json()["code"] == "INVALID_TRANSITION"


def test_expired_counter_offer(client, fast, flow, external, travel):
    external(GOOD)
    app = submit(flow, 10_000_000)
    assert app["status"] == "COUNTER_OFFER"
    travel(31)
    r = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=fast)
    assert r.status_code == 409 and r.json()["code"] == "EXPIRED"
    assert flow.get(app["id"])["status"] == "EXPIRED"


def test_expired_with_idempotency_key_is_not_rolled_back(client, fast, flow, external, travel):
    app = approved(flow, external)
    travel(31)
    headers = {**fast, "Idempotency-Key": uuid.uuid4().hex}
    r = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "EXPIRED"
    assert flow.get(app["id"])["status"] == "EXPIRED"


def test_expired_info_request(client, fast, flow, external, travel):
    app = needs_info(flow, external)
    travel(15)
    r = client.patch(
        f"/api/v1/applications/{app['id']}/missing-info", headers=fast, json={"revenueAmount": 12_000_000}
    )
    assert r.status_code == 409 and r.json()["code"] == "EXPIRED"
    got = flow.get(app["id"])
    assert got["status"] == "EXPIRED" and got["statusName"] == "Срок истёк"
    assert got["openInfoRequests"] == []


def test_info_request_answered_in_time_still_works(client, fast, flow, external, travel):
    app = needs_info(flow, external)
    travel(13)
    external(GOOD)
    r = client.patch(
        f"/api/v1/applications/{app['id']}/missing-info", headers=fast, json={"revenueAmount": 12_000_000}
    )
    assert r.status_code == 200, r.text


def test_expire_stale_script_closes_only_stale(client, flow, external, travel):
    stale_offer = approved(flow, external)
    stale_info = needs_info(flow, external)
    manual = flow.submitted()  # MANUAL_REVIEW без сроков не трогаем
    travel(40)
    assert expire_all_stale(get_sessionmaker()) >= 2
    assert flow.get(stale_offer["id"])["status"] == "EXPIRED"
    assert flow.get(stale_info["id"])["status"] == "EXPIRED"
    assert flow.get(manual["id"])["status"] == "MANUAL_REVIEW"
    assert expire_all_stale(get_sessionmaker()) == 0  # повторный запуск ничего не делает


def test_script_does_not_touch_fresh_applications(flow, external):
    app = approved(flow, external)
    expire_all_stale(get_sessionmaker())
    assert flow.get(app["id"])["status"] == "APPROVED"
