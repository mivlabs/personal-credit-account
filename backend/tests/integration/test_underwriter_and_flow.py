from fastapi.testclient import TestClient

from tests.integration.conftest import Flow

DECISION = "/api/v1/underwriter/applications/{}/decision"


def decide(client: TestClient, headers, app_id: int, **body):
    return client.post(DECISION.format(app_id), headers=headers, json=body)


def test_queue_lists_manual_review_oldest_first_with_context(client: TestClient, underwriter, flow: Flow):
    first = flow.submitted(requestedAmount=2_000_000)
    second = flow.submitted(requestedAmount=4_000_000)

    queue = client.get("/api/v1/underwriter/queue?limit=100", headers=underwriter).json()
    ids = [i["applicationId"] for i in queue["items"]]
    assert ids.index(first["id"]) < ids.index(second["id"])
    item = next(i for i in queue["items"] if i["applicationId"] == first["id"])
    assert item["companyName"] and item["productName"] == "Оборотный кредит"
    assert item["requestedAmount"] == 2_000_000 and item["waitingSeconds"] >= 0
    assert item["queueReason"] and "score" in item
    assert queue["total"] >= 2

    page = client.get("/api/v1/underwriter/queue?limit=1&offset=0", headers=underwriter).json()
    assert len(page["items"]) == 1 and page["limit"] == 1


def test_underwriter_screen_has_application_company_checks_and_decisions(
    client: TestClient, underwriter, flow: Flow
):
    app = flow.submitted()
    r = client.get(f"/api/v1/underwriter/applications/{app['id']}", headers=underwriter)
    assert r.status_code == 200
    body = r.json()
    assert body["application"]["id"] == app["id"]
    assert body["company"]["inn"] == "770100000001"
    assert body["externalChecks"] == []  # внешние проверки пока отключены
    assert body["decisions"][0]["type"] == "AUTO" and body["decisions"][0]["decidedBy"] is None
    assert body["queueReason"]


def test_manual_decision_requires_a_comment(client: TestClient, underwriter, flow: Flow):
    app = flow.submitted()
    for comment in ("", "   "):
        r = decide(client, underwriter, app["id"], outcome="APPROVED", comment=comment)
        assert r.status_code == 422
        assert [e["field"] for e in r.json()["errors"]] == ["comment"]
    r = client.post(DECISION.format(app["id"]), headers=underwriter, json={"outcome": "APPROVED"})
    assert r.status_code == 422
    assert flow.get(app["id"])["status"] == "MANUAL_REVIEW"


def test_counter_offer_and_needs_info_require_their_fields(client: TestClient, underwriter, flow: Flow):
    app = flow.submitted(requestedAmount=3_000_000)
    no_amount = decide(client, underwriter, app["id"], outcome="COUNTER_OFFER", comment="меньше")
    assert [e["field"] for e in no_amount.json()["errors"]] == ["offerAmount"]

    not_less = decide(
        client, underwriter, app["id"], outcome="COUNTER_OFFER", comment="больше", offerAmount=3_000_000
    )
    assert not_less.status_code == 422 and not_less.json()["errors"][0]["code"] == "NOT_LESS_THAN_REQUESTED"

    no_info = decide(client, underwriter, app["id"], outcome="NEEDS_INFO", comment="нужны данные")
    assert [e["field"] for e in no_info.json()["errors"]] == ["infoRequest"]
    assert flow.get(app["id"])["status"] == "MANUAL_REVIEW"


def test_decision_only_for_applications_in_manual_review(client: TestClient, underwriter, flow: Flow):
    draft = flow.filled_draft()
    r = decide(client, underwriter, draft["id"], outcome="APPROVED", comment="рано")
    assert r.status_code == 409 and r.json()["code"] == "INVALID_TRANSITION"

    app = flow.submitted()
    assert decide(client, underwriter, app["id"], outcome="REJECTED", comment="нет").status_code == 200
    again = decide(client, underwriter, app["id"], outcome="APPROVED", comment="передумал")
    assert again.status_code == 409 and again.json()["code"] == "INVALID_TRANSITION"


def test_full_path_to_issued(client: TestClient, fast, underwriter, flow: Flow):
    app = flow.submitted(requestedAmount=1_500_000, termMonths=24)
    app_id = app["id"]

    approved = decide(
        client,
        underwriter,
        app_id,
        outcome="APPROVED",
        comment="Выручка подтверждена",
        clientReason="Стабильная выручка",
    ).json()
    assert approved["status"] == "APPROVED"
    assert approved["decision"] == {
        **approved["decision"],
        "outcome": "APPROVED",
        "reason": "Стабильная выручка",
    }
    offer = approved["offer"]
    assert (offer["amount"], offer["termMonths"], offer["rate"], offer["status"]) == (
        1_500_000,
        24,
        17.5,  # ключевая 14.0 + спред 2.5 + риск-надбавка 1.0 (у ручного решения нет балла)
        "SENT",
    )
    assert offer["monthlyPayment"] > 0

    accepted = client.post(f"/api/v1/applications/{app_id}/offer/accept", headers=fast)
    assert accepted.status_code == 200
    assert accepted.json()["application"]["status"] == "SIGNING"
    assert "123456" in accepted.json()["signHint"]

    wrong = client.post(f"/api/v1/applications/{app_id}/sign", headers=fast, json={"code": "000000"})
    assert wrong.status_code == 422 and [e["field"] for e in wrong.json()["errors"]] == ["code"]
    assert flow.get(app_id)["status"] == "SIGNING"

    signed = client.post(f"/api/v1/applications/{app_id}/sign", headers=fast, json={"code": "123456"}).json()
    assert signed["status"] == "ISSUED" and signed["statusName"] == "Кредит выдан"
    assert signed["offer"]["status"] == "SIGNED" and signed["offer"]["signedAt"]

    audit = client.get(f"/api/v1/applications/{app_id}/audit", headers=underwriter).json()
    transitions = [(a["fromStatus"], a["toStatus"]) for a in audit]
    assert transitions[-4:] == [
        ("MANUAL_REVIEW", "APPROVED"),
        ("APPROVED", "OFFER_ACCEPTED"),
        ("OFFER_ACCEPTED", "SIGNING"),
        ("SIGNING", "ISSUED"),
    ]
    by_to = {a["toStatus"]: a for a in audit}
    assert by_to["APPROVED"]["userName"] == "Петрова Елена Андреевна"
    assert by_to["APPROVED"]["comment"] == "Выручка подтверждена"
    assert by_to["SUBMITTED"]["userName"] == "Соколов Андрей Викторович"
    assert by_to["CHECKING"]["userId"] is None  # системный переход
    assert "1 500 000" in by_to["ISSUED"]["comment"]  # дата и сумма выдачи в истории


