"""Замер времени ответа API и времени автоматического решения (подача заявки с конвейером).

Запуск на поднятом стенде (db, mocks и API):
    python scripts/measure.py [--base-url http://localhost:8000] [--reads 200] [--submits 20]

Только стандартная библиотека. Создаёт заявки от имени seed-клиентов и регистрирует одну компанию по ИНН 7702000075
(логин measure_slow_bki; при повторном запуске выполняется вход), поэтому гоняйте на отдельной или одноразовой БД, не на демо-данных.
Время считается на клиенте (включая локальный HTTP), одним потоком, без параллельной нагрузки.
"""

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
import uuid

PASSWORD = "demo1234"


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(self, method, path, token=None, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        dt = time.perf_counter() - t0
        return status, (json.loads(raw) if raw else None), dt

    def login(self, login):
        status, body, _ = self.call("POST", "/api/v1/auth/login", body={"login": login, "password": PASSWORD})
        assert status == 200, f"вход {login}: HTTP {status}"
        return body["accessToken"]


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def summary(name, values):
    ms = [v * 1000 for v in values]
    print(
        f"| {name} | {len(ms)} | {statistics.median(ms):.0f} | {pct(ms, 0.95):.0f} | {max(ms):.0f} |"
    )


def draft_and_submit(api, token, amount=1_500_000, term=12, extra=None):
    body = {
        "productCode": "WORKING_CAPITAL",
        "requestedAmount": amount,
        "termMonths": term,
        "purpose": "Пополнение оборотных средств",
        "draftStep": 3,
    }
    body.update(extra or {})
    status, draft, _ = api.call("POST", "/api/v1/applications", token=token, body=body)
    assert status == 201, f"черновик: HTTP {status} {draft}"
    status, sub, dt = api.call(
        "POST",
        f"/api/v1/applications/{draft['id']}/submit",
        token=token,
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert status == 202, f"подача: HTTP {status} {sub}"
    return sub["status"], dt


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--reads", type=int, default=200)
    p.add_argument("--submits", type=int, default=20)
    args = p.parse_args()
    api = Api(args.base_url)

    token = api.login("client_fast")
    uw = api.login("underwriter")
    _, draft_app, _ = api.call(
        "POST",
        "/api/v1/applications",
        token=token,
        body={"productCode": "WORKING_CAPITAL", "requestedAmount": 1_000_000, "termMonths": 12, "purpose": "замер"},
    )
    app_id = draft_app["id"]

    print("Чтение (последовательные запросы):\n")
    print("| Запрос | N | p50, мс | p95, мс | max, мс |\n|---|---|---|---|---|")
    reads = [
        ("GET /health", "GET", "/health", None),
        ("GET /products", "GET", "/api/v1/products", token),
        ("GET /companies/me", "GET", "/api/v1/companies/me", token),
        ("GET /applications/{id}", "GET", f"/api/v1/applications/{app_id}", token),
        ("GET /underwriter/queue", "GET", "/api/v1/underwriter/queue?limit=50", uw),
    ]
    for name, method, path, tok in reads:
        times = []
        for _ in range(args.reads):
            status, _, dt = api.call(method, path, token=tok)
            assert status == 200, f"{name}: HTTP {status}"
            times.append(dt)
        summary(name, times)

    print("\nПодача заявки до решения (POST /submit возвращает уже итоговый статус):\n")
    print("| Сценарий | N | статусы | p50, мс | p95, мс | max, мс |\n|---|---|---|---|---|---|")
    scenarios = [
        ("client_fast, 1,5 млн, 12 мес. (одобрение)", "client_fast", args.submits, {}),
        ("client_counter, 10 млн, 12 мес. (контроффер)", "client_counter", args.submits, {"amount": 10_000_000}),
        ("client_reject (стоп-фактор)", "client_reject", args.submits, {}),
        ("client_timeout (БКИ 503, ретраи)", "client_timeout", 5, {}),
    ]
    for name, login, n, kw in scenarios:
        tok = api.login(login)
        times, statuses = [], {}
        for _ in range(n):
            st, dt = draft_and_submit(api, tok, **kw)
            statuses[st] = statuses.get(st, 0) + 1
            times.append(dt)
        ms = [v * 1000 for v in times]
        print(
            f"| {name} | {n} | {dict(statuses)} | {statistics.median(ms):.0f} | {pct(ms, 0.95):.0f} | {max(ms):.0f} |"
        )

    status, reg, _ = api.call(
        "POST", "/api/v1/auth/register", body={"login": "measure_slow_bki", "password": "secret123", "inn": "7702000075"}
    )
    if status in (200, 201):
        tok = reg["accessToken"]
    elif status == 409:
        tok = api.call("POST", "/api/v1/auth/login", body={"login": "measure_slow_bki", "password": "secret123"})[1][
            "accessToken"
        ]
    else:
        tok = None
    if tok:
        times, statuses = [], {}
        for _ in range(3):
            st, dt = draft_and_submit(api, tok, amount=1_000_000)
            statuses[st] = statuses.get(st, 0) + 1
            times.append(dt * 1000)
        print(
            f"| ИНН …75 (БКИ отвечает 2 с, бюджет 3 с) | 3 | {dict(statuses)} | "
            f"{statistics.median(times):.0f} | {max(times):.0f} | {max(times):.0f} |"
        )
    else:
        print(f"(замер ИНН 7702000075 пропущен: регистрация HTTP {status})")


if __name__ == "__main__":
    main()
