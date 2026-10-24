"""Снимок решения, клиентское объяснение, ручное решение выше лимита, бэкфилл миграции."""

import importlib.util
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text

from app.db.models import CreditDecision, ExternalCheck
from app.domain.enums import CheckSource, CheckStatus
from app.integrations.base import ExternalData, SourceResult
from tests.conftest import BACKEND_DIR, Flow

DECISION = "/api/v1/underwriter/applications/{}/decision"
SECRET = "СЕКРЕТНЫЙ-ВНУТРЕННИЙ-КОММЕНТАРИЙ"


def egrul(registered="2016-03-14", industry="services"):
    return {"active": True, "registrationDate": registered, "industry": industry}


GOOD = {"EGRUL": egrul(), "FNS": {"annualRevenue": "12000000"}, "BKI": {"debtAmount": "0", "overdueDays": 0}}
# балл 50 (ручная проверка), лимит 0
BORDERLINE = {
    "EGRUL": egrul("2026-01-23", "construction"),
    "FNS": {"annualRevenue": "6000000"},
    "BKI": {"debtAmount": "3000000", "overdueDays": 30},
}
# балл 50 (ручная проверка), лимит 3 млн
BORDERLINE_LIMIT = {
    "EGRUL": egrul("2026-01-23", "other"),
    "FNS": {"annualRevenue": "12000000"},
    "BKI": {"debtAmount": "3000000", "overdueDays": 60},
}


class FakeChecks:
    payloads: dict = GOOD

    def __init__(self, session=None):
        self.session = session

    def fetch_all(self, application_id, company):
        results = {}
        for source in CheckSource:
            data = self.payloads[source.value]
            now = datetime.now(UTC)
            self.session.add(
                ExternalCheck(
                    application_id=application_id,
                    source_code=source.value,
                    check_status_code=CheckStatus.OK.value,
                    response_cval=json.dumps(data),
                    request_dttm=now,
                    response_dttm=now,
                )
            )
            results[source] = SourceResult(source, CheckStatus.OK, data)
        return ExternalData(results)


@pytest.fixture
def external(monkeypatch):
    def use(payloads):
        monkeypatch.setattr(FakeChecks, "payloads", payloads)
        monkeypatch.setattr("app.domain.pipeline.get_external_checks_client", FakeChecks)

    return use


def submit(flow: Flow, amount=3_000_000, **extra) -> dict:
    draft = flow.draft(requestedAmount=amount, termMonths=12, purpose="Тест", **extra)
    assert flow.submit(draft["id"]).status_code == 202
    return flow.get(draft["id"])


def screen(client, underwriter, app_id) -> dict:
    return client.get(f"/api/v1/underwriter/applications/{app_id}", headers=underwriter).json()


SCENARIOS = {
    "APPROVED": (GOOD, 3_000_000, "WITHIN_LIMIT"),
    "COUNTER_OFFER": (GOOD, 10_000_000, "ABOVE_LIMIT"),
    "MANUAL_REVIEW": (BORDERLINE, 1_000_000, "BORDERLINE_SCORE"),
    "NEEDS_INFO": ({**GOOD, "FNS": {"annualRevenue": None}}, 1_000_000, "MISSING_FINANCIALS"),
    "REJECTED": ({**GOOD, "BKI": {"debtAmount": "0", "overdueDays": 120}}, 1_000_000, "OVERDUE"),
}


@pytest.mark.parametrize("outcome", list(SCENARIOS))
def test_snapshot_is_written_for_all_five_outcomes(client, underwriter, flow, external, outcome):
    payloads, amount, rule = SCENARIOS[outcome]
    external(payloads)
    app = submit(flow, amount)
    assert app["status"] == outcome
    d = screen(client, underwriter, app["id"])["decisions"][0]
    snap = d["snapshot"]
    assert d["comment"] is None  # дамп конфига больше не пишется в комментарий
    assert snap["ruleCode"] == rule and snap["policyVersion"] and snap["asOfDate"] == "2026-10-23"
    assert snap["thresholds"] == {"approve": 70, "reject": 40}
    assert {c["source"] for c in snap["externalChecks"]} == {"EGRUL", "FNS", "BKI"}
    assert all(c["status"] == "OK" and c["requestedAt"] for c in snap["externalChecks"])
    for key in ("annualRevenue", "debtAmount", "overdueDays", "registrationDate", "active", "industry"):
        assert set(snap["inputs"][key]) == {"value", "source", "status"}
    assert snap["inputs"]["registrationDate"]["source"] == "EGRUL"
    if outcome in ("APPROVED", "COUNTER_OFFER", "MANUAL_REVIEW"):
        assert snap["score"] == d["score"]
        assert len(snap["factors"]) == 5
        assert all(
            {"code", "label", "value", "points", "maxPoints", "explanation"} <= set(f)
            for f in snap["factors"]
        )
        assert sum(f["points"] for f in snap["factors"]) == snap["score"]
        assert set(snap["limit"]) == {"value", "formula", "components"}
        assert set(snap["limit"]["components"]) == {"revenueShare", "debtShare", "productMax"}
    else:
        assert snap["factors"] == [] and snap["limit"] is None
    if outcome in ("APPROVED", "COUNTER_OFFER"):
        assert float(snap["rate"]["total"]) == app["offer"]["rate"]
        assert app["offer"]["rateBreakdown"]["total"] == app["offer"]["rate"]
    else:
        assert snap["rate"] is None