def test_counter_offer_can_be_accepted_with_smaller_amount(client: TestClient, fast, underwriter, flow: Flow):
    app = flow.submitted(requestedAmount=10_000_000, termMonths=24)
    r = decide(
        client, underwriter, app["id"], outcome="COUNTER_OFFER", comment="Лимит ниже", offerAmount=6_000_000
    )
    body = r.json()
    assert body["status"] == "COUNTER_OFFER" and body["offer"]["amount"] == 6_000_000
    assert body["requestedAmount"] == 10_000_000  # клиент видит, сколько просил и сколько предлагают

    accepted = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=fast).json()
    assert accepted["application"]["status"] == "SIGNING"


def test_client_can_decline_offer(client: TestClient, fast, underwriter, flow: Flow):
    app = flow.submitted()
    decide(client, underwriter, app["id"], outcome="APPROVED", comment="ок")
    r = client.post(f"/api/v1/applications/{app['id']}/offer/decline", headers=fast)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "DECLINED_BY_CLIENT" and body["offer"]["status"] == "DECLINED"
    again = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=fast)
    assert again.status_code == 409 and again.json()["code"] == "INVALID_TRANSITION"


def test_rejection_shows_reason_without_internals(client: TestClient, underwriter, flow: Flow):
    app = flow.submitted()
    r = decide(
        client,
        underwriter,
        app["id"],
        outcome="REJECTED",
        comment="внутренний комментарий андеррайтера",
        clientReason="Долговая нагрузка выше допустимой",
    ).json()
    assert r["status"] == "REJECTED"
    assert r["decision"]["reason"] == "Долговая нагрузка выше допустимой"
    assert "внутренний" not in str(r)  # комментарий андеррайтера клиенту не отдаётся
    assert r["offer"] is None


def test_needs_info_roundtrip_restarts_pipeline(client: TestClient, fast, underwriter, flow: Flow):
    app = flow.submitted()
    r = decide(
        client,
        underwriter,
        app["id"],
        outcome="NEEDS_INFO",
        comment="Нет подтверждения выручки",
        infoRequest={"description": "Укажите годовую выручку", "fields": ["revenueAmount"]},
    ).json()
    assert r["status"] == "NEEDS_INFO"
    (request,) = r["openInfoRequests"]
    assert request["fields"] == ["revenueAmount"] and request["status"] == "OPEN"

    tl = client.get(f"/api/v1/applications/{app['id']}/timeline", headers=fast).json()
    review = next(s for s in tl["stages"] if s["code"] == "REVIEW")
    assert review["actionRequired"] is True

    extra = client.patch(
        f"/api/v1/applications/{app['id']}/missing-info",
        headers=fast,
        json={"revenueAmount": 9_000_000, "purpose": "иное"},
    )
    assert extra.status_code == 422
    assert {e["field"]: e["code"] for e in extra.json()["errors"]} == {"purpose": "NOT_REQUESTED"}

    empty = client.patch(f"/api/v1/applications/{app['id']}/missing-info", headers=fast, json={})
    assert empty.status_code == 422 and empty.json()["errors"][0]["code"] == "REQUIRED"

    answered = client.patch(
        f"/api/v1/applications/{app['id']}/missing-info", headers=fast, json={"revenueAmount": 9_000_000}
    )
    assert answered.status_code == 200
    final = flow.get(app["id"])
    assert final["revenueAmount"] == 9_000_000 and final["openInfoRequests"] == []
    assert final["status"] == "MANUAL_REVIEW"  # конвейер перезапущен и дошёл до итога заново
    path = [h["toStatus"] for h in final["history"]]
    assert path[-5:] == ["NEEDS_INFO", "CHECKING", "EXTERNAL_CHECK", "SCORING", "MANUAL_REVIEW"]

    again = client.patch(
        f"/api/v1/applications/{app['id']}/missing-info", headers=fast, json={"revenueAmount": 1}
    )
    assert again.status_code == 409 and again.json()["code"] == "INVALID_TRANSITION"


def test_sign_hint_only_in_demo_mode(client: TestClient, underwriter, flow: Flow, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_mode", False)
    app = flow.submitted(requestedAmount=1_500_000, termMonths=24)
    decide(client, underwriter, app["id"], outcome="APPROVED", comment="ok", clientReason="ok")
    accepted = client.post(f"/api/v1/applications/{app['id']}/offer/accept", headers=flow.headers)
    assert accepted.status_code == 200
    assert accepted.json().get("signHint") is None
    assert "123456" not in accepted.text
