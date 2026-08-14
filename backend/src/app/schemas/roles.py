"""Phase 5 Role and Policy Pydantic schemas (T-627).

Request/response models for role CRUD, connection policies,
and policy test dry-run results.
"""

from pydantic import BaseModel, Field, field_validator

MAX_DB_INTEGER = 2_147_483_647


def _reject_control_chars(value: str) -> str:
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("must not contain control characters")
    return value


def _validate_group_mapping_values(values: list[str]) -> list[str]:
    validated = [_reject_control_chars(group_value) for group_value in values]
    if len(set(validated)) != len(validated):
        raise ValueError("duplicate group mappings are not allowed")
    return validated


class ConnectionPolicyItem(BaseModel):
    """Single connection policy within a role."""

    connection_id: str
    allowed_tables: list[dict] = Field(default_factory=list)
    row_filters: list[dict] = Field(default_factory=list)
    column_masks: list[dict] = Field(default_factory=list)

    @field_validator("connection_id")
    @classmethod
    def _validate_text_fields(cls, value: str) -> str:
        return _reject_control_chars(value)


class RoleGroupMappingSummary(BaseModel):
    """Group mapping embedded in a role response."""

    id: str
    sso_group_value: str


class TableColumnPolicy(BaseModel):
    """Allowed-table or column-mask entry in a persisted policy."""

    table: str
    columns: list[str]


class RowFilterPolicy(BaseModel):
    """Row-filter entry in a persisted policy."""

    table: str
    filter: str


class ConnectionPolicyResponse(BaseModel):
    """Persisted connection policy embedded in role detail."""

    id: str
    connection_id: str
    allowed_tables: list[TableColumnPolicy] = Field(default_factory=list)
    row_filters: list[RowFilterPolicy] = Field(default_factory=list)
    column_masks: list[TableColumnPolicy] = Field(default_factory=list)


class RoleResponse(BaseModel):
    """List view of a role."""

    id: str
    name: str
    description: str | None = None
    priority: int
    permissions: list[str] = Field(default_factory=list)
    is_builtin: bool = False
    group_mappings: list[RoleGroupMappingSummary] = Field(default_factory=list)
    connection_policy_count: int = 0
    created_at: str
    updated_at: str


class RoleDetailResponse(BaseModel):
    """Full role detail including connection policies."""

    id: str
    name: str
    description: str | None = None
    priority: int
    permissions: list[str] = Field(default_factory=list)
    is_builtin: bool = False
    group_mappings: list[RoleGroupMappingSummary] = Field(default_factory=list)
    connection_policies: list[ConnectionPolicyResponse] = Field(default_factory=list)
    created_at: str
    updated_at: str


class RoleListResponse(BaseModel):
    """Configured platform roles."""

    roles: list[RoleResponse]


class RoleCreate(BaseModel):
    """Create a new role (admin only)."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int = Field(..., ge=0, le=MAX_DB_INTEGER)
    permissions: list[str] = Field(default_factory=list)
    group_mappings: list[str] = Field(default_factory=list)
    connection_policies: list[ConnectionPolicyItem] = Field(default_factory=list)

    @field_validator("name", "description")
    @classmethod
    def _validate_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _reject_control_chars(value)

    @field_validator("group_mappings")
    @classmethod
    def _validate_group_mappings(cls, value: list[str]) -> list[str]:
        return _validate_group_mapping_values(value)


class RoleUpdate(BaseModel):
    """Update an existing role (admin only)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int | None = Field(None, ge=0, le=MAX_DB_INTEGER)
    permissions: list[str] | None = None
    group_mappings: list[str] | None = None
    connection_policies: list[ConnectionPolicyItem] | None = None

    @field_validator("name", "description")
    @classmethod
    def _validate_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _reject_control_chars(value)

    @field_validator("group_mappings")
    @classmethod
    def _validate_group_mappings(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _validate_group_mapping_values(value)


class PolicyTestRequest(BaseModel):
    """Dry-run a natural language question against role policy."""

    question: str = Field(..., min_length=1, max_length=2000)
    connection_id: str
    sample_sql: str | None = Field(
        default=None,
        max_length=20000,
        description=(
            "Optional sample SQL the admin wants to dry-run through the role "
            "auth rule. When present and non-empty, the endpoint runs "
            "RoleAuthorizationRule against the current schema + policy and "
            "overrides would_be_allowed with the SQL-level verdict. When "
            "absent, the endpoint falls back to the policy-state preview "
            "(would_be_allowed = bool(accessible_tables))."
        ),
    )


class DraftConnectionPolicy(BaseModel):
    """Complete unsaved connection policy used by the preview endpoint."""

    connection_id: str
    allowed_tables: list[TableColumnPolicy]
    row_filters: list[RowFilterPolicy]
    column_masks: list[TableColumnPolicy]

    @field_validator("connection_id")
    @classmethod
    def _validate_connection_id(cls, value: str) -> str:
        return _reject_control_chars(value)


class DraftPolicyTestRequest(BaseModel):
    """Dry-run one complete unsaved connection policy."""

    question: str = Field(..., min_length=1, max_length=2000)
    sample_sql: str | None = Field(default=None, max_length=20000)
    connection_policy: DraftConnectionPolicy


class PolicyTestResponse(BaseModel):
    """Result of a policy dry-run test."""

    accessible_tables: list[str] = Field(default_factory=list)
    accessible_columns: dict[str, list[str]] = Field(default_factory=dict)
    blocked_tables: list[str] = Field(default_factory=list)
    applicable_row_filters: list[dict] = Field(default_factory=list)
    masked_columns: dict[str, list[str]] = Field(default_factory=dict)
    would_be_allowed: bool = True
    message_key: str | None = Field(
        default=None,
        description=(
            "Set to 'error.queryBlockedPolicy' when sample_sql evaluation "
            "blocks the query. Null when sample_sql is absent or the rule "
            "allows the query."
        ),
    )
