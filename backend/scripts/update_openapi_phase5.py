"""Update openapi.yaml with Phase 5 schemas and endpoints (T-633).

Adds:
- Extended UserProfile (role_id, role_name, permissions, auth_provider)
- SSO schemas (SsoProviderPublic, Response, Create, Update)
- Role schemas (RoleResponse, RoleDetailResponse, Create, Update)
- Policy test schemas (PolicyTestRequest, PolicyTestResponse)
- Group mapping schemas (GroupMappingResponse, GroupMappingCreate)
- Audit schemas (AuditVerifyResponse, AuditStatusResponse)
- New error codes
- Phase 5 endpoint stubs (for future wave implementation)
"""

import yaml

SPEC_PATH = "/home/avril/QueryCraft/specs/001-core-text-to-sql/contracts/openapi.yaml"

with open(SPEC_PATH) as f:
    spec = yaml.safe_load(f)

# 1. Extend UserProfile schema
spec["components"]["schemas"]["UserProfile"]["properties"]["role_id"] = {
    "type": "string", "format": "uuid", "nullable": True
}
spec["components"]["schemas"]["UserProfile"]["properties"]["role_name"] = {
    "type": "string", "nullable": True
}
spec["components"]["schemas"]["UserProfile"]["properties"]["permissions"] = {
    "type": "array", "items": {"type": "string"}, "default": []
}
spec["components"]["schemas"]["UserProfile"]["properties"]["auth_provider"] = {
    "type": "string", "enum": ["local", "oidc", "saml"], "default": "local"
}

# 2. Add SSO schemas
spec["components"]["schemas"]["SsoProviderPublic"] = {
    "type": "object",
    "required": ["protocol", "display_name", "login_url"],
    "properties": {
        "protocol": {"type": "string", "enum": ["oidc", "saml"]},
        "display_name": {"type": "string"},
        "login_url": {"type": "string"},
    },
}

spec["components"]["schemas"]["SsoProviderResponse"] = {
    "type": "object",
    "required": ["id", "protocol", "display_name", "is_active", "created_at", "updated_at"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "protocol": {"type": "string", "enum": ["oidc", "saml"]},
        "display_name": {"type": "string"},
        "issuer_url": {"type": "string", "nullable": True},
        "client_id": {"type": "string", "nullable": True},
        "client_secret_masked": {"type": "string", "default": "●●●●●●●●"},
        "scopes": {"type": "string", "default": "openid email profile groups"},
        "redirect_uri": {"type": "string", "nullable": True},
        "group_claim_name": {"type": "string", "default": "groups"},
        "saml_entity_id": {"type": "string", "nullable": True},
        "saml_metadata_url": {"type": "string", "nullable": True},
        "saml_metadata_xml_masked": {"type": "string", "default": "●●●●●●●●"},
        "saml_certificate_masked": {"type": "string", "default": "●●●●●●●●"},
        "is_active": {"type": "boolean", "default": True},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
    },
}

spec["components"]["schemas"]["SsoProviderCreate"] = {
    "type": "object",
    "required": ["protocol", "display_name"],
    "properties": {
        "protocol": {"type": "string", "enum": ["oidc", "saml"]},
        "display_name": {"type": "string", "minLength": 1, "maxLength": 200},
        "issuer_url": {"type": "string", "nullable": True},
        "client_id": {"type": "string", "nullable": True},
        "client_secret": {"type": "string", "nullable": True, "writeOnly": True},
        "scopes": {"type": "string", "default": "openid email profile groups"},
        "redirect_uri": {"type": "string", "nullable": True},
        "group_claim_name": {"type": "string", "default": "groups"},
        "saml_entity_id": {"type": "string", "nullable": True},
        "saml_metadata_url": {"type": "string", "nullable": True},
        "saml_metadata_xml": {"type": "string", "nullable": True, "writeOnly": True},
        "saml_certificate": {"type": "string", "nullable": True, "writeOnly": True},
    },
}

spec["components"]["schemas"]["SsoProviderUpdate"] = {
    "type": "object",
    "properties": {
        "display_name": {"type": "string", "minLength": 1, "maxLength": 200, "nullable": True},
        "issuer_url": {"type": "string", "nullable": True},
        "client_id": {"type": "string", "nullable": True},
        "client_secret": {"type": "string", "nullable": True, "writeOnly": True},
        "scopes": {"type": "string", "nullable": True},
        "redirect_uri": {"type": "string", "nullable": True},
        "group_claim_name": {"type": "string", "nullable": True},
        "saml_entity_id": {"type": "string", "nullable": True},
        "saml_metadata_url": {"type": "string", "nullable": True},
        "saml_metadata_xml": {"type": "string", "nullable": True, "writeOnly": True},
        "saml_certificate": {"type": "string", "nullable": True, "writeOnly": True},
        "is_active": {"type": "boolean", "nullable": True},
    },
}

