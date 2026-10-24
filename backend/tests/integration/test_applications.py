import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import LoanApplication, LoanApplicationAud
from tests.integration.conftest import Flow


def field_errors(response) -> dict[str, str]:
    return {e["field"]: e["code"] for e in response.json()["errors"]}


def test_create_draft_and_continue_from_saved_step(client: TestClient, fast, flow: Flow):
    draft = flow.draft(requestedAmount=1_500_000, draftStep=2)
    assert draft["status"] == "DRAFT" and draft["statusName"] == "Черновик"
    assert draft["draftStep"] == 2 and draft["requestedAmount"] == 1_500_000
    assert [(h["fromStatus"], h["toStatus"]) for h in draft["history"]] == [(None, "DRAFT")]

    r = client.patch(
        f"/api/v1/applications/{draft['id']}",
        headers=fast,
        json={"termMonths": 24, "purpose": "Станок", "draftStep": 3},
    )
    assert r.status_code == 200
    assert (r.json()["termMonths"], r.json()["draftStep"]) == (24, 3)
    assert r.json()["requestedAmount"] == 1_500_000  # не затронуто частичным PATCH

    mine = client.get("/api/v1/applications", headers=fast).json()
    item = next(a for a in mine if a["id"] == draft["id"])
    assert item["status"] == "DRAFT" and item["draftStep"] == 3 and item["actionRequired"] is True


def test_submit_validates_required_fields_and_product_ranges(client: TestClient, flow: Flow):
    empty = flow.draft()
    r = flow.submit(empty["id"])
    assert r.status_code == 422
    assert field_errors(r) == {"requestedAmount": "REQUIRED", "termMonths": "REQUIRED", "purpose": "REQUIRED"}

    out_of_range = flow.filled_draft(
        requestedAmount=50_000, termMonths=100
    )  # WORKING_CAPITAL: 300k–10M, 3–36 мес.
    r = flow.submit(out_of_range["id"])
    assert r.status_code == 422
    assert field_errors(r) == {"requestedAmount": "OUT_OF_RANGE", "termMonths": "OUT_OF_RANGE"}
    assert "300 000" in r.json()["errors"][0]["message"]
    assert flow.get(out_of_range["id"])["status"] == "DRAFT"  # ошибка не сдвинула статус


def test_submit_moves_application_through_pipeline_to_manual_review(flow: Flow):
    app = flow.submitted()
    assert app["status"] == "MANUAL_REVIEW"
    assert [h["toStatus"] for h in app["history"]] == [
        "DRAFT",
        "SUBMITTED",
        "CHECKING",
        "EXTERNAL_CHECK",
        "SCORING",
        "MANUAL_REVIEW",
    ]
    assert app["decision"]["outcome"] == "MANUAL_REVIEW"
    assert app["decision"]["reason"] == "Данные проверит специалист банка"
    assert "score" not in app["decision"]  # клиент не видит баллов


def test_idempotent_submit_same_key_returns_same_application(client: TestClient, flow: Flow, db: Session):
    draft = flow.filled_draft()
    key = uuid.uuid4().hex

    first = flow.submit(draft["id"], key)
    second = flow.submit(draft["id"], key)
    third = flow.submit(draft["id"], key)

    assert (first.status_code, second.status_code, third.status_code) == (202, 200, 200)
    assert {first.json()["id"], second.json()["id"], third.json()["id"]} == {draft["id"]}
    submitted_transitions = db.scalar(
        select(func.count())
        .select_from(LoanApplicationAud)
        .where(
            LoanApplicationAud.application_id == draft["id"], LoanApplicationAud.to_status_code == "SUBMITTED"
        )
    )
    assert submitted_transitions == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(LoanApplication)
            .where(LoanApplication.idempotency_key_code == key)
        )
        == 1
    )


