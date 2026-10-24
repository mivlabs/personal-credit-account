import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.db.models import CreditDecision, ExternalCheck
from tests.integration.conftest import Flow, login_headers

pytestmark = pytest.mark.live_integrations


@pytest.mark.parametrize(
    ("login", "amount", "expected"),
    [
        ("client_fast", 1500000, "APPROVED"),
        ("client_counter", 10000000, "COUNTER_OFFER"),
        ("client_manual", 1500000, "MANUAL_REVIEW"),
        ("client_info", 1500000, "NEEDS_INFO"),
        ("client_reject", 1500000, "REJECTED"),
        ("client_timeout", 1500000, "MANUAL_REVIEW"),
    ],
)
def test_real_wiremock_five_outcomes(client, underwriter, db, login, amount, expected):
    headers = login_headers(client, login)
    flow = Flow(client, headers)
    draft = flow.draft(requestedAmount=amount, termMonths=12, purpose="Demo")
    key = uuid.uuid4().hex
    response = flow.submit(draft["id"], key)
    assert response.status_code == 202, response.text
    a = flow.get(draft["id"])
    assert a["status"] == expected
    screen = client.get(f"/api/v1/underwriter/applications/{a['id']}", headers=underwriter).json()
    assert len(screen["externalChecks"]) >= 3
    assert screen["decisions"][0]["snapshot"]["ruleCode"]
    if expected == "NEEDS_INFO":
        r = client.patch(
            f"/api/v1/applications/{a['id']}/missing-info", headers=headers, json={"revenueAmount": 12000000}
        )
        assert r.status_code == 200, r.text
        assert flow.get(a["id"])["status"] == "APPROVED"
        assert flow.get(a["id"])["revenueAmount"] == 12000000
        assert (
            len(
                client.get(f"/api/v1/underwriter/applications/{a['id']}", headers=underwriter).json()[
                    "externalChecks"
                ]
            )
            == 6
        )
    else:
        assert flow.submit(a["id"], key).status_code == 200
        assert (
            db.scalar(
                select(func.count())
                .select_from(CreditDecision)
                .where(CreditDecision.application_id == a["id"])
            )
            == 1
        )
    if expected in ("APPROVED", "COUNTER_OFFER"):
        assert (
            client.post(
                f"/api/v1/applications/{a['id']}/sign", headers=headers, json={"code": "123456"}
            ).status_code
            == 409
        )
        assert client.post(f"/api/v1/applications/{a['id']}/offer/accept", headers=headers).status_code == 200
        assert (
            client.post(
                f"/api/v1/applications/{a['id']}/sign", headers=headers, json={"code": "123456"}
            ).json()["status"]
            == "ISSUED"
        )
        assert (
            client.post(
                f"/api/v1/applications/{a['id']}/sign", headers=headers, json={"code": "123456"}
            ).status_code
            == 409
        )


def test_concurrent_submission_creates_one_decision_and_check_set(client, fast, db):
    flow = Flow(client, fast)
    a = flow.draft(requestedAmount=1500000, termMonths=12, purpose="Concurrency")
    key = uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: flow.submit(a["id"], key), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 202]
    assert (
        db.scalar(
            select(func.count()).select_from(ExternalCheck).where(ExternalCheck.application_id == a["id"])
        )
        == 3
    )
    assert (
        db.scalar(
            select(func.count()).select_from(CreditDecision).where(CreditDecision.application_id == a["id"])
        )
        == 1
    )


def test_real_wiremock_client_timeout_recheck_creates_new_checks(client, underwriter):
    headers = login_headers(client, "client_timeout")
    flow = Flow(client, headers)
    draft = flow.draft(requestedAmount=1500000, termMonths=12, purpose="Demo")
    assert flow.submit(draft["id"]).status_code == 202
    assert flow.get(draft["id"])["status"] == "MANUAL_REVIEW"
    before = client.get(f"/api/v1/underwriter/applications/{draft['id']}", headers=underwriter).json()
    r = client.post(
        f"/api/v1/underwriter/applications/{draft['id']}/recheck",
        headers=underwriter,
        json={"comment": "Повторная проверка БКИ"},
    )
    assert r.status_code == 200 and r.json()["status"] == "MANUAL_REVIEW"  # БКИ по-прежнему отвечает 503
    after = client.get(f"/api/v1/underwriter/applications/{draft['id']}", headers=underwriter).json()
    assert len(after["externalChecks"]) > len(before["externalChecks"])
    assert len(after["decisions"]) == len(before["decisions"]) + 1
