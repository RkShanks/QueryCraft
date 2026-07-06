"""Tests for query Pydantic schema validation (T-038).

Validates SubmitQuestionRequest rejects empty/whitespace/over-2000-char questions;
QueryResult enforces kind="result" discriminator and required fields;
EvaluatorRejection and RefinePrompt round-trip correctly.
"""

import pytest
from pydantic import ValidationError

from app.schemas.query import (
    AcceptQueryRequest,
    ColumnMeta,
    EvaluatorRejection,
    QueryResult,
    RefinePrompt,
    RegenerateQueryRequest,
    RejectQueryRequest,
    SubmitQuestionRequest,
    Violation,
)


class TestSubmitQuestionRequest:
    """Validation rules for question submission."""

    def test_rejects_empty_question(self):
        with pytest.raises(ValidationError) as exc_info:
            SubmitQuestionRequest(question="")
        assert "question" in str(exc_info.value)

    def test_rejects_whitespace_question(self):
        with pytest.raises(ValidationError) as exc_info:
            SubmitQuestionRequest(question="   ")
        assert "question" in str(exc_info.value)

    def test_rejects_over_2000_chars(self):
        with pytest.raises(ValidationError) as exc_info:
            SubmitQuestionRequest(question="x" * 2001)
        assert "question" in str(exc_info.value)

    def test_accepts_valid_question(self):
        conn_id = "550e8400-e29b-41d4-a716-446655440001"
        req = SubmitQuestionRequest(question="Show me sales by region", connection_id=conn_id)
        assert req.question == "Show me sales by region"


class TestQueryResult:
    """Discriminator and required field checks."""

    def test_enforces_kind_result(self):
        result = QueryResult(
            kind="result",
            attempt_id="550e8400-e29b-41d4-a716-446655440000",
            question="Show me sales",
            generated_sql="SELECT 1",
            columns=[ColumnMeta(name="id", type="integer")],
            rows=[[1]],
            row_count=1,
            attempt_number=1,
            is_last_auto_retry=False,
        )
        assert result.kind == "result"

    def test_rejects_invalid_kind(self):
        with pytest.raises(ValidationError) as exc_info:
            QueryResult(
                kind="invalid",
                attempt_id="550e8400-e29b-41d4-a716-446655440000",
                question="Show me sales",
                generated_sql="SELECT 1",
                columns=[ColumnMeta(name="id", type="integer")],
                rows=[[1]],
                row_count=1,
                attempt_number=1,
                is_last_auto_retry=False,
            )
        assert "kind" in str(exc_info.value)


class TestEvaluatorRejection:
    """Round-trip for evaluator rejection schema."""

    def test_round_trip(self):
        rejection = EvaluatorRejection(
            message_key="query.evaluator.rejected",
            violations=[Violation(rule="read_only_check", message_key="evaluator.violation.dataModifying")],
        )
        assert rejection.message_key == "query.evaluator.rejected"
        assert len(rejection.violations) == 1


class TestRefinePrompt:
    """Round-trip for refine prompt schema."""

    def test_round_trip(self):
        prompt = RefinePrompt(
            kind="refine",
            message_key="query.refine.message",
            should_refine=True,
        )
        assert prompt.kind == "refine"
        assert prompt.should_refine is True


class TestAcceptQueryRequest:
    """Validation for accept payload."""

    def test_requires_attempt_id(self):
        with pytest.raises(ValidationError) as exc_info:
            AcceptQueryRequest(attempt_id="")
        assert "attempt_id" in str(exc_info.value)

    def test_accepts_valid_attempt_id(self):
        req = AcceptQueryRequest(attempt_id="550e8400-e29b-41d4-a716-446655440000")
        assert req.attempt_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_rejects_control_character_attempt_id(self):
        with pytest.raises(ValidationError) as exc_info:
            AcceptQueryRequest(attempt_id="\x00")
        assert "attempt_id" in str(exc_info.value)


class TestRejectQueryRequest:
    """Validation for reject payload."""

    def test_requires_attempt_id(self):
        with pytest.raises(ValidationError) as exc_info:
            RejectQueryRequest(attempt_id="")
        assert "attempt_id" in str(exc_info.value)

    def test_rejects_control_character_attempt_id(self):
        with pytest.raises(ValidationError) as exc_info:
            RejectQueryRequest(attempt_id="\x00")
        assert "attempt_id" in str(exc_info.value)


class TestRegenerateQueryRequest:
    """Validation for regenerate payload."""

    def test_rejects_control_character_attempt_id(self):
        with pytest.raises(ValidationError) as exc_info:
            RegenerateQueryRequest(attempt_id="\x00")
        assert "attempt_id" in str(exc_info.value)
