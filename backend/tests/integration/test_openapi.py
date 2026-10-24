import re

from app.main import app
from app.scripts.export_openapi import DEFAULT_OUTPUT, render_openapi_yaml


def test_openapi_file_matches_code():
    assert DEFAULT_OUTPUT.read_text(encoding="utf-8") == render_openapi_yaml(), (
        "docs/api/openapi.yaml разошёлся с кодом: uv run python -m app.scripts.export_openapi"
    )


def _operations():
    for path, item in app.openapi()["paths"].items():
        for method, op in item.items():
            yield path, method, op


def test_operation_ids_are_unique_camel_case():
    ids = [op["operationId"] for _, _, op in _operations()]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z][A-Za-z0-9]*", i) for i in ids), ids


def test_all_contract_endpoints_present():
    expected = {
        ("post", "/api/v1/auth/login"),
        ("post", "/api/v1/auth/register"),
        ("get", "/api/v1/auth/me"),
        ("get", "/api/v1/products"),
        ("get", "/api/v1/companies/me"),
        ("post", "/api/v1/companies/me/enrich"),
        ("get", "/api/v1/applications"),
        ("post", "/api/v1/applications"),
        ("patch", "/api/v1/applications/{application_id}"),
        ("post", "/api/v1/applications/{application_id}/submit"),
        ("get", "/api/v1/applications/{application_id}"),
        ("get", "/api/v1/applications/{application_id}/timeline"),
        ("patch", "/api/v1/applications/{application_id}/missing-info"),
        ("post", "/api/v1/applications/{application_id}/offer/accept"),
        ("post", "/api/v1/applications/{application_id}/offer/decline"),
        ("post", "/api/v1/applications/{application_id}/sign"),
        ("post", "/api/v1/applications/{application_id}/withdraw"),
        ("post", "/api/v1/products/recommendations"),
        ("post", "/api/v1/underwriter/applications/{application_id}/recheck"),
        ("get", "/api/v1/underwriter/queue"),
        ("get", "/api/v1/underwriter/applications/{application_id}"),
        ("post", "/api/v1/underwriter/applications/{application_id}/decision"),
        ("get", "/api/v1/applications/{application_id}/audit"),
        ("get", "/health"),
    }
    assert {(m, p) for p, m, _ in _operations()} == expected


def test_errors_are_problem_json_and_secured_operations_use_bearer():
    for path, method, op in _operations():
        for status, resp in op["responses"].items():
            if int(status) >= 400:
                assert list(resp["content"]) == ["application/problem+json"], (path, method, status)
        if path not in ("/api/v1/auth/login", "/api/v1/auth/register", "/health"):
            assert op["security"] == [{"bearerAuth": []}], (path, method)


def test_money_is_number_and_statuses_are_enums():
    schemas = app.openapi()["components"]["schemas"]
    assert schemas["OfferOut"]["properties"]["amount"]["type"] == "number"
    assert schemas["ApplicationStatus"]["enum"][0] == "DRAFT"
    assert "ProblemDetail" in schemas
    assert {"HTTPValidationError", "ValidationError"}.isdisjoint(schemas)