# 3. Add Role schemas
spec["components"]["schemas"]["RoleResponse"] = {
    "type": "object",
    "required": ["id", "name", "priority", "permissions", "is_builtin", "created_at", "updated_at"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "name": {"type": "string"},
        "description": {"type": "string", "nullable": True},
        "priority": {"type": "integer"},
        "permissions": {"type": "array", "items": {"type": "string"}, "default": []},
        "is_builtin": {"type": "boolean", "default": False},
        "group_mappings": {"type": "array", "items": {"type": "object"}, "default": []},
        "connection_policy_count": {"type": "integer", "default": 0},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
    },
}

spec["components"]["schemas"]["RoleDetailResponse"] = {
    "allOf": [
        {"$ref": "#/components/schemas/RoleResponse"},
        {
            "type": "object",
            "properties": {
                "connection_policies": {
                    "type": "array",
                    "items": {"type": "object"},
                    "default": [],
                },
            },
        },
    ],
}

spec["components"]["schemas"]["RoleCreate"] = {
    "type": "object",
    "required": ["name", "priority"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100},
        "description": {"type": "string", "maxLength": 500, "nullable": True},
        "priority": {"type": "integer", "minimum": 0},
        "permissions": {"type": "array", "items": {"type": "string"}, "default": []},
        "group_mappings": {"type": "array", "items": {"type": "string"}, "default": []},
        "connection_policies": {"type": "array", "items": {"type": "object"}, "default": []},
    },
}

spec["components"]["schemas"]["RoleUpdate"] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100, "nullable": True},
        "description": {"type": "string", "maxLength": 500, "nullable": True},
        "priority": {"type": "integer", "minimum": 0, "nullable": True},
        "permissions": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "group_mappings": {"type": "array", "items": {"type": "string"}, "nullable": True},
        "connection_policies": {"type": "array", "items": {"type": "object"}, "nullable": True},
    },
}

# 4. Policy test schemas
spec["components"]["schemas"]["PolicyTestRequest"] = {
    "type": "object",
    "required": ["question", "connection_id"],
    "properties": {
        "question": {"type": "string", "minLength": 1, "maxLength": 2000},
        "connection_id": {"type": "string", "format": "uuid"},
    },
}

spec["components"]["schemas"]["PolicyTestResponse"] = {
    "type": "object",
    "required": ["would_be_allowed"],
    "properties": {
        "accessible_tables": {"type": "array", "items": {"type": "string"}, "default": []},
        "accessible_columns": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}, "default": {}},
        "blocked_tables": {"type": "array", "items": {"type": "string"}, "default": []},
        "applicable_row_filters": {"type": "array", "items": {"type": "object"}, "default": []},
        "masked_columns": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}, "default": {}},
        "would_be_allowed": {"type": "boolean", "default": True},
    },
}

# 5. Group mapping schemas
spec["components"]["schemas"]["GroupMappingResponse"] = {
    "type": "object",
    "required": ["id", "sso_group_value", "role_id", "role_name", "created_at"],
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "sso_group_value": {"type": "string"},
        "role_id": {"type": "string", "format": "uuid"},
        "role_name": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
    },
}

spec["components"]["schemas"]["GroupMappingCreate"] = {
    "type": "object",
    "required": ["sso_group_value", "role_id"],
    "properties": {
        "sso_group_value": {"type": "string"},
        "role_id": {"type": "string", "format": "uuid"},
    },
}

# 6. Audit schemas
spec["components"]["schemas"]["AuditVerifyResponse"] = {
    "type": "object",
    "required": ["verified", "entries_checked", "verified_at"],
    "properties": {
        "verified": {"type": "boolean"},
        "entries_checked": {"type": "integer"},
        "first_break_at": {"type": "integer", "nullable": True},
        "verified_at": {"type": "string", "format": "date-time"},
    },
}

spec["components"]["schemas"]["AuditStatusResponse"] = {
    "type": "object",
    "required": ["total_entries"],
    "properties": {
        "total_entries": {"type": "integer"},
        "last_verification": {"type": "object", "nullable": True},
    },
}

