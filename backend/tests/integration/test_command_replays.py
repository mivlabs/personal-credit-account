import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.db.models import Disbursement
from tests.integration.conftest import Flow

pytestmark = pytest.mark.live_integrations


def test_concurrent_accept_and_sign_replay_are_atomic(client, fast, db):
    flow = Flow(client, fast)
    draft = flow.draft(requestedAmount=1500000, termMonths=12, purpose="Replay")
    assert flow.submit(draft["id"]).status_code == 202
    base = f"/api/v1/applications/{draft['id']}"
    headers = {**fast, "Idempotency-Key": uuid.uuid4().hex}
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: client.post(base + "/offer/accept", headers=headers), range(2)))
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    headers = {**fast, "Idempotency-Key": uuid.uuid4().hex}
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda _: client.post(base + "/sign", headers=headers, json={"code": "123456"}), range(2)
            )
        )
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    assert (
        db.scalar(
            select(func.count()).select_from(Disbursement).where(Disbursement.application_id == draft["id"])
        )
        == 1
    )
    conflict = client.post(base + "/sign", headers=headers, json={"code": "654321"})
    assert conflict.status_code == 409


def test_failed_sign_not_cached_and_info_replay(client):
    from tests.integration.conftest import login_headers

    headers = login_headers(client, "client_info")
    flow = Flow(client, headers)
    a = flow.draft(requestedAmount=1500000, termMonths=12, purpose="Info replay")
    flow.submit(a["id"])
    base = f"/api/v1/applications/{a['id']}"
    replay = {**headers, "Idempotency-Key": uuid.uuid4().hex}
    first = client.patch(base + "/missing-info", headers=replay, json={"revenueAmount": 12000000})
    second = client.patch(base + "/missing-info", headers=replay, json={"revenueAmount": 12000000})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    client.post(base + "/offer/accept", headers=headers)
    replay = {**headers, "Idempotency-Key": uuid.uuid4().hex}
    assert client.post(base + "/sign", headers=replay, json={"code": "bad"}).status_code == 422
    assert client.post(base + "/sign", headers=replay, json={"code": "123456"}).status_code == 200
