"""Runtime-owned OpenAPI metadata and deterministic schema construction."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from app.schemas.admin_settings import (
    AdminSettingsResponse,
    SchemaRefreshResponse,
    UpdateAdminSettingsResponse,
)
from app.schemas.audit import AuditRetentionResponse, AuditStatusResponse, AuditVerifyResponse
from app.schemas.audit_search import AuditExportRequest, AuditSearchResponse
from app.schemas.auth import UserProfile
from app.schemas.connection import (
    ConnectionResponse,
    ConnectionSchemaResponse,
    ConnectionTestResult,
    UserConnectionListResponse,
)
from app.schemas.detection import DetectionThresholdRead
from app.schemas.errors import (
    ErrorResponse,
    QuotaExceededErrorResponse,
    QuotaSyncPendingErrorResponse,
    ValidationErrorResponse,
)
from app.schemas.feedback import FeedbackResponse
from app.schemas.group_mapping import GroupMappingListResponse, GroupMappingResponse
from app.schemas.history import AcceptedQueryDetail, HistoryListResponse
from app.schemas.operational import LivenessResponse, NotReadyResponse, ReadinessResponse
from app.schemas.query import (
    AcceptedQuerySummary,
    AcceptQueryRequest,
    EvaluatorRejection,
    QueryLimitsResponse,
    QueryResult,
    RefinePrompt,
    RegenerateQueryRequest,
    RejectQueryRequest,
    SubmitQuestionRequest,
)
from app.schemas.quota import QuotaListResponse, QuotaStatusResponse, RoleQuotaConfig, RoleQuotaUpsert
from app.schemas.roles import PolicyTestResponse, RoleDetailResponse, RoleListResponse
from app.schemas.session import (
    CreateSessionResponse,
    SessionConnectionResponse,
    SessionDetail,
    SessionListResponse,
)
from app.schemas.sso import SsoProviderListResponse, SsoProviderPublicListResponse, SsoProviderResponse

type OperationKey = tuple[str, str]
type ModelType = type[BaseModel]
type ResponseModels = ModelType | tuple[ModelType, ...]

OPERATION_IDS: dict[OperationKey, str] = {
    ("GET", "/health"): "getHealth",
    ("GET", "/ready"): "getReadiness",
    ("POST", "/api/v1/auth/sign-in"): "signIn",
    ("POST", "/api/v1/auth/sign-out"): "signOut",
    ("GET", "/api/v1/auth/me"): "getMe",
    ("GET", "/api/v1/query/limits"): "getQueryLimits",
    ("POST", "/api/v1/query/submit"): "submitQuestion",
    ("POST", "/api/v1/query/accept"): "acceptQuery",
    ("POST", "/api/v1/query/reject"): "rejectQuery",
    ("POST", "/api/v1/query/regenerate"): "regenerateQuery",
    ("GET", "/api/v1/history"): "listHistory",
    ("GET", "/api/v1/history/{query_id}"): "getHistoryEntry",
    ("DELETE", "/api/v1/history/{query_id}"): "deleteHistoryEntry",
    ("POST", "/api/v1/admin/refresh-schema"): "refreshSchema",
    ("GET", "/api/v1/admin/settings"): "getAdminSettings",
    ("PATCH", "/api/v1/admin/settings"): "updateAdminSettings",
    ("GET", "/api/v1/admin/connections"): "listAdminConnections",
    ("POST", "/api/v1/admin/connections"): "createAdminConnection",
    ("GET", "/api/v1/admin/connections/{connection_id}"): "getAdminConnection",
    ("PUT", "/api/v1/admin/connections/{connection_id}"): "updateAdminConnection",
    ("DELETE", "/api/v1/admin/connections/{connection_id}"): "deleteAdminConnection",
    ("POST", "/api/v1/admin/connections/{connection_id}/disable"): "disableAdminConnection",
    ("POST", "/api/v1/admin/connections/{connection_id}/enable"): "enableAdminConnection",
    ("POST", "/api/v1/admin/connections/{connection_id}/test"): "testAdminConnection",
    ("POST", "/api/v1/admin/connections/{connection_id}/refresh-schema"): "refreshAdminConnectionSchema",
    ("GET", "/api/v1/admin/connections/{connection_id}/schema"): "getAdminConnectionSchema",
    ("GET", "/api/v1/admin/quotas"): "listQuotas",
    ("GET", "/api/v1/admin/quotas/status"): "getQuotaStatus",
    ("GET", "/api/v1/admin/quotas/{role_id}"): "getQuota",
    ("PUT", "/api/v1/admin/quotas/{role_id}"): "upsertQuota",
    ("DELETE", "/api/v1/admin/quotas/{role_id}"): "deleteQuota",
    ("GET", "/api/v1/admin/detection/config"): "getDetectionConfig",
    ("PUT", "/api/v1/admin/detection/config"): "updateDetectionConfig",
    ("GET", "/api/v1/admin/sso/providers"): "listAdminSsoProviders",
    ("POST", "/api/v1/admin/sso/providers"): "createSsoProvider",
    ("PUT", "/api/v1/admin/sso/providers/{provider_id}"): "updateSsoProvider",
    ("DELETE", "/api/v1/admin/sso/providers/{provider_id}"): "deleteSsoProvider",
    ("GET", "/api/v1/admin/sso/group-mappings"): "listGroupMappings",
    ("POST", "/api/v1/admin/sso/group-mappings"): "createGroupMapping",
    ("DELETE", "/api/v1/admin/sso/group-mappings/{mapping_id}"): "deleteGroupMapping",
    ("GET", "/api/v1/admin/roles"): "listRoles",
    ("POST", "/api/v1/admin/roles"): "createRole",
    ("GET", "/api/v1/admin/roles/{role_id}"): "getRole",
    ("PUT", "/api/v1/admin/roles/{role_id}"): "updateRole",
    ("DELETE", "/api/v1/admin/roles/{role_id}"): "deleteRole",
    ("POST", "/api/v1/admin/roles/{role_id}/test-policy"): "testRolePolicy",
    ("POST", "/api/v1/admin/audit/verify"): "verifyAuditChain",
    ("GET", "/api/v1/admin/audit/status"): "getAuditStatus",
    ("GET", "/api/v1/admin/audit/retention"): "getAuditRetention",
    ("GET", "/api/v1/admin/audit/entries"): "searchAuditEntries",
    ("POST", "/api/v1/admin/audit/export"): "exportAuditEntries",
    ("GET", "/api/v1/connections"): "listUserConnections",
    ("POST", "/api/v1/sessions"): "createSession",
    ("GET", "/api/v1/sessions"): "getSessions",
    ("GET", "/api/v1/sessions/{session_id}"): "getSession",
    ("DELETE", "/api/v1/sessions/{session_id}"): "deleteSession",
    ("PATCH", "/api/v1/sessions/{session_id}/connection"): "updateSessionConnection",
    ("PATCH", "/api/v1/feedback/{attempt_id}"): "updateFeedback",
    ("GET", "/api/v1/auth/sso/providers"): "listSsoProviders",
    ("GET", "/api/v1/auth/sso/oidc/login"): "oidcLogin",
    ("GET", "/api/v1/auth/sso/oidc/callback"): "oidcCallback",
    ("GET", "/api/v1/auth/sso/saml/login"): "samlLogin",
    ("POST", "/api/v1/auth/sso/saml/callback"): "samlCallback",
}

REQUEST_MODELS: dict[OperationKey, ModelType] = {
    ("POST", "/api/v1/query/submit"): SubmitQuestionRequest,
    ("POST", "/api/v1/query/accept"): AcceptQueryRequest,
    ("POST", "/api/v1/query/reject"): RejectQueryRequest,
    ("POST", "/api/v1/query/regenerate"): RegenerateQueryRequest,
    ("PUT", "/api/v1/admin/quotas/{role_id}"): RoleQuotaUpsert,
    ("POST", "/api/v1/admin/audit/export"): AuditExportRequest,
}

SUCCESS_MODELS: dict[OperationKey, tuple[int, ResponseModels]] = {
    ("GET", "/health"): (200, LivenessResponse),
    ("GET", "/ready"): (200, ReadinessResponse),
    ("POST", "/api/v1/auth/sign-in"): (200, UserProfile),
    ("GET", "/api/v1/auth/me"): (200, UserProfile),
    ("GET", "/api/v1/query/limits"): (200, QueryLimitsResponse),
    ("POST", "/api/v1/query/submit"): (200, QueryResult),
    ("POST", "/api/v1/query/accept"): (201, AcceptedQuerySummary),
    ("POST", "/api/v1/query/reject"): (200, (QueryResult, RefinePrompt)),
    ("POST", "/api/v1/query/regenerate"): (200, (QueryResult, RefinePrompt)),
    ("GET", "/api/v1/history"): (200, HistoryListResponse),
    ("GET", "/api/v1/history/{query_id}"): (200, AcceptedQueryDetail),
    ("POST", "/api/v1/admin/refresh-schema"): (200, SchemaRefreshResponse),
    ("GET", "/api/v1/admin/settings"): (200, AdminSettingsResponse),
    ("PATCH", "/api/v1/admin/settings"): (200, UpdateAdminSettingsResponse),
    ("POST", "/api/v1/admin/connections"): (201, ConnectionResponse),
    ("GET", "/api/v1/admin/connections/{connection_id}"): (200, ConnectionResponse),
    ("PUT", "/api/v1/admin/connections/{connection_id}"): (200, ConnectionResponse),
    ("POST", "/api/v1/admin/connections/{connection_id}/disable"): (200, ConnectionResponse),
    ("POST", "/api/v1/admin/connections/{connection_id}/enable"): (200, ConnectionResponse),
    ("POST", "/api/v1/admin/connections/{connection_id}/test"): (200, ConnectionTestResult),
    ("POST", "/api/v1/admin/connections/{connection_id}/refresh-schema"): (200, SchemaRefreshResponse),
    ("GET", "/api/v1/admin/connections/{connection_id}/schema"): (200, ConnectionSchemaResponse),
    ("GET", "/api/v1/admin/quotas"): (200, QuotaListResponse),
    ("GET", "/api/v1/admin/quotas/status"): (200, QuotaStatusResponse),
    ("GET", "/api/v1/admin/quotas/{role_id}"): (200, RoleQuotaConfig),
    ("PUT", "/api/v1/admin/quotas/{role_id}"): (200, RoleQuotaConfig),
    ("GET", "/api/v1/admin/detection/config"): (200, DetectionThresholdRead),
    ("PUT", "/api/v1/admin/detection/config"): (200, DetectionThresholdRead),
    ("GET", "/api/v1/admin/sso/providers"): (200, SsoProviderListResponse),
    ("POST", "/api/v1/admin/sso/providers"): (201, SsoProviderResponse),
    ("PUT", "/api/v1/admin/sso/providers/{provider_id}"): (200, SsoProviderResponse),
    ("GET", "/api/v1/admin/sso/group-mappings"): (200, GroupMappingListResponse),
    ("POST", "/api/v1/admin/sso/group-mappings"): (201, GroupMappingResponse),
    ("GET", "/api/v1/admin/roles"): (200, RoleListResponse),
    ("POST", "/api/v1/admin/roles"): (201, RoleDetailResponse),
    ("GET", "/api/v1/admin/roles/{role_id}"): (200, RoleDetailResponse),
    ("PUT", "/api/v1/admin/roles/{role_id}"): (200, RoleDetailResponse),
    ("POST", "/api/v1/admin/roles/{role_id}/test-policy"): (200, PolicyTestResponse),
    ("POST", "/api/v1/admin/audit/verify"): (200, AuditVerifyResponse),
    ("GET", "/api/v1/admin/audit/status"): (200, AuditStatusResponse),
    ("GET", "/api/v1/admin/audit/retention"): (200, AuditRetentionResponse),
    ("GET", "/api/v1/admin/audit/entries"): (200, AuditSearchResponse),
    ("GET", "/api/v1/connections"): (200, UserConnectionListResponse),
    ("POST", "/api/v1/sessions"): (201, CreateSessionResponse),
    ("GET", "/api/v1/sessions"): (200, SessionListResponse),
    ("GET", "/api/v1/sessions/{session_id}"): (200, SessionDetail),
    ("PATCH", "/api/v1/sessions/{session_id}/connection"): (200, SessionConnectionResponse),
    ("PATCH", "/api/v1/feedback/{attempt_id}"): (200, FeedbackResponse),
    ("GET", "/api/v1/auth/sso/providers"): (200, SsoProviderPublicListResponse),
}

ERROR_MODELS: dict[OperationKey, dict[int, ResponseModels]] = {
    ("GET", "/ready"): {503: NotReadyResponse},
    ("POST", "/api/v1/auth/sign-in"): {401: ErrorResponse, 422: ValidationErrorResponse, 503: ErrorResponse},
    ("POST", "/api/v1/auth/sign-out"): {401: ErrorResponse, 503: ErrorResponse},
    ("GET", "/api/v1/auth/me"): {401: ErrorResponse, 503: ErrorResponse},
    ("GET", "/api/v1/query/limits"): {401: ErrorResponse, 403: ErrorResponse, 503: ErrorResponse},
    ("POST", "/api/v1/query/submit"): {
        400: (ErrorResponse, ValidationErrorResponse),
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
        422: EvaluatorRejection,
        429: QuotaExceededErrorResponse,
        500: ErrorResponse,
        502: ErrorResponse,
        503: ErrorResponse,
        504: ErrorResponse,
    },
    ("POST", "/api/v1/query/accept"): {
        400: (ErrorResponse, ValidationErrorResponse),
        401: ErrorResponse,
        403: ErrorResponse,
        409: ErrorResponse,
        422: ErrorResponse,
        500: ErrorResponse,
        503: ErrorResponse,
    },
    ("POST", "/api/v1/query/reject"): {
        400: (ErrorResponse, ValidationErrorResponse),
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
        422: ErrorResponse,
        429: QuotaExceededErrorResponse,
        500: ErrorResponse,
        502: ErrorResponse,
        503: ErrorResponse,
        504: ErrorResponse,
    },
    ("POST", "/api/v1/query/regenerate"): {
        400: (ErrorResponse, ValidationErrorResponse),
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
        422: ErrorResponse,
        429: QuotaExceededErrorResponse,
        500: ErrorResponse,
        502: ErrorResponse,
        503: ErrorResponse,
        504: ErrorResponse,
    },
    ("GET", "/api/v1/history"): {
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        422: ValidationErrorResponse,
        503: ErrorResponse,
    },
    ("GET", "/api/v1/history/{query_id}"): {
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        422: ValidationErrorResponse,
        503: ErrorResponse,
    },
    ("DELETE", "/api/v1/history/{query_id}"): {
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        422: ValidationErrorResponse,
        503: ErrorResponse,
    },
}

PUBLIC_OPERATIONS = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("POST", "/api/v1/auth/sign-in"),
    ("GET", "/api/v1/auth/sso/providers"),
    ("GET", "/api/v1/auth/sso/oidc/login"),
    ("GET", "/api/v1/auth/sso/oidc/callback"),
    ("GET", "/api/v1/auth/sso/saml/login"),
    ("POST", "/api/v1/auth/sso/saml/callback"),
}

SESSION_ONLY_OPERATIONS = {
    ("POST", "/api/v1/auth/sign-out"),
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/connections"),
    ("POST", "/api/v1/sessions"),
    ("GET", "/api/v1/sessions"),
    ("GET", "/api/v1/sessions/{session_id}"),
    ("DELETE", "/api/v1/sessions/{session_id}"),
    ("PATCH", "/api/v1/sessions/{session_id}/connection"),
    ("PATCH", "/api/v1/feedback/{attempt_id}"),
}

REDIRECT_OPERATIONS = {
    ("GET", "/api/v1/auth/sso/oidc/login"),
    ("GET", "/api/v1/auth/sso/oidc/callback"),
    ("GET", "/api/v1/auth/sso/saml/login"),
    ("POST", "/api/v1/auth/sso/saml/callback"),
}


def _merge_error_models(entries: dict[OperationKey, dict[int, ResponseModels]]) -> None:
    for operation_key in OPERATION_IDS:
        if operation_key in PUBLIC_OPERATIONS:
            continue
        authentication_errors = {401: ErrorResponse}
        if operation_key not in SESSION_ONLY_OPERATIONS:
            authentication_errors[403] = ErrorResponse
        entries[operation_key] = authentication_errors | entries.get(operation_key, {})


_merge_error_models(ERROR_MODELS)


def _extend_operation_errors(operation_key: OperationKey, statuses: Iterable[int]) -> None:
    ERROR_MODELS.setdefault(operation_key, {}).update({status_code: ErrorResponse for status_code in statuses})


for _operation_key, _statuses in {
    ("POST", "/api/v1/admin/refresh-schema"): (401, 403),
    ("PATCH", "/api/v1/admin/settings"): (422,),
    ("GET", "/api/v1/admin/connections"): (500,),
    ("POST", "/api/v1/admin/connections"): (422, 500),
    ("GET", "/api/v1/admin/connections/{connection_id}"): (404, 422, 500),
    ("PUT", "/api/v1/admin/connections/{connection_id}"): (404, 422, 500),
    ("DELETE", "/api/v1/admin/connections/{connection_id}"): (404, 409, 422, 500),
    ("POST", "/api/v1/admin/connections/{connection_id}/disable"): (404, 409, 422, 500),
    ("POST", "/api/v1/admin/connections/{connection_id}/enable"): (404, 409, 422, 500),
    ("POST", "/api/v1/admin/connections/{connection_id}/test"): (404, 422, 500),
    ("POST", "/api/v1/admin/connections/{connection_id}/refresh-schema"): (404, 422, 500, 502),
    ("GET", "/api/v1/admin/connections/{connection_id}/schema"): (404, 422, 500),
    ("GET", "/api/v1/admin/quotas/status"): (400, 422, 503),
    ("GET", "/api/v1/admin/quotas/{role_id}"): (400, 404),
    ("GET", "/api/v1/admin/detection/config"): (503,),
    ("PUT", "/api/v1/admin/detection/config"): (422, 503),
    ("GET", "/api/v1/admin/sso/providers"): (500, 503),
    ("POST", "/api/v1/admin/sso/providers"): (409, 422, 500),
    ("PUT", "/api/v1/admin/sso/providers/{provider_id}"): (404, 422, 500, 503),
    ("DELETE", "/api/v1/admin/sso/providers/{provider_id}"): (404, 500, 503),
    ("GET", "/api/v1/admin/sso/group-mappings"): (500,),
    ("POST", "/api/v1/admin/sso/group-mappings"): (404, 409, 422, 500),
    ("DELETE", "/api/v1/admin/sso/group-mappings/{mapping_id}"): (404, 500),
    ("GET", "/api/v1/admin/roles"): (500,),
    ("POST", "/api/v1/admin/roles"): (404, 409, 422, 500),
    ("GET", "/api/v1/admin/roles/{role_id}"): (404, 500),
    ("PUT", "/api/v1/admin/roles/{role_id}"): (404, 409, 422, 500),
    ("DELETE", "/api/v1/admin/roles/{role_id}"): (404, 422, 500),
    ("POST", "/api/v1/admin/roles/{role_id}/test-policy"): (400, 404, 422, 500),
    ("POST", "/api/v1/admin/audit/verify"): (500,),
    ("GET", "/api/v1/admin/audit/entries"): (422, 500),
    ("POST", "/api/v1/admin/audit/export"): (422, 500, 503),
    ("GET", "/api/v1/connections"): (503,),
    ("GET", "/api/v1/sessions"): (400, 422, 503),
    ("GET", "/api/v1/sessions/{session_id}"): (400, 404, 422, 503),
    ("DELETE", "/api/v1/sessions/{session_id}"): (404, 422, 503),
    ("PATCH", "/api/v1/sessions/{session_id}/connection"): (400, 404, 422, 503),
    ("PATCH", "/api/v1/feedback/{attempt_id}"): (404, 422, 503),
    ("GET", "/api/v1/auth/sso/providers"): (503,),
    ("GET", "/api/v1/auth/sso/oidc/callback"): (422, 503),
    ("POST", "/api/v1/auth/sso/saml/callback"): (422,),
}.items():
    _extend_operation_errors(_operation_key, _statuses)

ERROR_MODELS[("PUT", "/api/v1/admin/quotas/{role_id}")].update(
    {
        400: (ErrorResponse, ValidationErrorResponse),
        404: ErrorResponse,
        503: (ErrorResponse, QuotaSyncPendingErrorResponse),
    }
)
ERROR_MODELS[("DELETE", "/api/v1/admin/quotas/{role_id}")].update(
    {400: ErrorResponse, 404: ErrorResponse, 503: (ErrorResponse, QuotaSyncPendingErrorResponse)}
)
ERROR_MODELS[("POST", "/api/v1/admin/audit/export")][429] = QuotaExceededErrorResponse


def _route_operations(app: FastAPI) -> dict[OperationKey, APIRoute]:
    return {
        (method, route.path): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.include_in_schema
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }


def _operation(schema: dict[str, Any], operation_key: OperationKey) -> dict[str, Any]:
    method, path = operation_key
    return schema["paths"][path][method.lower()]


def _model_schema(response_models: ResponseModels) -> dict[str, Any]:
    if isinstance(response_models, tuple):
        return {"anyOf": [{"$ref": f"#/components/schemas/{model.__name__}"} for model in response_models]}
    return {"$ref": f"#/components/schemas/{response_models.__name__}"}


def _json_response(response_models: ResponseModels, description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": _model_schema(response_models)}},
    }


def _contract_models() -> list[ModelType]:
    models: set[ModelType] = set(REQUEST_MODELS.values())
    for _, response_models in SUCCESS_MODELS.values():
        models.update(response_models if isinstance(response_models, tuple) else (response_models,))
    for responses in ERROR_MODELS.values():
        for response_models in responses.values():
            models.update(response_models if isinstance(response_models, tuple) else (response_models,))
    return sorted(models, key=lambda model: model.__name__)


def _inject_model_definitions(schema: dict[str, Any]) -> None:
    _, definitions = models_json_schema(
        [(model, "validation") for model in _contract_models()],
        ref_template="#/components/schemas/{model}",
    )
    schema.setdefault("components", {}).setdefault("schemas", {}).update(definitions["$defs"])


def _patch_request_body(operation: dict[str, Any], request_model: ModelType) -> None:
    operation["requestBody"] = {
        "required": True,
        "content": {"application/json": {"schema": _model_schema(request_model)}},
    }


def _patch_success_response(operation: dict[str, Any], status_code: int, response_models: ResponseModels) -> None:
    operation["responses"][str(status_code)] = _json_response(response_models, "Successful response.")


def _patch_error_responses(operation: dict[str, Any], error_models: dict[int, ResponseModels]) -> None:
    for status_code in list(operation["responses"]):
        if int(status_code) >= 400:
            del operation["responses"][status_code]
    for status_code, response_models in error_models.items():
        operation["responses"][str(status_code)] = _json_response(response_models, "Sanitized error response.")


def _patch_redirect_response(operation: dict[str, Any]) -> None:
    operation["responses"].pop("200", None)
    operation["responses"]["302"] = {
        "description": "Browser navigation redirect.",
        "headers": {"Location": {"schema": {"type": "string"}}},
    }


def _patch_saml_form(operation: dict[str, Any]) -> None:
    operation["requestBody"] = {
        "required": True,
        "content": {
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "required": ["SAMLResponse", "RelayState"],
                    "properties": {"SAMLResponse": {"type": "string"}, "RelayState": {"type": "string"}},
                }
            }
        },
    }


def _patch_export_response(operation: dict[str, Any]) -> None:
    binary_schema = {"type": "string", "format": "binary"}
    operation["responses"]["200"] = {
        "description": "Filtered audit download.",
        "headers": {"Content-Disposition": {"schema": {"type": "string"}}},
        "content": {"text/csv": {"schema": binary_schema}, "application/json": {"schema": binary_schema}},
    }


def _patch_security(schema: dict[str, Any], operation_key: OperationKey, operation: dict[str, Any]) -> None:
    security_schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    security_schemes["sessionCookie"] = {"type": "apiKey", "in": "cookie", "name": "session_id"}
    security_schemes["AdminKey"] = {"type": "apiKey", "in": "header", "name": "X-Admin-Key"}
    if operation_key in PUBLIC_OPERATIONS:
        operation["security"] = []
    elif operation_key == ("POST", "/api/v1/admin/refresh-schema"):
        operation["security"] = [{"AdminKey": []}]
    else:
        operation["security"] = [{"sessionCookie": []}]


def _patch_operation(schema: dict[str, Any], operation_key: OperationKey) -> None:
    operation = _operation(schema, operation_key)
    operation["operationId"] = OPERATION_IDS[operation_key]
    _patch_security(schema, operation_key, operation)
    if operation_key in REQUEST_MODELS:
        _patch_request_body(operation, REQUEST_MODELS[operation_key])
    if operation_key in SUCCESS_MODELS:
        _patch_success_response(operation, *SUCCESS_MODELS[operation_key])
    _patch_error_responses(operation, ERROR_MODELS.get(operation_key, {}))


def _patch_special_operations(schema: dict[str, Any]) -> None:
    for operation_key in REDIRECT_OPERATIONS:
        _patch_redirect_response(_operation(schema, operation_key))
    _patch_saml_form(_operation(schema, ("POST", "/api/v1/auth/sso/saml/callback")))
    _patch_export_response(_operation(schema, ("POST", "/api/v1/admin/audit/export")))


def build_openapi_schema(app: FastAPI) -> dict[str, Any]:
    """Build the runtime-owned OpenAPI document."""
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    _inject_model_definitions(schema)
    for operation_key in OPERATION_IDS:
        _patch_operation(schema, operation_key)
    _patch_special_operations(schema)
    schema["servers"] = [{"url": "/"}]
    return schema


def configure_openapi(app: FastAPI) -> None:
    """Attach stable IDs and the canonical runtime schema builder."""
    runtime_operations = _route_operations(app)
    if runtime_operations.keys() != OPERATION_IDS.keys():
        raise RuntimeError("OpenAPI operation metadata does not match the application route set")
    for operation_key, route in runtime_operations.items():
        route.operation_id = OPERATION_IDS[operation_key]

    def runtime_openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = build_openapi_schema(app)
        return app.openapi_schema

    app.openapi = runtime_openapi
