"""Сквозная проверка запущенного стенда, как у жюри: вход → каталог → профиль → черновик → подача → конвейер → аудит.

Запуск (стенд поднят через `docker compose up`):
    cd backend && uv run python -m app.scripts.smoke [--base-url http://localhost:8000]

Использует только стандартную библиотеку. Выходит с кодом 1, если любой шаг не сработал.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

PASSWORD = "demo1234"
FINAL_FOR_SMOKE = "MANUAL_REVIEW"


class Smoke:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.failed = False

    def call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: Any = None,
        headers: dict | None = None,
    ) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, json.loads(raw) if raw else None

    def check(self, title: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'OK' if ok else 'FAIL'}] {title}" + (f": {detail}" if detail else ""))
        self.failed |= not ok

    def login(self, login: str) -> str:
        status, body = self.call("POST", "/api/v1/auth/login", body={"login": login, "password": PASSWORD})
        self.check(f"вход {login}", status == 200, f"HTTP {status}")
        return body["accessToken"] if status == 200 else ""

    def run(self) -> int:
        print(f"Проверка стенда: {self.base}")
        status, body = self.call("GET", "/health")
        self.check("GET /health", status == 200 and body["database"] == "ok", f"HTTP {status}")

        token = self.login("client_fast")
        if not token:
            return 1

        _, products = self.call("GET", "/api/v1/products", token=token)
        self.check("GET /products", len(products) == 3, ", ".join(p["code"] for p in products))

        _, company = self.call("GET", "/api/v1/companies/me", token=token)
        self.check(
            "GET /companies/me", company["inn"] == "770100000001", f"{company['name']} (ИНН {company['inn']})"
        )

        status, draft = self.call(
            "POST",
            "/api/v1/applications",
            token=token,
            body={
                "productCode": "EQUIPMENT",
                "requestedAmount": 1500000,
                "termMonths": 24,
                "purpose": "Покупка фрезерного станка",
                "revenueAmount": 12000000,
                "draftStep": 3,
            },
        )
        self.check(
            "POST /applications (черновик)", status == 201 and draft["status"] == "DRAFT", f"id={draft['id']}"
        )
        app_id = draft["id"]

        key = uuid.uuid4().hex
        status, submitted = self.call(
            "POST", f"/api/v1/applications/{app_id}/submit", token=token, headers={"Idempotency-Key": key}
        )
        self.check("POST /submit", status == 202, f"HTTP {status}, статус {submitted['status']}")
        status, again = self.call(
            "POST", f"/api/v1/applications/{app_id}/submit", token=token, headers={"Idempotency-Key": key}
        )
        self.check(
            "повторный submit с тем же ключом", status == 200 and again["id"] == app_id, f"HTTP {status}"
        )

        print("  ... конвейер обработки:")
        seen: list[str] = []
        deadline = time.monotonic() + 40
        current = ""
        while time.monotonic() < deadline:
            _, app = self.call("GET", f"/api/v1/applications/{app_id}", token=token)
            current = app["status"]
            if not seen or seen[-1] != current:
                seen.append(current)
                print(f"      {time.strftime('%H:%M:%S')}  {current}  ({app['statusName']})")
            if current == FINAL_FOR_SMOKE:
                break
            time.sleep(0.5)
        self.check(f"заявка дошла до {FINAL_FOR_SMOKE}", current == FINAL_FOR_SMOKE)

        _, timeline = self.call("GET", f"/api/v1/applications/{app_id}/timeline", token=token)
        stages = ", ".join(f"{s['code']}:{s['state']}" for s in timeline["stages"])
        self.check("GET /timeline", len(timeline["history"]) >= 6, stages)

        uw = self.login("underwriter")
        _, audit = self.call("GET", f"/api/v1/applications/{app_id}/audit", token=uw)
        path = " → ".join(["∅"] + [a["toStatus"] for a in audit])
        self.check("GET /audit содержит все переходы", len(audit) >= 6, path)

        _, queue = self.call("GET", "/api/v1/underwriter/queue?limit=100", token=uw)
        self.check(
            "заявка в очереди андеррайтера",
            any(i["applicationId"] == app_id for i in queue["items"]),
            f"в очереди {queue['total']}",
        )

        status, foreign = self.call(
            "GET", f"/api/v1/applications/{app_id}", token=self.login("client_counter")
        )
        self.check("чужая заявка недоступна (404)", status == 404 and foreign["code"] == "NOT_FOUND")
        status, _ = self.call("GET", "/api/v1/underwriter/queue", token=token)
        self.check("клиенту закрыта панель банка (403)", status == 403)

        print("ИТОГ:", "есть ошибки" if self.failed else "всё в порядке")
        return 1 if self.failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        sys.exit(Smoke(args.base_url).run())
    except (urllib.error.URLError, ConnectionError) as exc:
        print(f"Стенд недоступен: {exc}. Запущен ли `docker compose up`?")
        sys.exit(2)


if __name__ == "__main__":
    main()
