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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
          ]
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