def test_client_gets_explanation_without_internal_comment(client, underwriter, flow, external):
    external(BORDERLINE)
    app = submit(flow, 1_000_000)
    assert app["status"] == "MANUAL_REVIEW"
    auto = app["decisionExplanation"]
    assert auto["ruleText"] and not auto["decidedBySpecialist"]
    assert {f["impact"] for f in auto["factors"]} <= {"STRENGTH", "WEAKNESS"}
    assert {f["impactLabel"] for f in auto["factors"]} <= {"сильная сторона", "снижает оценку"}
    assert any(i["code"] == "annualRevenue" and i["sourceName"] == "ФНС" for i in auto["inputs"])
    assert auto["thresholds"] == {"approve": 70, "reject": 40}
    assert "rules" not in auto

    r = client.post(
        DECISION.format(app["id"]),
        headers=underwriter,
        json={"outcome": "REJECTED", "comment": SECRET, "clientReason": "Нет"},
    )
    assert r.status_code == 200, r.text
    for body in (r.text, json.dumps(flow.get(app["id"]), ensure_ascii=False)):
        assert SECRET not in body
    manual = flow.get(app["id"])["decisionExplanation"]
    assert manual["decidedBySpecialist"] is True and manual["factors"]  # факторы из AUTO-снимка
    # внутренний комментарий виден только в панели банка
    mine = screen(client, underwriter, app["id"])["decisions"][0]
    assert mine["comment"] == SECRET and mine["snapshot"]["comment"] == SECRET
    assert mine["snapshot"]["decidedBy"]["name"]


def test_manual_above_limit_requires_override(client, underwriter, flow, external):
    external(BORDERLINE_LIMIT)  # лимит 3 000 000
    app = submit(flow, 4_000_000)
    assert app["status"] == "MANUAL_REVIEW"
    assert screen(client, underwriter, app["id"])["autoLimit"] == 3_000_000

    r = client.post(
        DECISION.format(app["id"]), headers=underwriter, json={"outcome": "APPROVED", "comment": "ок"}
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    err = r.json()["errors"][0]
    assert err["field"] == "overrideLimit" and "лимит" in err["message"]

    over = client.post(
        DECISION.format(app["id"]),
        headers=underwriter,
        json={"outcome": "COUNTER_OFFER", "comment": "ок", "offerAmount": 3_500_000},
    )
    assert over.status_code == 422 and over.json()["errors"][0]["field"] == "overrideLimit"

    ok = client.post(
        DECISION.format(app["id"]),
        headers=underwriter,
        json={"outcome": "APPROVED", "comment": "Подтверждено выпиской", "overrideLimit": True},
    )
    assert ok.status_code == 200, ok.text
    snap = screen(client, underwriter, app["id"])["decisions"][0]["snapshot"]
    assert snap["limitExceeded"] is True and snap["overrideLimit"] is True and snap["limitUnknown"] is False
    assert snap["autoLimit"] == "3000000.00"
    audit = client.get(f"/api/v1/applications/{app["id"]}/audit", headers=underwriter).json()
    assert "overrideLimit" in audit[-1]["comment"]


def test_manual_within_limit_needs_no_override(client, underwriter, flow, external):
    external(BORDERLINE_LIMIT)
    app = submit(flow, 2_000_000)
    r = client.post(
        DECISION.format(app["id"]), headers=underwriter, json={"outcome": "APPROVED", "comment": "ок"}
    )
    assert r.status_code == 200, r.text
    snap = screen(client, underwriter, app["id"])["decisions"][0]["snapshot"]
    assert snap["limitExceeded"] is False and snap["overrideLimit"] is False


def test_manual_without_auto_limit_is_not_blocked(client, underwriter, flow):
    app = flow.submitted()  # внешние проверки отключены: AUTO-снимка с лимитом нет
    card = screen(client, underwriter, app["id"])
    assert card["autoLimit"] is None
    r = client.post(
        DECISION.format(app["id"]), headers=underwriter, json={"outcome": "APPROVED", "comment": "ок"}
    )
    assert r.status_code == 200, r.text
    assert screen(client, underwriter, app["id"])["decisions"][0]["snapshot"]["limitUnknown"] is True


def test_migration_backfill_moves_auto_json_and_keeps_broken_json(db, flow):
    spec = importlib.util.spec_from_file_location(
        "migration_0003", BACKEND_DIR / "alembic" / "versions" / "0003_decision_snapshot.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    a, b = flow.submitted()["id"], flow.submitted()["id"]
    good, broken = (
        db.scalar(select(CreditDecision.decision_id).where(CreditDecision.application_id == x))
        for x in (a, b)
    )
    update = text(
        "UPDATE credit_decision SET decision_snapshot = NULL, comment_desc = :c WHERE decision_id = :i"
    )
    db.execute(update, {"c": json.dumps({"ruleCode": "OLD", "limit": "1"}), "i": good})
    db.execute(update, {"c": "{не json", "i": broken})
    migration.backfill_snapshots(db.connection())
    db.expire_all()
    moved, kept = db.get(CreditDecision, good), db.get(CreditDecision, broken)
    assert moved.decision_snapshot == {"ruleCode": "OLD", "limit": "1"} and moved.comment_desc is None
    assert kept.decision_snapshot is None and kept.comment_desc == "{не json"
