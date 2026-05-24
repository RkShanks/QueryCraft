"""Phase 5 SSO Group Mapping Pydantic schemas (T-629).

Request/response models for mapping SSO group claims to platform roles.
"""

from pydantic import BaseModel


class GroupMappingResponse(BaseModel):
    """SSO group-to-role mapping response."""

    id: str
    sso_group_value: str
    role_id: str
    role_name: str
    created_at: str


class GroupMappingCreate(BaseModel):
    """Create a new group mapping (admin only)."""

    sso_group_value: str
    role_id: str
