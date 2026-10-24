"""Повторная проверка источников андеррайтером."""

from sqlalchemy import func, select

from app.db.models import CreditDecision, ExternalCheck
from tests.integration.fakes import GOOD, screen, submit

RECHECK = "/api/v1/underwriter/applications/{}/recheck"


def test_recheck_reruns_pipeline_with_new_checks_and_decision(client, underwriter, flow, external, db):
    external(GOOD, failing=("BKI",))  # как client_timeout: БКИ недоступно
    app = submit(flow, 1_000_000)
    assert app["status"] == "MANUAL_REVIEW"
    first = screen(client, underwriter, app["id"])
    assert first["decisions"][0]["snapshot"]["ruleCode"] == "EXTERNAL_UNAVAILABLE"
    assert "recheck" in first["application"]["availableActions"]
    checks_before = db.scalar(
        select(func.count()).select_from(ExternalCheck).where(ExternalCheck.application_id == app["id"])
    )

    r = client.post(RECHECK.format(app["id"]), headers=underwriter, json={"comment": "Повторяем БКИ"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "MANUAL_REVIEW"  # БКИ всё ещё недоступно

    after = screen(client, underwriter, app["id"])
    db.expire_all()
    checks_after = db.scalar(
        select(func.count()).select_from(ExternalCheck).where(ExternalCheck.application_id == app["id"])
    )
    assert checks_after == checks_before + 3  # новый набор проверок
    assert len(after["decisions"]) == 2 and after["decisions"][0]["type"] == "AUTO"
    assert after["decisions"][0]["id"] != first["decisions"][0]["id"]
    assert after["decisions"][0]["snapshot"]["ruleCode"] == "EXTERNAL_UNAVAILABLE"
    assert (
        db.scalar(
            select(func.count()).select_from(CreditDecision).where(CreditDecision.application_id == app["id"])
        )
        == 2
    )

    audit = client.get(f"/api/v1/applications/{app['id']}/audit", headers=underwriter).json()
    rechecks = [a for a in audit if a["fromStatus"] == "MANUAL_REVIEW" and a["toStatus"] == "EXTERNAL_CHECK"]
    assert len(rechecks) == 1 and "Повторяем БКИ" in rechecks[0]["comment"]
    assert rechecks[0]["userName"]


def test_recheck_with_recovered_source_can_change_outcome(client, underwriter, flow, external):
    external(GOOD, failing=("BKI",))
    app = submit(flow, 1_000_000)
    assert app["status"] == "MANUAL_REVIEW"
    external(GOOD)  # источник восстановился
    r = client.post(RECHECK.format(app["id"]), headers=underwriter, json={"comment": "Источник доступен"})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"


def test_recheck_requires_comment(client, underwriter, flow):
    app = flow.submitted()
    for body in ({}, {"comment": "   "}):
        r = client.post(RECHECK.format(app["id"]), headers=underwriter, json=body)
        assert r.status_code == 422
        assert "comment" in [e["field"] for e in r.json()["errors"]]


def test_recheck_outside_manual_review_is_409(client, underwriter, flow):
    draft = flow.filled_draft()
    r = client.post(RECHECK.format(draft["id"]), headers=underwriter, json={"comment": "рано"})
    assert r.status_code == 409 and r.json()["code"] == "INVALID_TRANSITION"
    assert r.headers["content-type"].startswith("application/problem+json")


def test_recheck_by_client_is_forbidden(client, fast, flow):
    app = flow.submitted()
    r = client.post(RECHECK.format(app["id"]), headers=fast, json={"comment": "сам проверю"})
    assert r.status_code == 403
