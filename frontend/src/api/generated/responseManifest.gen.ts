// This file is auto-generated from backend/openapi.json.

export const responseOperationManifest = [
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "acceptQuery",
    "path": "/api/v1/query/accept",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AcceptedQuerySummary"
        },
        "status": "201"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0000"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "createAdminConnection",
    "path": "/api/v1/admin/connections",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionResponse"
        },
        "status": "201"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0001"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "createAuditFilterContext",
    "path": "/api/v1/admin/audit/filter-context",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AuditFilterContextResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0002"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "POST",
    "operationId": "createGroupMapping",
    "path": "/api/v1/admin/sso/group-mappings",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/GroupMappingResponse"
        },
        "status": "201"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0003"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": "Composite role saves own mapping changes; the standalone generated operation remains for API compatibility."
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "createRole",
    "path": "/api/v1/admin/roles",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/RoleDetailResponse"
        },
        "status": "201"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0004"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "POST",
    "operationId": "createSession",
    "path": "/api/v1/sessions",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/CreateSessionResponse"
        },
        "status": "201"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      }
    ],
    "unusedReason": "The first query submission creates the current workspace session."
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "createSsoProvider",
    "path": "/api/v1/admin/sso/providers",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SsoProviderResponse"
        },
        "status": "201"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0005"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteAdminConnection",
    "path": "/api/v1/admin/connections/{connection_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0006"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteGroupMapping",
    "path": "/api/v1/admin/sso/group-mappings/{mapping_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteHistoryEntry",
    "path": "/api/v1/history/{query_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteQuota",
    "path": "/api/v1/admin/quotas/{role_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/QuotaSyncPendingErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0007"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteRole",
    "path": "/api/v1/admin/roles/{role_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0008"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteSession",
    "path": "/api/v1/sessions/{session_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0009"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "DELETE",
    "operationId": "deleteSsoProvider",
    "path": "/api/v1/admin/sso/providers/{provider_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "disableAdminConnection",
    "path": "/api/v1/admin/connections/{connection_id}/disable",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0010"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "enableAdminConnection",
    "path": "/api/v1/admin/connections/{connection_id}/enable",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0011"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "blob_download",
    "method": "POST",
    "operationId": "exportAuditEntries",
    "path": "/api/v1/admin/audit/export",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "format": "binary",
          "type": "string"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0012"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QuotaExceededErrorResponse"
        },
        "status": "429"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "GET",
    "operationId": "getAdminConnection",
    "path": "/api/v1/admin/connections/{connection_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0013"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": "Safe list rows provide the editable non-secret connection fields."
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getAdminConnectionSchema",
    "path": "/api/v1/admin/connections/{connection_id}/schema",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionSchemaResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0014"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getAdminSettings",
    "path": "/api/v1/admin/settings",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AdminSettingsResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getAuditRetention",
    "path": "/api/v1/admin/audit/retention",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AuditRetentionResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getAuditStatus",
    "path": "/api/v1/admin/audit/status",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AuditStatusResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getDetectionConfig",
    "path": "/api/v1/admin/detection/config",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/DetectionThresholdRead"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "GET",
    "operationId": "getHealth",
    "path": "/health",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/LivenessResponse"
        },
        "status": "200"
      }
    ],
    "unusedReason": "Deployment probes call the public liveness route outside the React application."
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getHistoryEntry",
    "path": "/api/v1/history/{query_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AcceptedQueryDetail"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getMe",
    "path": "/api/v1/auth/me",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/UserProfile"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getQueryLimits",
    "path": "/api/v1/query/limits",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QueryLimitsResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "GET",
    "operationId": "getQuota",
    "path": "/api/v1/admin/quotas/{role_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/RoleQuotaConfig"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      }
    ],
    "unusedReason": "The quota page consumes the bounded list and status operations."
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getQuotaStatus",
    "path": "/api/v1/admin/quotas/status",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QuotaStatusResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0015"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "GET",
    "operationId": "getReadiness",
    "path": "/ready",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ReadinessResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/NotReadyResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": "Deployment probes call readiness outside the React application."
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getRole",
    "path": "/api/v1/admin/roles/{role_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/RoleDetailResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getSession",
    "path": "/api/v1/sessions/{session_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SessionDetail"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0016"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "getSessions",
    "path": "/api/v1/sessions",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SessionListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0017"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listAdminConnections",
    "path": "/api/v1/admin/connections",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "items": {
            "$ref": "#/components/schemas/ConnectionResponse"
          },
          "title": "Response List Connections Api V1 Admin Connections Get",
          "type": "array"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listAdminSsoProviders",
    "path": "/api/v1/admin/sso/providers",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SsoProviderListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "GET",
    "operationId": "listGroupMappings",
    "path": "/api/v1/admin/sso/group-mappings",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/GroupMappingListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": "Authoritative role detail embeds the mappings used by the role editor."
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listHistory",
    "path": "/api/v1/history",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/HistoryListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listQuotas",
    "path": "/api/v1/admin/quotas",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QuotaListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listRoles",
    "path": "/api/v1/admin/roles",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/RoleListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listSsoProviders",
    "path": "/api/v1/auth/sso/providers",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SsoProviderPublicListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "listUserConnections",
    "path": "/api/v1/connections",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/UserConnectionListResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "browser_redirect",
    "method": "GET",
    "operationId": "oidcCallback",
    "path": "/api/v1/auth/sso/oidc/callback",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0018"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "browser_redirect",
    "method": "GET",
    "operationId": "oidcLogin",
    "path": "/api/v1/auth/sso/oidc/login",
    "responses": [],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "refreshAdminConnectionSchema",
    "path": "/api/v1/admin/connections/{connection_id}/refresh-schema",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SchemaRefreshResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0019"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "502"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "POST",
    "operationId": "refreshSchema",
    "path": "/api/v1/admin/refresh-schema",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SchemaRefreshResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      }
    ],
    "unusedReason": "The UI uses the per-connection schema refresh operation."
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "regenerateQuery",
    "path": "/api/v1/query/regenerate",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/QueryResult"
            },
            {
              "$ref": "#/components/schemas/RefinePrompt"
            }
          ],
          "x-querycraft-union-validator": "union_0020"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0021"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QuotaExceededErrorResponse"
        },
        "status": "429"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "502"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "504"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "rejectQuery",
    "path": "/api/v1/query/reject",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/QueryResult"
            },
            {
              "$ref": "#/components/schemas/RefinePrompt"
            }
          ],
          "x-querycraft-union-validator": "union_0022"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0023"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QuotaExceededErrorResponse"
        },
        "status": "429"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "502"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "504"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "browser_redirect",
    "method": "POST",
    "operationId": "samlCallback",
    "path": "/api/v1/auth/sso/saml/callback",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "browser_redirect",
    "method": "GET",
    "operationId": "samlLogin",
    "path": "/api/v1/auth/sso/saml/login",
    "responses": [],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "GET",
    "operationId": "searchAuditEntries",
    "path": "/api/v1/admin/audit/entries",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AuditSearchResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0024"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "signIn",
    "path": "/api/v1/auth/sign-in",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/UserProfile"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "no_body",
    "method": "POST",
    "operationId": "signOut",
    "path": "/api/v1/auth/sign-out",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "submitQuestion",
    "path": "/api/v1/query/submit",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QueryResult"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0025"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/EvaluatorRejection"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/QuotaExceededErrorResponse"
        },
        "status": "429"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "502"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "504"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "testAdminConnection",
    "path": "/api/v1/admin/connections/{connection_id}/test",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionTestResult"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0026"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "testDraftRolePolicy",
    "path": "/api/v1/admin/roles/test-policy",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/PolicyTestResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0027"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "POST",
    "operationId": "testRolePolicy",
    "path": "/api/v1/admin/roles/{role_id}/test-policy",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/PolicyTestResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0028"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": "The editor validates unsaved policy drafts with testDraftRolePolicy."
  },
  {
    "classification": "consumed_json",
    "method": "PUT",
    "operationId": "updateAdminConnection",
    "path": "/api/v1/admin/connections/{connection_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ConnectionResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0029"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "PATCH",
    "operationId": "updateAdminSettings",
    "path": "/api/v1/admin/settings",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/UpdateAdminSettingsResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0030"
        },
        "status": "422"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "PUT",
    "operationId": "updateDetectionConfig",
    "path": "/api/v1/admin/detection/config",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/DetectionThresholdRead"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0031"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "unused",
    "method": "PATCH",
    "operationId": "updateFeedback",
    "path": "/api/v1/feedback/{attempt_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/FeedbackResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0032"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": "The current auto-save workspace does not render the legacy feedback control."
  },
  {
    "classification": "consumed_json",
    "method": "PUT",
    "operationId": "updateRole",
    "path": "/api/v1/admin/roles/{role_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/RoleDetailResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "409"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0033"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "PATCH",
    "operationId": "updateSessionConnection",
    "path": "/api/v1/sessions/{session_id}/connection",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SessionConnectionResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0034"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "PUT",
    "operationId": "updateSsoProvider",
    "path": "/api/v1/admin/sso/providers/{provider_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/SsoProviderResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/ValidationErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0035"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "PUT",
    "operationId": "upsertQuota",
    "path": "/api/v1/admin/quotas/{role_id}",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/RoleQuotaConfig"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "400"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "404"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ValidationErrorResponse"
        },
        "status": "422"
      },
      {
        "contentType": "application/json",
        "schema": {
          "anyOf": [
            {
              "$ref": "#/components/schemas/ErrorResponse"
            },
            {
              "$ref": "#/components/schemas/QuotaSyncPendingErrorResponse"
            }
          ],
          "x-querycraft-union-validator": "union_0036"
        },
        "status": "503"
      }
    ],
    "unusedReason": null
  },
  {
    "classification": "consumed_json",
    "method": "POST",
    "operationId": "verifyAuditChain",
    "path": "/api/v1/admin/audit/verify",
    "responses": [
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/AuditVerifyResponse"
        },
        "status": "200"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "401"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "403"
      },
      {
        "contentType": "application/json",
        "schema": {
          "$ref": "#/components/schemas/ErrorResponse"
        },
        "status": "500"
      }
    ],
    "unusedReason": null
  }
] as const;

