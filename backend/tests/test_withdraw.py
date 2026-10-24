"""Отзыв заявки клиентом."""

import uuid

from tests.fakes import GOOD, submit


def withdraw(client, headers, app_id, key=None, **body):
    h = {**headers, **({"Idempotency-Key": key} if key else {})}
    return client.post(f"/api/v1/applications/{app_id}/withdraw", headers=h, json=body or None)


def queue_ids(client, underwriter):
    items = client.get("/api/v1/underwriter/queue?limit=100", headers=underwriter).json()["items"]
    return [i["applicationId"] for i in items]


def test_withdraw_draft(client, fast, underwriter, flow):
    draft = flow.filled_draft()
    assert "withdraw" in draft["availableActions"]
    r = withdraw(client, fast, draft["id"], reason="Передумали")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "WITHDRAWN" and body["statusName"] == "Заявка отозвана"
    assert body["availableActions"] == []
    audit = client.get(f"/api/v1/applications/{draft['id']}/audit", headers=underwriter).json()
    assert "Передумали" in audit[-1]["comment"]
    # финальный статус: править и подавать нельзя
    patch = client.patch(f"/api/v1/applications/{draft['id']}", headers=fast, json={"purpose": "x"})
    assert patch.status_code == 409
    assert flow.submit(draft["id"]).status_code == 409


def test_withdraw_in_manual_review_removes_from_default_queue(client, fast, underwriter, flow):
    app = flow.submitted()
    assert app["status"] == "MANUAL_REVIEW" and "withdraw" in app["availableActions"]
    assert app["id"] in queue_ids(client, underwriter)
    r = withdraw(client, fast, app["id"])  # без тела
    assert r.status_code == 200 and r.json()["status"] == "WITHDRAWN"
    assert app["id"] not in queue_ids(client, underwriter)
    # андеррайтер не может решать по отозванной заявке
    d = client.post(
        f"/api/v1/underwriter/applications/{app['id']}/decision",
        headers=underwriter,
        json={"outcome": "APPROVED", "comment": "поздно"},
    )
    assert d.status_code == 409


def test_withdraw_in_needs_info_hides_open_requests(client, fast, flow, external):
    external({**GOOD, "FNS": {"annualRevenue": None}})
    app = submit(flow, 1_000_000)
    assert app["status"] == "NEEDS_INFO" and app["openInfoRequests"]
    r = withdraw(client, fast, app["id"], reason="Не готовы")
    assert r.status_code == 200
    assert r.json()["status"] == "WITHDRAWN" and r.json()["openInfoRequests"] == []


def test_withdraw_after_offer_is_not_allowed(client, fast, flow, external):
    external(GOOD)
    app = submit(flow, 1_000_000)
    assert app["status"] == "APPROVED"
    r = withdraw(client, fast, app["id"])
    assert r.status_code == 409 and r.json()["code"] == "INVALID_TRANSITION"
    # для оффера остаётся существующий отказ
    d = client.post(f"/api/v1/applications/{app['id']}/offer/decline", headers=fast)
    assert d.status_code == 200 and d.json()["status"] == "DECLINED_BY_CLIENT"
    assert withdraw(client, fast, app["id"]).status_code == 409


def test_withdraw_idempotent_replay_and_key_conflict(client, fast, flow):
    draft = flow.filled_draft()
    key = uuid.uuid4().hex
    first = withdraw(client, fast, draft["id"], key, reason="a")
    assert first.status_code == 200
    again = withdraw(client, fast, draft["id"], key, reason="a")
    assert again.status_code == 200 and again.json() == first.json()
    other_body = withdraw(client, fast, draft["id"], key, reason="b")
    assert other_body.status_code == 409 and other_body.json()["code"] == "IDEMPOTENCY_CONFLICT"
    # без ключа повтор отклоняется состоянием
    assert withdraw(client, fast, draft["id"]).status_code == 409


def test_withdraw_foreign_application_unknown_and_underwriter(client, other_client, underwriter, fast, flow):
    draft = flow.filled_draft()
    assert withdraw(client, other_client, draft["id"]).status_code == 404
    assert withdraw(client, underwriter, draft["id"]).status_code == 403
    assert withdraw(client, fast, 999999999).status_code == 404
