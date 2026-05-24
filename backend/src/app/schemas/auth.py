"""Auth Pydantic schemas matching openapi.yaml.

Defines SignInRequest and UserProfile.
"""

from pydantic import BaseModel, Field


class SignInRequest(BaseModel):
    """POST /auth/sign-in request body."""

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[\w.-]+$")
    password: str = Field(..., min_length=1)


class UserProfile(BaseModel):
    """GET /auth/me response — extended for Phase 5 SSO/RBAC."""

    id: str
    username: str
    display_name: str
    role: str  # deprecated, kept for backward compatibility
    role_id: str | None = None
    role_name: str | None = None
    permissions: list[str] = []
    auth_provider: str = "local"