export const responseComponentSchemas = {
  "AcceptedQueryDetail": {
    "description": "GET /history/{id} response.",
    "properties": {
      "accepted_at": {
        "title": "Accepted At",
        "type": "string"
      },
      "database_connection_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Connection Id",
        "x-querycraft-union-validator": "union_0037"
      },
      "database_connection_name": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Connection Name",
        "x-querycraft-union-validator": "union_0038"
      },
      "database_type": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Type",
        "x-querycraft-union-validator": "union_0039"
      },
      "generated_sql": {
        "title": "Generated Sql",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "llm_provider": {
        "title": "Llm Provider",
        "type": "string"
      },
      "question_text": {
        "title": "Question Text",
        "type": "string"
      },
      "result_columns": {
        "anyOf": [
          {
            "items": {},
            "type": "array"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Result Columns",
        "x-querycraft-union-validator": "union_0040"
      },
      "result_row_count": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Result Row Count",
        "x-querycraft-union-validator": "union_0041"
      },
      "result_rows": {
        "anyOf": [
          {
            "items": {},
            "type": "array"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Result Rows",
        "x-querycraft-union-validator": "union_0042"
      }
    },
    "required": [
      "id",
      "question_text",
      "generated_sql",
      "llm_provider",
      "accepted_at"
    ],
    "title": "AcceptedQueryDetail",
    "type": "object"
  },
  "AcceptedQuerySummary": {
    "description": "Summary of an accepted query (used in history list and accept response).",
    "properties": {
      "accepted_at": {
        "title": "Accepted At",
        "type": "string"
      },
      "database_connection_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Connection Id",
        "x-querycraft-union-validator": "union_0043"
      },
      "database_connection_name": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Connection Name",
        "x-querycraft-union-validator": "union_0044"
      },
      "database_type": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Type",
        "x-querycraft-union-validator": "union_0045"
      },
      "generated_sql": {
        "title": "Generated Sql",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "question_text": {
        "title": "Question Text",
        "type": "string"
      }
    },
    "required": [
      "id",
      "question_text",
      "generated_sql",
      "accepted_at"
    ],
    "title": "AcceptedQuerySummary",
    "type": "object"
  },
  "AdminSettingsResponse": {
    "description": "GET /admin/settings response.",
    "properties": {
      "llm_context_cap": {
        "title": "Llm Context Cap",
        "type": "integer"
      },
      "max_regenerate_attempts": {
        "title": "Max Regenerate Attempts",
        "type": "integer"
      }
    },
    "required": [
      "llm_context_cap",
      "max_regenerate_attempts"
    ],
    "title": "AdminSettingsResponse",
    "type": "object"
  },
  "AttemptSummary": {
    "description": "Summary of an accepted query within a session.",
    "properties": {
      "accepted_at": {
        "title": "Accepted At",
        "type": "string"
      },
      "database_connection_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Connection Id",
        "x-querycraft-union-validator": "union_0046"
      },
      "database_connection_name": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Connection Name",
        "x-querycraft-union-validator": "union_0047"
      },
      "database_type": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Database Type",
        "x-querycraft-union-validator": "union_0048"
      },
      "feedback": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Feedback",
        "x-querycraft-union-validator": "union_0049"
      },
      "generated_sql": {
        "title": "Generated Sql",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "question_text": {
        "title": "Question Text",
        "type": "string"
      },
      "result_columns": {
        "anyOf": [
          {
            "items": {},
            "type": "array"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Result Columns",
        "x-querycraft-union-validator": "union_0050"
      },
      "result_row_count": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Result Row Count",
        "x-querycraft-union-validator": "union_0051"
      },
      "result_rows": {
        "anyOf": [
          {
            "items": {},
            "type": "array"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Result Rows",
        "x-querycraft-union-validator": "union_0052"
      },
      "saved": {
        "title": "Saved",
        "type": "boolean"
      }
    },
    "required": [
      "id",
      "question_text",
      "generated_sql",
      "accepted_at",
      "saved"
    ],
    "title": "AttemptSummary",
    "type": "object"
  },
  "AuditEntryRead": {
    "description": "Search result representation of one audit entry.",
    "properties": {
      "action_type": {
        "title": "Action Type",
        "type": "string"
      },
      "actor_identity": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Actor Identity",
        "x-querycraft-union-validator": "union_0053"
      },
      "context": {
        "additionalProperties": true,
        "title": "Context",
        "type": "object"
      },
      "outcome": {
        "title": "Outcome",
        "type": "string"
      },
      "resource_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Resource Id",
        "x-querycraft-union-validator": "union_0054"
      },
      "resource_type": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Resource Type",
        "x-querycraft-union-validator": "union_0055"
      },
      "sequence_number": {
        "title": "Sequence Number",
        "type": "integer"
      },
      "timestamp": {
        "format": "date-time",
        "title": "Timestamp",
        "type": "string"
      }
    },
    "required": [
      "sequence_number",
      "timestamp",
      "action_type",
      "outcome",
      "context"
    ],
    "title": "AuditEntryRead",
    "type": "object"
  },
  "AuditFilterContextResponse": {
    "description": "Value-safe metadata returned for an opaque filter context.",
    "properties": {
      "applied_fields": {
        "items": {
          "enum": [
            "start_date",
            "end_date",
            "action_type",
            "actor_identity",
            "outcome",
            "resource_type"
          ],
          "type": "string"
        },
        "title": "Applied Fields",
        "type": "array"
      },
      "expires_at": {
        "format": "date-time",
        "title": "Expires At",
        "type": "string"
      },
      "filter_context": {
        "title": "Filter Context",
        "type": "string"
      }
    },
    "required": [
      "filter_context",
      "applied_fields",
      "expires_at"
    ],
    "title": "AuditFilterContextResponse",
    "type": "object"
  },
  "AuditRetentionResponse": {
    "description": "Current audit retention and last purge summary.",
    "properties": {
      "last_purge_at": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Last Purge At",
        "x-querycraft-union-validator": "union_0056"
      },
      "purged_count": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Purged Count",
        "x-querycraft-union-validator": "union_0057"
      },
      "retention_months": {
        "title": "Retention Months",
        "type": "integer"
      }
    },
    "required": [
      "retention_months"
    ],
    "title": "AuditRetentionResponse",
    "type": "object"
  },
  "AuditSearchPagination": {
    "description": "Audit search pagination metadata.",
    "properties": {
      "page": {
        "title": "Page",
        "type": "integer"
      },
      "page_size": {
        "title": "Page Size",
        "type": "integer"
      },
      "total_entries": {
        "title": "Total Entries",
        "type": "integer"
      },
      "total_pages": {
        "title": "Total Pages",
        "type": "integer"
      }
    },
    "required": [
      "page",
      "page_size",
      "total_entries",
      "total_pages"
    ],
    "title": "AuditSearchPagination",
    "type": "object"
  },
  "AuditSearchResponse": {
    "description": "Audit search response.",
    "properties": {
      "entries": {
        "items": {
          "$ref": "#/components/schemas/AuditEntryRead"
        },
        "title": "Entries",
        "type": "array"
      },
      "pagination": {
        "$ref": "#/components/schemas/AuditSearchPagination"
      }
    },
    "required": [
      "entries",
      "pagination"
    ],
    "title": "AuditSearchResponse",
    "type": "object"
  },
  "AuditStatusResponse": {
    "description": "Audit log status including last verification result.",
    "properties": {
      "last_verification": {
        "anyOf": [
          {
            "additionalProperties": true,
            "type": "object"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Last Verification",
        "x-querycraft-union-validator": "union_0058"
      },
      "total_entries": {
        "title": "Total Entries",
        "type": "integer"
      }
    },
    "required": [
      "total_entries"
    ],
    "title": "AuditStatusResponse",
    "type": "object"
  },
  "AuditVerifyResponse": {
    "description": "Result of an audit chain integrity verification.",
    "properties": {
      "entries_checked": {
        "title": "Entries Checked",
        "type": "integer"
      },
      "first_break_at": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "First Break At",
        "x-querycraft-union-validator": "union_0059"
      },
      "verified": {
        "title": "Verified",
        "type": "boolean"
      },
      "verified_at": {
        "title": "Verified At",
        "type": "string"
      }
    },
    "required": [
      "verified",
      "entries_checked",
      "verified_at"
    ],
    "title": "AuditVerifyResponse",
    "type": "object"
  },
  "ColumnMeta": {
    "description": "Column metadata in QueryResult.",
    "properties": {
      "masked": {
        "default": false,
        "title": "Masked",
        "type": "boolean"
      },
      "name": {
        "title": "Name",
        "type": "string"
      },
      "type": {
        "title": "Type",
        "type": "string"
      }
    },
    "required": [
      "name",
      "type"
    ],
    "title": "ColumnMeta",
    "type": "object"
  },
  "ConnectionPolicyResponse": {
    "description": "Persisted connection policy embedded in role detail.",
    "properties": {
      "allowed_tables": {
        "items": {
          "$ref": "#/components/schemas/TableColumnPolicy"
        },
        "title": "Allowed Tables",
        "type": "array"
      },
      "column_masks": {
        "items": {
          "$ref": "#/components/schemas/TableColumnPolicy"
        },
        "title": "Column Masks",
        "type": "array"
      },
      "connection_id": {
        "title": "Connection Id",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "row_filters": {
        "items": {
          "$ref": "#/components/schemas/RowFilterPolicy"
        },
        "title": "Row Filters",
        "type": "array"
      }
    },
    "required": [
      "id",
      "connection_id"
    ],
    "title": "ConnectionPolicyResponse",
    "type": "object"
  },
  "ConnectionResponse": {
    "description": "Response body for connection details with write-only metadata omitted.",
    "properties": {
      "created_at": {
        "format": "date-time",
        "title": "Created At",
        "type": "string"
      },
      "database_name": {
        "title": "Database Name",
        "type": "string"
      },
      "database_type": {
        "$ref": "#/components/schemas/DatabaseType"
      },
      "display_name": {
        "title": "Display Name",
        "type": "string"
      },
      "health_error_category": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Health Error Category",
        "x-querycraft-union-validator": "union_0060"
      },
      "health_status": {
        "$ref": "#/components/schemas/HealthStatus"
      },
      "id": {
        "format": "uuid",
        "title": "Id",
        "type": "string"
      },
      "last_health_check_at": {
        "anyOf": [
          {
            "format": "date-time",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Last Health Check At",
        "x-querycraft-union-validator": "union_0061"
      },
      "lifecycle_state": {
        "$ref": "#/components/schemas/LifecycleState"
      },
      "port": {
        "title": "Port",
        "type": "integer"
      },
      "schema_introspection_status": {
        "$ref": "#/components/schemas/SchemaIntrospectionStatus"
      },
      "schema_last_refreshed_at": {
        "anyOf": [
          {
            "format": "date-time",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Schema Last Refreshed At",
        "x-querycraft-union-validator": "union_0062"
      },
      "ssl_mode": {
        "title": "Ssl Mode",
        "type": "string"
      },
      "updated_at": {
        "format": "date-time",
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "id",
      "display_name",
      "database_type",
      "port",
      "database_name",
      "ssl_mode",
      "lifecycle_state",
      "health_status",
      "last_health_check_at",
      "health_error_category",
      "schema_introspection_status",
      "schema_last_refreshed_at",
      "created_at",
      "updated_at"
    ],
    "title": "ConnectionResponse",
    "type": "object"
  },
  "ConnectionSchemaColumn": {
    "description": "Column metadata in a connection schema summary.",
    "properties": {
      "column_name": {
        "title": "Column Name",
        "type": "string"
      },
      "data_type": {
        "title": "Data Type",
        "type": "string"
      },
      "foreign_key": {
        "anyOf": [
          {
            "$ref": "#/components/schemas/ConnectionSchemaForeignKey"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "x-querycraft-union-validator": "union_0063"
      },
      "is_primary_key": {
        "title": "Is Primary Key",
        "type": "boolean"
      }
    },
    "required": [
      "column_name",
      "data_type",
      "is_primary_key"
    ],
    "title": "ConnectionSchemaColumn",
    "type": "object"
  },
  "ConnectionSchemaForeignKey": {
    "description": "Foreign-key target in a connection schema summary.",
    "properties": {
      "column": {
        "title": "Column",
        "type": "string"
      },
      "table": {
        "title": "Table",
        "type": "string"
      }
    },
    "required": [
      "table",
      "column"
    ],
    "title": "ConnectionSchemaForeignKey",
    "type": "object"
  },
  "ConnectionSchemaResponse": {
    "description": "Introspected schema for one source connection.",
    "properties": {
      "connection_id": {
        "format": "uuid",
        "title": "Connection Id",
        "type": "string"
      },
      "introspected_at": {
        "anyOf": [
          {
            "format": "date-time",
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Introspected At",
        "x-querycraft-union-validator": "union_0064"
      },
      "tables": {
        "items": {
          "$ref": "#/components/schemas/ConnectionSchemaTable"
        },
        "title": "Tables",
        "type": "array"
      }
    },
    "required": [
      "connection_id",
      "tables"
    ],
    "title": "ConnectionSchemaResponse",
    "type": "object"
  },
  "ConnectionSchemaTable": {
    "description": "Table metadata in a connection schema summary.",
    "properties": {
      "column_count": {
        "title": "Column Count",
        "type": "integer"
      },
      "columns": {
        "items": {
          "$ref": "#/components/schemas/ConnectionSchemaColumn"
        },
        "title": "Columns",
        "type": "array"
      },
      "table_name": {
        "title": "Table Name",
        "type": "string"
      }
    },
    "required": [
      "table_name",
      "column_count",
      "columns"
    ],
    "title": "ConnectionSchemaTable",
    "type": "object"
  },
  "ConnectionTestResult": {
    "description": "Response body for connection test result.",
    "properties": {
      "error_category": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Error Category",
        "x-querycraft-union-validator": "union_0065"
      },
      "latency_ms": {
        "anyOf": [
          {
            "type": "number"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Latency Ms",
        "x-querycraft-union-validator": "union_0066"
      },
      "message_key": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Message Key",
        "x-querycraft-union-validator": "union_0067"
      },
      "status": {
        "title": "Status",
        "type": "string"
      },
      "tested_at": {
        "format": "date-time",
        "title": "Tested At",
        "type": "string"
      }
    },
    "required": [
      "status",
      "tested_at"
    ],
    "title": "ConnectionTestResult",
    "type": "object"
  },
  "CreateSessionResponse": {
    "description": "Response after creating a session.",
    "properties": {
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "preview_text": {
        "title": "Preview Text",
        "type": "string"
      }
    },
    "required": [
      "id",
      "preview_text",
      "created_at"
    ],
    "title": "CreateSessionResponse",
    "type": "object"
  },
  "DatabaseType": {
    "description": "Supported source database types.",
    "enum": [
      "postgresql",
      "mysql",
      "mssql"
    ],
    "title": "DatabaseType",
    "type": "string"
  },
  "DetectionThresholdRead": {
    "description": "Current detection threshold configuration.",
    "properties": {
      "block_confidence": {
        "title": "Block Confidence",
        "type": "number"
      },
      "flag_confidence": {
        "title": "Flag Confidence",
        "type": "number"
      },
      "updated_at": {
        "format": "date-time",
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "block_confidence",
      "flag_confidence",
      "updated_at"
    ],
    "title": "DetectionThresholdRead",
    "type": "object"
  },
  "ErrorResponse": {
    "description": "Constant, user-safe error response.",
    "properties": {
      "error": {
        "title": "Error",
        "type": "string"
      },
      "field": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Field",
        "x-querycraft-union-validator": "union_0068"
      },
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "message_params": {
        "anyOf": [
          {
            "additionalProperties": true,
            "type": "object"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Message Params",
        "x-querycraft-union-validator": "union_0069"
      }
    },
    "required": [
      "error",
      "message_key"
    ],
    "title": "ErrorResponse",
    "type": "object"
  },
  "EvaluatorRejection": {
    "description": "Evaluator rejection response (HTTP 422).",
    "properties": {
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "message_params": {
        "anyOf": [
          {
            "additionalProperties": true,
            "type": "object"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Message Params",
        "x-querycraft-union-validator": "union_0070"
      },
      "violations": {
        "items": {
          "$ref": "#/components/schemas/Violation"
        },
        "title": "Violations",
        "type": "array"
      }
    },
    "required": [
      "message_key",
      "violations"
    ],
    "title": "EvaluatorRejection",
    "type": "object"
  },
  "FeedbackResponse": {
    "description": "Response after updating feedback.",
    "properties": {
      "feedback": {
        "title": "Feedback",
        "type": "integer"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "saved": {
        "title": "Saved",
        "type": "boolean"
      }
    },
    "required": [
      "id",
      "feedback",
      "saved"
    ],
    "title": "FeedbackResponse",
    "type": "object"
  },
  "GroupMappingListResponse": {
    "description": "Configured SSO group-to-role mappings.",
    "properties": {
      "mappings": {
        "items": {
          "$ref": "#/components/schemas/GroupMappingResponse"
        },
        "title": "Mappings",
        "type": "array"
      }
    },
    "required": [
      "mappings"
    ],
    "title": "GroupMappingListResponse",
    "type": "object"
  },
  "GroupMappingResponse": {
    "description": "SSO group-to-role mapping response.",
    "properties": {
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "role_id": {
        "title": "Role Id",
        "type": "string"
      },
      "role_name": {
        "title": "Role Name",
        "type": "string"
      },
      "sso_group_value": {
        "title": "Sso Group Value",
        "type": "string"
      }
    },
    "required": [
      "id",
      "sso_group_value",
      "role_id",
      "role_name",
      "created_at"
    ],
    "title": "GroupMappingResponse",
    "type": "object"
  },
  "HealthStatus": {
    "description": "Connection health check results.",
    "enum": [
      "untested",
      "healthy",
      "unhealthy"
    ],
    "title": "HealthStatus",
    "type": "string"
  },
  "HistoryListResponse": {
    "description": "GET /history response.",
    "properties": {
      "items": {
        "items": {
          "$ref": "#/components/schemas/AcceptedQuerySummary"
        },
        "title": "Items",
        "type": "array"
      },
      "next_cursor": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Next Cursor",
        "x-querycraft-union-validator": "union_0071"
      },
      "total": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Total",
        "x-querycraft-union-validator": "union_0072"
      }
    },
    "required": [
      "items"
    ],
    "title": "HistoryListResponse",
    "type": "object"
  },
  "LifecycleState": {
    "description": "Connection lifecycle states.",
    "enum": [
      "active",
      "disabled"
    ],
    "title": "LifecycleState",
    "type": "string"
  },
  "LivenessResponse": {
    "properties": {
      "status": {
        "const": "live",
        "default": "live",
        "title": "Status",
        "type": "string"
      }
    },
    "title": "LivenessResponse",
    "type": "object"
  },
  "NotReadyResponse": {
    "properties": {
      "status": {
        "const": "not_ready",
        "default": "not_ready",
        "title": "Status",
        "type": "string"
      }
    },
    "title": "NotReadyResponse",
    "type": "object"
  },
  "PolicyTestResponse": {
    "description": "Result of a policy dry-run test.",
    "properties": {
      "accessible_columns": {
        "additionalProperties": {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "title": "Accessible Columns",
        "type": "object"
      },
      "accessible_tables": {
        "items": {
          "type": "string"
        },
        "title": "Accessible Tables",
        "type": "array"
      },
      "applicable_row_filters": {
        "items": {
          "additionalProperties": true,
          "type": "object"
        },
        "title": "Applicable Row Filters",
        "type": "array"
      },
      "blocked_tables": {
        "items": {
          "type": "string"
        },
        "title": "Blocked Tables",
        "type": "array"
      },
      "masked_columns": {
        "additionalProperties": {
          "items": {
            "type": "string"
          },
          "type": "array"
        },
        "title": "Masked Columns",
        "type": "object"
      },
      "message_key": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "description": "Set to 'error.queryBlockedPolicy' when sample_sql evaluation blocks the query. Null when sample_sql is absent or the rule allows the query.",
        "title": "Message Key",
        "x-querycraft-union-validator": "union_0073"
      },
      "would_be_allowed": {
        "default": true,
        "title": "Would Be Allowed",
        "type": "boolean"
      }
    },
    "title": "PolicyTestResponse",
    "type": "object"
  },
  "QueryLimitsResponse": {
    "description": "Safe public subset of the query submission configuration.",
    "properties": {
      "max_question_length": {
        "exclusiveMinimum": 0,
        "title": "Max Question Length",
        "type": "integer"
      }
    },
    "required": [
      "max_question_length"
    ],
    "title": "QueryLimitsResponse",
    "type": "object"
  },
  "QueryResult": {
    "description": "Successful query execution response.",
    "properties": {
      "accepted_query_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Accepted Query Id",
        "x-querycraft-union-validator": "union_0074"
      },
      "attempt_id": {
        "title": "Attempt Id",
        "type": "string"
      },
      "attempt_number": {
        "title": "Attempt Number",
        "type": "integer"
      },
      "columns": {
        "items": {
          "$ref": "#/components/schemas/ColumnMeta"
        },
        "title": "Columns",
        "type": "array"
      },
      "generated_sql": {
        "title": "Generated Sql",
        "type": "string"
      },
      "is_last_auto_retry": {
        "title": "Is Last Auto Retry",
        "type": "boolean"
      },
      "kind": {
        "default": "result",
        "pattern": "^result$",
        "title": "Kind",
        "type": "string"
      },
      "question": {
        "title": "Question",
        "type": "string"
      },
      "row_count": {
        "title": "Row Count",
        "type": "integer"
      },
      "rows": {
        "items": {
          "items": {},
          "type": "array"
        },
        "title": "Rows",
        "type": "array"
      },
      "session_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Session Id",
        "x-querycraft-union-validator": "union_0075"
      }
    },
    "required": [
      "attempt_id",
      "question",
      "generated_sql",
      "columns",
      "rows",
      "row_count",
      "attempt_number",
      "is_last_auto_retry"
    ],
    "title": "QueryResult",
    "type": "object"
  },
  "QuotaDimensionStatus": {
    "description": "Current usage for one quota dimension.",
    "properties": {
      "limit": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Limit",
        "x-querycraft-union-validator": "union_0076"
      },
      "remaining": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Remaining",
        "x-querycraft-union-validator": "union_0077"
      },
      "used": {
        "title": "Used",
        "type": "integer"
      }
    },
    "required": [
      "used"
    ],
    "title": "QuotaDimensionStatus",
    "type": "object"
  },
  "QuotaExceededErrorResponse": {
    "description": "Quota denial with a safe retry timestamp.",
    "properties": {
      "error": {
        "const": "quota_exceeded",
        "title": "Error",
        "type": "string"
      },
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "reset_at": {
        "title": "Reset At",
        "type": "string"
      }
    },
    "required": [
      "error",
      "message_key",
      "reset_at"
    ],
    "title": "QuotaExceededErrorResponse",
    "type": "object"
  },
  "QuotaListResponse": {
    "description": "Quota configuration list response.",
    "properties": {
      "quotas": {
        "items": {
          "$ref": "#/components/schemas/RoleQuotaConfig"
        },
        "title": "Quotas",
        "type": "array"
      }
    },
    "required": [
      "quotas"
    ],
    "title": "QuotaListResponse",
    "type": "object"
  },
  "QuotaStatusResponse": {
    "description": "Quota status list response.",
    "properties": {
      "next_cursor": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Next Cursor",
        "x-querycraft-union-validator": "union_0078"
      },
      "status": {
        "items": {
          "$ref": "#/components/schemas/RoleQuotaStatus"
        },
        "title": "Status",
        "type": "array"
      },
      "total": {
        "title": "Total",
        "type": "integer"
      }
    },
    "required": [
      "status",
      "total",
      "next_cursor"
    ],
    "title": "QuotaStatusResponse",
    "type": "object"
  },
  "QuotaSyncPendingErrorResponse": {
    "description": "Durable quota mutation awaiting cache publication.",
    "properties": {
      "error": {
        "const": "quota_sync_pending",
        "title": "Error",
        "type": "string"
      },
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "mutation_applied": {
        "const": true,
        "title": "Mutation Applied",
        "type": "boolean"
      }
    },
    "required": [
      "error",
      "message_key",
      "mutation_applied"
    ],
    "title": "QuotaSyncPendingErrorResponse",
    "type": "object"
  },
  "ReadinessResponse": {
    "properties": {
      "status": {
        "const": "ready",
        "default": "ready",
        "title": "Status",
        "type": "string"
      }
    },
    "title": "ReadinessResponse",
    "type": "object"
  },
  "RefinePrompt": {
    "description": "Max-retries-reached response (kind=refine).",
    "properties": {
      "kind": {
        "default": "refine",
        "pattern": "^refine$",
        "title": "Kind",
        "type": "string"
      },
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "message_params": {
        "anyOf": [
          {
            "additionalProperties": true,
            "type": "object"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Message Params",
        "x-querycraft-union-validator": "union_0079"
      },
      "should_refine": {
        "title": "Should Refine",
        "type": "boolean"
      }
    },
    "required": [
      "message_key",
      "should_refine"
    ],
    "title": "RefinePrompt",
    "type": "object"
  },
  "RoleDetailResponse": {
    "description": "Full role detail including connection policies.",
    "properties": {
      "connection_policies": {
        "items": {
          "$ref": "#/components/schemas/ConnectionPolicyResponse"
        },
        "title": "Connection Policies",
        "type": "array"
      },
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "description": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Description",
        "x-querycraft-union-validator": "union_0080"
      },
      "group_mappings": {
        "items": {
          "$ref": "#/components/schemas/RoleGroupMappingSummary"
        },
        "title": "Group Mappings",
        "type": "array"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "is_builtin": {
        "default": false,
        "title": "Is Builtin",
        "type": "boolean"
      },
      "name": {
        "title": "Name",
        "type": "string"
      },
      "permissions": {
        "items": {
          "type": "string"
        },
        "title": "Permissions",
        "type": "array"
      },
      "priority": {
        "title": "Priority",
        "type": "integer"
      },
      "updated_at": {
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "id",
      "name",
      "priority",
      "created_at",
      "updated_at"
    ],
    "title": "RoleDetailResponse",
    "type": "object"
  },
  "RoleGroupMappingSummary": {
    "description": "Group mapping embedded in a role response.",
    "properties": {
      "id": {
        "title": "Id",
        "type": "string"
      },
      "sso_group_value": {
        "title": "Sso Group Value",
        "type": "string"
      }
    },
    "required": [
      "id",
      "sso_group_value"
    ],
    "title": "RoleGroupMappingSummary",
    "type": "object"
  },
  "RoleListResponse": {
    "description": "Configured platform roles.",
    "properties": {
      "roles": {
        "items": {
          "$ref": "#/components/schemas/RoleResponse"
        },
        "title": "Roles",
        "type": "array"
      }
    },
    "required": [
      "roles"
    ],
    "title": "RoleListResponse",
    "type": "object"
  },
  "RoleQuotaConfig": {
    "description": "Quota configuration for one role.",
    "properties": {
      "created_at": {
        "format": "date-time",
        "title": "Created At",
        "type": "string"
      },
      "daily_execution_limit": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Daily Execution Limit",
        "x-querycraft-union-validator": "union_0081"
      },
      "daily_export_limit": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Daily Export Limit",
        "x-querycraft-union-validator": "union_0082"
      },
      "daily_query_limit": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Daily Query Limit",
        "x-querycraft-union-validator": "union_0083"
      },
      "role_id": {
        "format": "uuid",
        "title": "Role Id",
        "type": "string"
      },
      "role_name": {
        "title": "Role Name",
        "type": "string"
      },
      "updated_at": {
        "format": "date-time",
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "role_id",
      "role_name",
      "created_at",
      "updated_at"
    ],
    "title": "RoleQuotaConfig",
    "type": "object"
  },
  "RoleQuotaStatus": {
    "description": "Current quota status for one role.",
    "properties": {
      "dimensions": {
        "additionalProperties": {
          "$ref": "#/components/schemas/QuotaDimensionStatus"
        },
        "title": "Dimensions",
        "type": "object"
      },
      "reset_at": {
        "format": "date-time",
        "title": "Reset At",
        "type": "string"
      },
      "role_id": {
        "format": "uuid",
        "title": "Role Id",
        "type": "string"
      },
      "role_name": {
        "title": "Role Name",
        "type": "string"
      }
    },
    "required": [
      "role_id",
      "role_name",
      "dimensions",
      "reset_at"
    ],
    "title": "RoleQuotaStatus",
    "type": "object"
  },
  "RoleResponse": {
    "description": "List view of a role.",
    "properties": {
      "connection_policy_count": {
        "default": 0,
        "title": "Connection Policy Count",
        "type": "integer"
      },
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "description": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Description",
        "x-querycraft-union-validator": "union_0084"
      },
      "group_mappings": {
        "items": {
          "$ref": "#/components/schemas/RoleGroupMappingSummary"
        },
        "title": "Group Mappings",
        "type": "array"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "is_builtin": {
        "default": false,
        "title": "Is Builtin",
        "type": "boolean"
      },
      "name": {
        "title": "Name",
        "type": "string"
      },
      "permissions": {
        "items": {
          "type": "string"
        },
        "title": "Permissions",
        "type": "array"
      },
      "priority": {
        "title": "Priority",
        "type": "integer"
      },
      "updated_at": {
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "id",
      "name",
      "priority",
      "created_at",
      "updated_at"
    ],
    "title": "RoleResponse",
    "type": "object"
  },
  "RowFilterPolicy": {
    "description": "Row-filter entry in a persisted policy.",
    "properties": {
      "filter": {
        "title": "Filter",
        "type": "string"
      },
      "table": {
        "title": "Table",
        "type": "string"
      }
    },
    "required": [
      "table",
      "filter"
    ],
    "title": "RowFilterPolicy",
    "type": "object"
  },
  "SchemaIntrospectionStatus": {
    "description": "Schema introspection lifecycle states.",
    "enum": [
      "none",
      "success",
      "failed",
      "stale"
    ],
    "title": "SchemaIntrospectionStatus",
    "type": "string"
  },
  "SchemaRefreshResponse": {
    "description": "Schema introspection statistics returned by refresh operations.",
    "properties": {
      "approximate_tokens": {
        "anyOf": [
          {
            "type": "integer"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Approximate Tokens",
        "x-querycraft-union-validator": "union_0085"
      },
      "columns_count": {
        "title": "Columns Count",
        "type": "integer"
      },
      "refreshed_at": {
        "format": "date-time",
        "title": "Refreshed At",
        "type": "string"
      },
      "tables_count": {
        "title": "Tables Count",
        "type": "integer"
      }
    },
    "required": [
      "tables_count",
      "columns_count",
      "refreshed_at"
    ],
    "title": "SchemaRefreshResponse",
    "type": "object"
  },
  "SessionConnectionResponse": {
    "description": "Response after updating session connection.",
    "properties": {
      "connection_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Connection Id",
        "x-querycraft-union-validator": "union_0086"
      },
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "last_activity_at": {
        "title": "Last Activity At",
        "type": "string"
      },
      "preview_text": {
        "title": "Preview Text",
        "type": "string"
      }
    },
    "required": [
      "id",
      "preview_text",
      "created_at",
      "last_activity_at"
    ],
    "title": "SessionConnectionResponse",
    "type": "object"
  },
  "SessionDetail": {
    "description": "Full session detail with conversation history.",
    "properties": {
      "attempts": {
        "items": {
          "$ref": "#/components/schemas/AttemptSummary"
        },
        "title": "Attempts",
        "type": "array"
      },
      "attempts_next_cursor": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Attempts Next Cursor",
        "x-querycraft-union-validator": "union_0087"
      },
      "attempts_total": {
        "title": "Attempts Total",
        "type": "integer"
      },
      "connection_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Connection Id",
        "x-querycraft-union-validator": "union_0088"
      },
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "last_activity_at": {
        "title": "Last Activity At",
        "type": "string"
      },
      "preview_text": {
        "title": "Preview Text",
        "type": "string"
      }
    },
    "required": [
      "id",
      "preview_text",
      "created_at",
      "last_activity_at",
      "attempts",
      "attempts_total",
      "attempts_next_cursor"
    ],
    "title": "SessionDetail",
    "type": "object"
  },
  "SessionListResponse": {
    "description": "Response for listing sessions.",
    "properties": {
      "items": {
        "items": {
          "$ref": "#/components/schemas/SessionSummary"
        },
        "title": "Items",
        "type": "array"
      },
      "next_cursor": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "title": "Next Cursor",
        "x-querycraft-union-validator": "union_0089"
      },
      "total": {
        "title": "Total",
        "type": "integer"
      }
    },
    "required": [
      "items",
      "total",
      "next_cursor"
    ],
    "title": "SessionListResponse",
    "type": "object"
  },
  "SessionSummary": {
    "description": "Summary of a session for list views.",
    "properties": {
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "last_activity_at": {
        "title": "Last Activity At",
        "type": "string"
      },
      "preview_text": {
        "title": "Preview Text",
        "type": "string"
      }
    },
    "required": [
      "id",
      "preview_text",
      "created_at",
      "last_activity_at"
    ],
    "title": "SessionSummary",
    "type": "object"
  },
  "SsoProviderListResponse": {
    "description": "Admin-visible SSO providers with masked secrets.",
    "properties": {
      "providers": {
        "items": {
          "$ref": "#/components/schemas/SsoProviderResponse"
        },
        "title": "Providers",
        "type": "array"
      }
    },
    "required": [
      "providers"
    ],
    "title": "SsoProviderListResponse",
    "type": "object"
  },
  "SsoProviderPublic": {
    "description": "Public SSO provider info for sign-in page.",
    "properties": {
      "display_name": {
        "title": "Display Name",
        "type": "string"
      },
      "login_url": {
        "title": "Login Url",
        "type": "string"
      },
      "protocol": {
        "title": "Protocol",
        "type": "string"
      }
    },
    "required": [
      "protocol",
      "display_name",
      "login_url"
    ],
    "title": "SsoProviderPublic",
    "type": "object"
  },
  "SsoProviderPublicListResponse": {
    "description": "Public active SSO providers.",
    "properties": {
      "providers": {
        "items": {
          "$ref": "#/components/schemas/SsoProviderPublic"
        },
        "title": "Providers",
        "type": "array"
      }
    },
    "required": [
      "providers"
    ],
    "title": "SsoProviderPublicListResponse",
    "type": "object"
  },
  "SsoProviderResponse": {
    "description": "Admin-facing SSO provider response with masked secrets.",
    "properties": {
      "client_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Client Id",
        "x-querycraft-union-validator": "union_0090"
      },
      "client_secret_masked": {
        "default": "●●●●●●●●",
        "title": "Client Secret Masked",
        "type": "string"
      },
      "created_at": {
        "title": "Created At",
        "type": "string"
      },
      "display_name": {
        "title": "Display Name",
        "type": "string"
      },
      "group_claim_name": {
        "default": "groups",
        "title": "Group Claim Name",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "is_active": {
        "default": true,
        "title": "Is Active",
        "type": "boolean"
      },
      "issuer_url": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Issuer Url",
        "x-querycraft-union-validator": "union_0091"
      },
      "protocol": {
        "title": "Protocol",
        "type": "string"
      },
      "redirect_uri": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Redirect Uri",
        "x-querycraft-union-validator": "union_0092"
      },
      "saml_certificate_masked": {
        "default": "●●●●●●●●",
        "title": "Saml Certificate Masked",
        "type": "string"
      },
      "saml_entity_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Saml Entity Id",
        "x-querycraft-union-validator": "union_0093"
      },
      "saml_metadata_url": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Saml Metadata Url",
        "x-querycraft-union-validator": "union_0094"
      },
      "saml_metadata_xml_masked": {
        "default": "●●●●●●●●",
        "title": "Saml Metadata Xml Masked",
        "type": "string"
      },
      "scopes": {
        "default": "openid email profile groups",
        "title": "Scopes",
        "type": "string"
      },
      "updated_at": {
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "id",
      "protocol",
      "display_name",
      "created_at",
      "updated_at"
    ],
    "title": "SsoProviderResponse",
    "type": "object"
  },
  "TableColumnPolicy": {
    "description": "Allowed-table or column-mask entry in a persisted policy.",
    "properties": {
      "columns": {
        "items": {
          "type": "string"
        },
        "title": "Columns",
        "type": "array"
      },
      "table": {
        "title": "Table",
        "type": "string"
      }
    },
    "required": [
      "table",
      "columns"
    ],
    "title": "TableColumnPolicy",
    "type": "object"
  },
  "UpdateAdminSettingsResponse": {
    "description": "Response after updating admin settings.",
    "properties": {
      "llm_context_cap": {
        "title": "Llm Context Cap",
        "type": "integer"
      },
      "max_regenerate_attempts": {
        "title": "Max Regenerate Attempts",
        "type": "integer"
      },
      "updated_at": {
        "title": "Updated At",
        "type": "string"
      }
    },
    "required": [
      "llm_context_cap",
      "max_regenerate_attempts",
      "updated_at"
    ],
    "title": "UpdateAdminSettingsResponse",
    "type": "object"
  },
  "UserConnectionListResponse": {
    "description": "Response body for user-facing connection list.",
    "properties": {
      "connections": {
        "items": {
          "$ref": "#/components/schemas/UserConnectionResponse"
        },
        "title": "Connections",
        "type": "array"
      }
    },
    "required": [
      "connections"
    ],
    "title": "UserConnectionListResponse",
    "type": "object"
  },
  "UserConnectionResponse": {
    "description": "Minimal user-facing connection response (T-428, FR-077).\n\nOnly id, display_name, and database_type. No host/port/credentials.",
    "properties": {
      "database_type": {
        "$ref": "#/components/schemas/DatabaseType"
      },
      "display_name": {
        "title": "Display Name",
        "type": "string"
      },
      "id": {
        "format": "uuid",
        "title": "Id",
        "type": "string"
      }
    },
    "required": [
      "id",
      "display_name",
      "database_type"
    ],
    "title": "UserConnectionResponse",
    "type": "object"
  },
  "UserProfile": {
    "description": "GET /auth/me response — extended for Phase 5 SSO/RBAC.",
    "properties": {
      "auth_provider": {
        "default": "local",
        "title": "Auth Provider",
        "type": "string"
      },
      "display_name": {
        "title": "Display Name",
        "type": "string"
      },
      "id": {
        "title": "Id",
        "type": "string"
      },
      "permissions": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Permissions",
        "type": "array"
      },
      "role": {
        "title": "Role",
        "type": "string"
      },
      "role_id": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Role Id",
        "x-querycraft-union-validator": "union_0095"
      },
      "role_name": {
        "anyOf": [
          {
            "type": "string"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Role Name",
        "x-querycraft-union-validator": "union_0096"
      },
      "username": {
        "title": "Username",
        "type": "string"
      }
    },
    "required": [
      "id",
      "username",
      "display_name",
      "role"
    ],
    "title": "UserProfile",
    "type": "object"
  },
  "ValidationErrorDetail": {
    "description": "One sanitized request-validation failure.",
    "properties": {
      "field": {
        "title": "Field",
        "type": "string"
      },
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "message_params": {
        "anyOf": [
          {
            "additionalProperties": true,
            "type": "object"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Message Params",
        "x-querycraft-union-validator": "union_0097"
      }
    },
    "required": [
      "field",
      "message_key"
    ],
    "title": "ValidationErrorDetail",
    "type": "object"
  },
  "ValidationErrorResponse": {
    "description": "Sanitized request-validation response.",
    "properties": {
      "details": {
        "items": {
          "$ref": "#/components/schemas/ValidationErrorDetail"
        },
        "title": "Details",
        "type": "array"
      },
      "error": {
        "const": "validation",
        "title": "Error",
        "type": "string"
      },
      "message_key": {
        "title": "Message Key",
        "type": "string"
      }
    },
    "required": [
      "error",
      "message_key",
      "details"
    ],
    "title": "ValidationErrorResponse",
    "type": "object"
  },
  "Violation": {
    "description": "Single evaluator rule failure.",
    "properties": {
      "message_key": {
        "title": "Message Key",
        "type": "string"
      },
      "message_params": {
        "anyOf": [
          {
            "additionalProperties": true,
            "type": "object"
          },
          {
            "type": "null"
          }
        ],
        "default": null,
        "title": "Message Params",
        "x-querycraft-union-validator": "union_0098"
      },
      "rule": {
        "title": "Rule",
        "type": "string"
      }
    },
    "required": [
      "rule",
      "message_key"
    ],
    "title": "Violation",
    "type": "object"
  }
} as const;