def test_conflicting_idempotency_keys(flow: Flow):
    a, b = flow.filled_draft(), flow.filled_draft()
    key = uuid.uuid4().hex
    assert flow.submit(a["id"], key).status_code == 202

    other_key = flow.submit(a["id"], uuid.uuid4().hex)  # уже поданная заявка, другой ключ
    assert other_key.status_code == 409 and other_key.json()["code"] == "IDEMPOTENCY_CONFLICT"

    reused = flow.submit(b["id"], key)  # тот же ключ на другую заявку
    assert reused.status_code == 409 and reused.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert flow.get(b["id"])["status"] == "DRAFT"


def test_submit_requires_idempotency_key_header(client: TestClient, fast, flow: Flow):
    draft = flow.filled_draft()
    r = client.post(f"/api/v1/applications/{draft['id']}/submit", headers=fast)
    assert r.status_code == 422
    assert field_errors(r) == {"Idempotency-Key": "missing"}


def test_draft_cannot_be_edited_after_submit(client: TestClient, fast, flow: Flow):
    app = flow.submitted()
    r = client.patch(f"/api/v1/applications/{app['id']}", headers=fast, json={"purpose": "поздно"})
    assert r.status_code == 409
    assert r.json()["code"] == "INVALID_TRANSITION"
    assert flow.get(app["id"])["purpose"] != "поздно"


def test_timeline_shows_done_current_upcoming_and_action_required(client: TestClient, fast, flow: Flow):
    draft = flow.filled_draft()
    tl = client.get(f"/api/v1/applications/{draft['id']}/timeline", headers=fast).json()
    assert [(s["code"], s["state"]) for s in tl["stages"]] == [
        ("DRAFT", "current"),
        ("SUBMITTED", "upcoming"),
        ("REVIEW", "upcoming"),
        ("DECISION", "upcoming"),
        ("SIGNING", "upcoming"),
        ("ISSUED", "upcoming"),
    ]
    assert tl["stages"][0]["actionRequired"] is True

    app = flow.submitted()
    tl = client.get(f"/api/v1/applications/{app['id']}/timeline", headers=fast).json()
    states = {s["code"]: s for s in tl["stages"]}
    assert states["DRAFT"]["state"] == states["SUBMITTED"]["state"] == "done"
    assert states["REVIEW"]["state"] == "current" and states["REVIEW"]["actionRequired"] is False
    assert states["REVIEW"]["enteredAt"] is not None and states["DECISION"]["enteredAt"] is None
    assert tl["currentStatus"] == "MANUAL_REVIEW"
    assert len(tl["history"]) == 6 and tl["history"][-1]["toStatusName"] == "На рассмотрении у специалиста"


def test_draft_rejects_non_positive_amount(client: TestClient, fast):
    r = client.post(
        "/api/v1/applications", headers=fast, json={"productCode": "OVERDRAFT", "requestedAmount": 0}
    )
    assert r.status_code == 422 and field_errors(r) == {"requestedAmount": "greater_than"}


def test_direct_status_patch_is_rejected(client, fast, flow):
    draft = flow.filled_draft()
    response = client.patch(f"/api/v1/applications/{draft['id']}", headers=fast, json={"status": "APPROVED"})
    assert response.status_code == 422
    assert flow.get(draft["id"])["status"] == "DRAFT"


def test_unexpected_pipeline_failure_rolls_back_submission(client, fast, flow, monkeypatch):
    draft = flow.filled_draft()
    key = uuid.uuid4().hex

    def fail(*args):
        raise RuntimeError("Injected technical failure")

    with monkeypatch.context() as patch:
        patch.setattr("app.domain.pipeline.decide", fail)
        assert flow.submit(draft["id"], key).status_code == 500
    current = flow.get(draft["id"])
    assert current["status"] == "DRAFT" and current["decision"] is None
    assert [h["toStatus"] for h in current["history"]] == ["DRAFT"]
    assert flow.submit(draft["id"], key).status_code == 202
