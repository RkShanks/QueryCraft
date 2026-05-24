"""Phase 5 Role and Policy Pydantic schemas (T-627).

Request/response models for role CRUD, connection policies,
and policy test dry-run results.
"""

from pydantic import BaseModel, Field


class ConnectionPolicyItem(BaseModel):
    """Single connection policy within a role."""

    connection_id: str
    allowed_tables: list[dict] = Field(default_factory=list)
    row_filters: list[dict] = Field(default_factory=list)
    column_masks: list[dict] = Field(default_factory=list)


class RoleResponse(BaseModel):
    """List view of a role."""

    id: str
    name: str
    description: str | None = None
    priority: int
    permissions: list[str] = Field(default_factory=list)
    is_builtin: bool = False
    group_mappings: list[dict] = Field(default_factory=list)
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
    group_mappings: list[dict] = Field(default_factory=list)
    connection_policies: list[dict] = Field(default_factory=list)
    created_at: str
    updated_at: str


class RoleCreate(BaseModel):
    """Create a new role (admin only)."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int = Field(..., ge=0)
    permissions: list[str] = Field(default_factory=list)
    group_mappings: list[str] = Field(default_factory=list)
    connection_policies: list[ConnectionPolicyItem] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """Update an existing role (admin only)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int | None = Field(None, ge=0)
    permissions: list[str] | None = None
    group_mappings: list[str] | None = None
    connection_policies: list[ConnectionPolicyItem] | None = None


class PolicyTestRequest(BaseModel):
    """Dry-run a natural language question against role policy."""

    question: str = Field(..., min_length=1, max_length=2000)
    connection_id: str


class PolicyTestResponse(BaseModel):
    """Result of a policy dry-run test."""

    accessible_tables: list[str] = Field(default_factory=list)
    accessible_columns: dict[str, list[str]] = Field(default_factory=dict)
    blocked_tables: list[str] = Field(default_factory=list)
    applicable_row_filters: list[dict] = Field(default_factory=list)
    masked_columns: dict[str, list[str]] = Field(default_factory=dict)
    would_be_allowed: bool = True
