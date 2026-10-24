from fastapi.testclient import TestClient

from tests.integration.conftest import Flow


def test_login_returns_token_and_user(client: TestClient):
    r = client.post("/api/v1/auth/login", json={"login": "client_fast", "password": "demo1234"})
    assert r.status_code == 200
    body = r.json()
    assert body["tokenType"] == "Bearer" and body["accessToken"]
    assert body["user"]["role"] == "CLIENT" and body["user"]["companyId"] is not None


def test_login_with_wrong_password_or_unknown_login(client: TestClient):
    for creds in ({"login": "client_fast", "password": "nope"}, {"login": "ghost", "password": "demo1234"}):
        r = client.post("/api/v1/auth/login", json=creds)
        assert r.status_code == 401
        assert r.headers["content-type"].startswith("application/problem+json")
        assert r.json()["code"] == "INVALID_CREDENTIALS"
        assert creds["password"] not in r.text  # пароль не возвращается и не попадает в ответ ошибки


def test_me_returns_current_user(client: TestClient, underwriter):
    r = client.get("/api/v1/auth/me", headers=underwriter)
    assert r.status_code == 200
    assert r.json()["role"] == "UNDERWRITER" and r.json()["companyId"] is None


def test_requests_without_or_with_bad_token_are_unauthorized(client: TestClient):
    for headers in ({}, {"Authorization": "Bearer not-a-jwt"}, {"Authorization": "Basic abc"}):
        r = client.get("/api/v1/products", headers=headers)
        assert r.status_code == 401
        assert r.json()["code"] == "UNAUTHORIZED"
        assert r.headers["www-authenticate"] == "Bearer"


def test_client_cannot_call_underwriter_endpoints(client: TestClient, fast, flow: Flow):
    app = flow.submitted()
    calls = [
        client.get("/api/v1/underwriter/queue", headers=fast),
        client.get(f"/api/v1/underwriter/applications/{app['id']}", headers=fast),
        client.post(
            f"/api/v1/underwriter/applications/{app['id']}/decision",
            headers=fast,
            json={"outcome": "APPROVED", "comment": "сам себе одобрю"},
        ),
        client.get(f"/api/v1/applications/{app['id']}/audit", headers=fast),
    ]
    assert [c.status_code for c in calls] == [403] * 4
    assert {c.json()["code"] for c in calls} == {"FORBIDDEN"}


def test_underwriter_cannot_use_client_only_endpoints(client: TestClient, underwriter):
    assert client.get("/api/v1/products", headers=underwriter).status_code == 403
    assert client.get("/api/v1/companies/me", headers=underwriter).status_code == 403
    assert (
        client.post(
            "/api/v1/applications", headers=underwriter, json={"productCode": "OVERDRAFT"}
        ).status_code
        == 403
    )


def test_client_does_not_see_foreign_application(client: TestClient, other_client, flow: Flow):
    app = flow.submitted()
    app_id = app["id"]
    for method, path, kwargs in [
        ("get", f"/api/v1/applications/{app_id}", {}),
        ("get", f"/api/v1/applications/{app_id}/timeline", {}),
        ("patch", f"/api/v1/applications/{app_id}", {"json": {"purpose": "чужое"}}),
        ("post", f"/api/v1/applications/{app_id}/offer/accept", {}),
        ("post", f"/api/v1/applications/{app_id}/sign", {"json": {"code": "123456"}}),
    ]:
        r = client.request(method, path, headers=other_client, **kwargs)
        assert r.status_code == 404, (method, path, r.text)
        assert r.json()["code"] == "NOT_FOUND"
    assert app_id not in [a["id"] for a in client.get("/api/v1/applications", headers=other_client).json()]


def test_products_and_company_profile(client: TestClient, fast):
    products = client.get("/api/v1/products", headers=fast).json()
    assert [p["code"] for p in products] == ["WORKING_CAPITAL", "EQUIPMENT", "OVERDRAFT"]
    assert all(isinstance(p["minAmount"], float) and isinstance(p["rate"], float) for p in products)

    company = client.get("/api/v1/companies/me", headers=fast).json()
    assert company["inn"] == "770100000001" and company["legalForm"] == "IP"
    assert company["legalAddress"] and company["registrationDate"]


def test_health_and_request_id(client: TestClient):
    r = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok"}
    assert r.headers["x-request-id"] == "trace-123"


def test_validation_errors_are_problem_json_with_russian_field_messages(client: TestClient, fast):
    r = client.post(
        "/api/v1/applications", headers=fast, json={"productCode": "NOPE", "requestedAmount": "abc"}
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert {e["field"] for e in body["errors"]} == {"productCode", "requestedAmount"}
    assert all(e["message"] for e in body["errors"])


def test_token_signed_with_old_demo_secret_is_rejected(client: TestClient):
    import jwt as pyjwt

    from app.core.security import DEMO_JWT_SECRET

    forged = pyjwt.encode({"sub": "1", "role": "UNDERWRITER", "exp": 4102444800}, DEMO_JWT_SECRET, "HS256")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_weak_secret_is_replaced_and_persisted(tmp_path, monkeypatch):
    from app.core import security
    from app.core.config import get_settings

    path = tmp_path / "secret"
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("JWT_SECRET_FILE", str(path))
    get_settings.cache_clear()
    security.get_jwt_secret.cache_clear()
    try:
        first = security.get_jwt_secret()
        assert len(first) >= 32 and first != security.DEMO_JWT_SECRET
        assert path.read_text() == first
        security.get_jwt_secret.cache_clear()
        assert security.get_jwt_secret() == first  # следующий старт читает файл
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        security.get_jwt_secret.cache_clear()


def test_login_rate_limit_and_reset(client: TestClient, monkeypatch):
    from app.services import auth as auth_service

    now = [1000.0]
    monkeypatch.setattr(auth_service, "_now", lambda: now[0])
    bad = {"login": "rate-limited-user", "password": "nope"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=bad).status_code == 401
    r = client.post("/api/v1/auth/login", json=bad)
    assert r.status_code == 429
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "TOO_MANY_REQUESTS"
    assert 1 <= int(r.headers["Retry-After"]) <= 300
    # другой логин не затронут
    assert (
        client.post("/api/v1/auth/login", json={"login": "client_fast", "password": "demo1234"}).status_code
        == 200
    )
    # окно истекло: снова 401, а не 429
    now[0] += 301
    assert client.post("/api/v1/auth/login", json=bad).status_code == 401


def test_successful_login_resets_failure_counter(client: TestClient):
    from app.services import auth as auth_service

    auth_service.reset_login_limiter()
    for _ in range(4):
        client.post("/api/v1/auth/login", json={"login": "client_fast", "password": "nope"})
    assert (
        client.post("/api/v1/auth/login", json={"login": "client_fast", "password": "demo1234"}).status_code
        == 200
    )
    for _ in range(4):
        assert (
            client.post("/api/v1/auth/login", json={"login": "client_fast", "password": "nope"}).status_code
            == 401
        )
    auth_service.reset_login_limiter()
