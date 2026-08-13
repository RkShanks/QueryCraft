"""Canonical OpenAPI parity and generation contracts for IS-GAP-008."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute

from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_OPENAPI = BACKEND_ROOT / "openapi.json"
GENERATOR = BACKEND_ROOT / "scripts" / "generate_openapi.py"
HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})
DOCUMENTATION_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"})


def _schema_operations(schema: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (method.upper(), path): operation
        for path, path_item in schema["paths"].items()
        if path not in DOCUMENTATION_PATHS
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    }


def _runtime_operations() -> set[tuple[str, str]]:
    app = create_app()
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema and route.path not in DOCUMENTATION_PATHS
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }


def _canonical_schema() -> dict[str, Any]:
    return json.loads(CANONICAL_OPENAPI.read_text(encoding="utf-8"))


def _json_schema(operation: dict[str, Any], status_code: str) -> dict[str, Any]:
    return operation["responses"][status_code]["content"]["application/json"]["schema"]


def _schema_refs(schema: dict[str, Any]) -> Iterator[str]:
    for key, value in schema.items():
        if key == "$ref":
            yield value.rsplit("/", maxsplit=1)[-1]
        elif isinstance(value, dict):
            yield from _schema_refs(value)
        elif isinstance(value, list):
            for member in value:
                if isinstance(member, dict):
                    yield from _schema_refs(member)


def test_runtime_and_canonical_operation_sets_match_exactly():
    runtime_schema = create_app().openapi()
    canonical_schema = _canonical_schema()
    runtime_operations = set(_schema_operations(runtime_schema))
    canonical_operations = set(_schema_operations(canonical_schema))

    assert runtime_operations == _runtime_operations()
    assert canonical_operations == runtime_operations
    assert len(canonical_operations) == len(runtime_operations)


def test_operation_ids_are_unique_stable_and_preserve_existing_client_names():
    runtime_operations = _schema_operations(create_app().openapi())
    canonical_operations = _schema_operations(_canonical_schema())
    runtime_ids = {key: operation["operationId"] for key, operation in runtime_operations.items()}
    canonical_ids = {key: operation["operationId"] for key, operation in canonical_operations.items()}

    assert runtime_ids == canonical_ids
    assert len(set(runtime_ids.values())) == len(runtime_ids)
    assert runtime_ids[("POST", "/api/v1/auth/sign-in")] == "signIn"
    assert runtime_ids[("POST", "/api/v1/query/submit")] == "submitQuestion"
    assert runtime_ids[("GET", "/api/v1/sessions")] == "getSessions"
    assert runtime_ids[("GET", "/api/v1/admin/connections")] == "listAdminConnections"


@pytest.mark.parametrize(
    ("operation_key", "content_type", "schema_name"),
    [
        (("POST", "/api/v1/query/submit"), "application/json", "SubmitQuestionRequest"),
        (("POST", "/api/v1/query/accept"), "application/json", "AcceptQueryRequest"),
        (("POST", "/api/v1/query/reject"), "application/json", "RejectQueryRequest"),
        (("POST", "/api/v1/query/regenerate"), "application/json", "RegenerateQueryRequest"),
        (("PUT", "/api/v1/admin/quotas/{role_id}"), "application/json", "RoleQuotaUpsert"),
        (("POST", "/api/v1/admin/audit/export"), "application/json", "AuditExportRequest"),
    ],
)
def test_json_request_bodies_are_typed(
    operation_key: tuple[str, str],
    content_type: str,
    schema_name: str,
):
    operation = _schema_operations(_canonical_schema())[operation_key]
    request_schema = operation["requestBody"]["content"][content_type]["schema"]

    assert request_schema == {"$ref": f"#/components/schemas/{schema_name}"}


def test_saml_callback_declares_its_form_body_and_redirect_response():
    operation = _schema_operations(_canonical_schema())[("POST", "/api/v1/auth/sso/saml/callback")]
    form_schema = operation["requestBody"]["content"]["application/x-www-form-urlencoded"]["schema"]

    assert {"SAMLResponse", "RelayState"} <= set(form_schema["required"])
    assert set(operation["responses"]) == {"302", "422"}
    assert "content" not in operation["responses"]["302"]
    assert operation["responses"]["302"]["headers"]["Location"]["schema"] == {"type": "string"}


@pytest.mark.parametrize(
    "operation_key",
    [
        ("GET", "/api/v1/auth/sso/oidc/login"),
        ("GET", "/api/v1/auth/sso/oidc/callback"),
        ("GET", "/api/v1/auth/sso/saml/login"),
    ],
)
def test_browser_and_identity_provider_flows_remain_redirect_contracts(operation_key: tuple[str, str]):
    operation = _schema_operations(_canonical_schema())[operation_key]

    assert "302" in operation["responses"]
    assert "content" not in operation["responses"]["302"]
    assert operation["responses"]["302"]["headers"]["Location"]["schema"] == {"type": "string"}


def test_query_success_and_rejection_contracts_are_typed():
    operations = _schema_operations(_canonical_schema())
    submit_operation = operations[("POST", "/api/v1/query/submit")]

    assert _json_schema(submit_operation, "200") == {"$ref": "#/components/schemas/QueryResult"}
    assert set(_schema_refs(_json_schema(submit_operation, "400"))) == {
        "ErrorResponse",
        "ValidationErrorResponse",
    }
    assert _json_schema(submit_operation, "422") == {"$ref": "#/components/schemas/EvaluatorRejection"}
    for operation_key in (
        ("POST", "/api/v1/query/reject"),
        ("POST", "/api/v1/query/regenerate"),
    ):
        assert set(_schema_refs(_json_schema(operations[operation_key], "200"))) == {
            "QueryResult",
            "RefinePrompt",
        }


def test_downloads_and_empty_responses_declare_exact_content_contracts():
    operations = _schema_operations(_canonical_schema())
    export_response = operations[("POST", "/api/v1/admin/audit/export")]["responses"]["200"]

    assert set(export_response["content"]) == {"application/json", "text/csv"}
    assert export_response["headers"]["Content-Disposition"]["schema"] == {"type": "string"}
    for operation_key in (
        ("POST", "/api/v1/auth/sign-out"),
        ("DELETE", "/api/v1/history/{query_id}"),
        ("DELETE", "/api/v1/admin/connections/{connection_id}"),
        ("DELETE", "/api/v1/admin/quotas/{role_id}"),
        ("DELETE", "/api/v1/admin/sso/providers/{provider_id}"),
        ("DELETE", "/api/v1/admin/sso/group-mappings/{mapping_id}"),
        ("DELETE", "/api/v1/admin/roles/{role_id}"),
        ("DELETE", "/api/v1/sessions/{session_id}"),
    ):
        response = operations[operation_key]["responses"]["204"]
        assert "content" not in response


def test_public_probes_and_paginated_resources_are_typed():
    operations = _schema_operations(_canonical_schema())

    assert operations[("GET", "/health")]["security"] == []
    assert operations[("GET", "/ready")]["security"] == []
    assert _json_schema(operations[("GET", "/health")], "200") == {"$ref": "#/components/schemas/LivenessResponse"}
    assert _json_schema(operations[("GET", "/ready")], "503") == {"$ref": "#/components/schemas/NotReadyResponse"}
    assert _json_schema(operations[("GET", "/api/v1/query/limits")], "200") == {
        "$ref": "#/components/schemas/QueryLimitsResponse"
    }
    for operation_key, schema_name in (
        (("GET", "/api/v1/history"), "HistoryListResponse"),
        (("GET", "/api/v1/sessions"), "SessionListResponse"),
        (("GET", "/api/v1/sessions/{session_id}"), "SessionDetail"),
        (("GET", "/api/v1/admin/quotas/status"), "QuotaStatusResponse"),
    ):
        assert _json_schema(operations[operation_key], "200") == {"$ref": f"#/components/schemas/{schema_name}"}


def test_declared_json_errors_use_sanitized_response_schemas():
    allowed_error_schemas = {
        "ErrorResponse",
        "EvaluatorRejection",
        "NotReadyResponse",
        "QuotaExceededErrorResponse",
        "QuotaSyncPendingErrorResponse",
        "ValidationErrorResponse",
    }
    for operation in _schema_operations(_canonical_schema()).values():
        for status_code, response in operation["responses"].items():
            if int(status_code) < 400 or "application/json" not in response.get("content", {}):
                continue
            response_refs = set(_schema_refs(response["content"]["application/json"]["schema"]))
            assert response_refs
            assert response_refs <= allowed_error_schemas


def test_canonical_generation_is_deterministic(tmp_path: Path):
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    environment = os.environ.copy()

    for output_path in (first_output, second_output):
        subprocess.run(
            [sys.executable, str(GENERATOR), "--output", str(output_path)],
            cwd=BACKEND_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    assert first_output.read_bytes() == second_output.read_bytes()
    assert first_output.read_bytes() == CANONICAL_OPENAPI.read_bytes()
