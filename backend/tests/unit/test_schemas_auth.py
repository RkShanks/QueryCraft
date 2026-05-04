"""Tests for auth Pydantic schema validation (T-036).

Validates SignInRequest rejects empty username, empty password, and username >64 chars;
UserProfile round-trips all required fields.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import SignInRequest, UserProfile


class TestSignInRequest:
    """Validation rules for sign-in payload."""

    def test_rejects_empty_username(self):
        with pytest.raises(ValidationError) as exc_info:
            SignInRequest(username="", password="secret")
        assert "username" in str(exc_info.value)

    def test_rejects_empty_password(self):
        with pytest.raises(ValidationError) as exc_info:
            SignInRequest(username="admin", password="")
        assert "password" in str(exc_info.value)

    def test_rejects_username_over_64_chars(self):
        with pytest.raises(ValidationError) as exc_info:
            SignInRequest(username="a" * 65, password="secret")
        assert "username" in str(exc_info.value)

    def test_accepts_valid_credentials(self):
        req = SignInRequest(username="admin", password="secret")
        assert req.username == "admin"
        assert req.password == "secret"


class TestUserProfile:
    """Round-trip and required field checks for UserProfile."""

    def test_round_trips_required_fields(self):
        profile = UserProfile(
            id="550e8400-e29b-41d4-a716-446655440000",
            username="admin",
            display_name="Administrator",
            role="admin",
        )
        assert profile.id == "550e8400-e29b-41d4-a716-446655440000"
        assert profile.username == "admin"
        assert profile.display_name == "Administrator"
        assert profile.role == "admin"

    def test_rejects_missing_id(self):
        with pytest.raises(ValidationError) as exc_info:
            UserProfile(username="admin", display_name="Admin", role="admin")
        assert "id" in str(exc_info.value)
