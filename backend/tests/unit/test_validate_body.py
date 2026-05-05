"""Unit tests for validate_body dependency (T-058b).

Tests that validate_body returns a FastAPI dependency which:
- Returns the model instance on valid input
- Raises HTTPException(400) with the contract error envelope on failure
"""

import pytest
from fastapi import HTTPException

from app.api.dependencies.validation import validate_body
from app.schemas.query import SubmitQuestionRequest


class TestValidateBody:
    """validate_body dependency tests."""

    @pytest.mark.asyncio
    async def test_valid_body_returns_model(self):
        """Valid payload should return the parsed model."""
        dep = validate_body(SubmitQuestionRequest)
        result = await dep({"question": "What is revenue?"})
        assert isinstance(result, SubmitQuestionRequest)
        assert result.question == "What is revenue?"

    @pytest.mark.asyncio
    async def test_missing_field_raises_400_with_envelope(self):
        """Missing required field should raise HTTPException(400)."""
        dep = validate_body(SubmitQuestionRequest)
        with pytest.raises(HTTPException) as exc_info:
            await dep({})
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "validation"
        assert exc_info.value.detail["message_key"] == "error.validation.generic"
        assert "details" in exc_info.value.detail
        assert len(exc_info.value.detail["details"]) >= 1
        assert exc_info.value.detail["details"][0]["field"] == "question"

    @pytest.mark.asyncio
    async def test_pattern_violation_raises_400_with_envelope(self):
        """Pattern violation should raise HTTPException(400)."""
        from app.schemas.auth import SignInRequest

        dep = validate_body(SignInRequest)
        with pytest.raises(HTTPException) as exc_info:
            await dep({"username": "00:", "password": "x"})
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "validation"
        assert "details" in exc_info.value.detail
        assert any("username" in d["field"] for d in exc_info.value.detail["details"])