# 7. Add new error codes to ErrorResponse description (as comments in description)
existing_desc = spec["components"]["schemas"]["ErrorResponse"].get("description", "")
if "Phase 5" not in existing_desc:
    spec["components"]["schemas"]["ErrorResponse"]["description"] = (
        existing_desc + "\n\nPhase 5 error codes: forbidden, sso_no_role, sso_validation_failed, "
        "sso_provider_unavailable, sso_not_configured, local_login_admin_only, "
        "role_not_found, duplicate_group_mapping, query_blocked_policy, "
        "filter_validation_failed, policy_schema_conflict, audit_chain_broken, "
        "builtin_role_protected."
    )

# 8. Add Phase 5 tags
existing_tags = {t["name"] for t in spec.get("tags", [])}
for tag_name, tag_desc in [
    ("SSO", "SSO authentication and configuration"),
    ("Roles", "Role-based access control management"),
    ("Audit", "Tamper-evident audit log verification"),
]:
    if tag_name not in existing_tags:
        spec["tags"].append({"name": tag_name, "description": tag_desc})

# 9. Add Phase 5 endpoint stubs (documented for future implementation waves)
phase5_paths = {
    "/auth/sso/providers": {
        "get": {
            "operationId": "listSsoProviders",
            "tags": ["SSO"],
            "summary": "List configured SSO providers",
            "description": "Public endpoint returning available SSO providers for sign-in page.",
            "responses": {
                "200": {
                    "description": "List of SSO providers.",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "providers": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/SsoProviderPublic"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    "/admin/sso/providers": {
        "get": {
            "operationId": "listAdminSsoProviders",
            "tags": ["SSO"],
            "summary": "List SSO providers (admin)",
            "security": [{"sessionCookie": []}],
            "responses": {
                "200": {
                    "description": "List of SSO providers with secrets masked.",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "providers": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/SsoProviderResponse"},
                                    },
                                },
                            },
                        },
                    },
                },
                "403": {
                    "description": "Missing admin.sso.manage permission.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
        "post": {
            "operationId": "createSsoProvider",
            "tags": ["SSO"],
            "summary": "Create SSO provider",
            "security": [{"sessionCookie": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/SsoProviderCreate"},
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Provider created.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SsoProviderResponse"},
                        },
                    },
                },
                "403": {
                    "description": "Missing admin.sso.manage permission.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
                "409": {
                    "description": "Provider for this protocol already exists.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/admin/roles": {
        "get": {
            "operationId": "listRoles",
            "tags": ["Roles"],
            "summary": "List roles",
            "security": [{"sessionCookie": []}],
            "responses": {
                "200": {
                    "description": "List of roles.",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "roles": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/RoleResponse"},
                                    },
                                },
                            },
                        },
                    },
                },
                "403": {
                    "description": "Missing admin.roles.manage permission.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
        "post": {
            "operationId": "createRole",
            "tags": ["Roles"],
            "summary": "Create role",
            "security": [{"sessionCookie": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/RoleCreate"},
                    },
                },
            },
            "responses": {
                "201": {
                    "description": "Role created.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/RoleResponse"},
                        },
                    },
                },
                "403": {
                    "description": "Missing admin.roles.manage permission.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
                "409": {
                    "description": "Duplicate name, priority, or group mapping.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/admin/audit/verify": {
        "post": {
            "operationId": "verifyAuditChain",
            "tags": ["Audit"],
            "summary": "Verify audit chain integrity",
            "security": [{"sessionCookie": []}],
            "responses": {
                "200": {
                    "description": "Verification result.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AuditVerifyResponse"},
                        },
                    },
                },
                "403": {
                    "description": "Missing admin.audit.verify permission.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
    "/admin/audit/status": {
        "get": {
            "operationId": "getAuditStatus",
            "tags": ["Audit"],
            "summary": "Get audit log status",
            "security": [{"sessionCookie": []}],
            "responses": {
                "200": {
                    "description": "Audit status.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/AuditStatusResponse"},
                        },
                    },
                },
                "403": {
                    "description": "Missing admin.audit.verify permission.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                        },
                    },
                },
            },
        },
    },
}

for path, methods in phase5_paths.items():
    if path not in spec["paths"]:
        spec["paths"][path] = {}
    for method, definition in methods.items():
        spec["paths"][path][method] = definition

# Write back
with open(SPEC_PATH, "w") as f:
    yaml.dump(spec, f, sort_keys=False, allow_unicode=True, default_flow_style=False)

print(f"Updated {SPEC_PATH} with Phase 5 schemas and endpoints.")
print("New schemas:", list(spec["components"]["schemas"].keys())[-12:])
print("New paths:", list(phase5_paths.keys()))
