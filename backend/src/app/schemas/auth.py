"""Auth Pydantic schemas matching openapi.yaml.

Defines SignInRequest and UserProfile.
"""

from pydantic import BaseModel, Field


class SignInRequest(BaseModel):
    """POST /auth/sign-in request body."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=1)


class UserProfile(BaseModel):
    """GET /auth/me response."""

    id: str
    username: str
    display_name: str
    role: str
