"""Host-side verification against the existing local Compose demo; creates only synthetic data."""

import json
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE = "http://localhost:3000/api/v1"


def call(path, token=None, body=None, method=None, key=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if key:
        headers["Idempotency-Key"] = key
    request = Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method or ("POST" if body is not None else "GET"),
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def login():
    return call("/auth/login", body={"login": "client_fast", "password": "demo1234"})["accessToken"]


token = login()
a = call(
    "/applications",
    token,
    {
        "productCode": "WORKING_CAPITAL",
        "requestedAmount": 1500000,
        "termMonths": 12,
        "purpose": "Проверка сохранности после перезапуска",
    },
)
a = call(f"/applications/{a['id']}/submit", token, method="POST", key=uuid.uuid4().hex)
assert a["status"] == "APPROVED", a["status"]
before = {k: a[k] for k in ("id", "status", "offer", "history")}
subprocess.run(["docker", "compose", "restart"], cwd=Path(__file__).resolve().parents[1], check=True)
deadline = time.monotonic() + 60
while True:
    try:
        token = login()
        a = call(f"/applications/{a['id']}", token)
        break
    except (URLError, TimeoutError, ConnectionError):
        if time.monotonic() > deadline:
            raise
        time.sleep(0.5)
after = {k: a[k] for k in ("id", "status", "offer", "history")}
assert before == after
print(f"PASS: application {a['id']}, offer and audit survived restart and repeat seed")
