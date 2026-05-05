"""Query Pydantic schemas matching openapi.yaml.

Defines SubmitQuestionRequest, QueryResult, ColumnMeta, EvaluatorRejection,
Violation, AcceptQueryRequest, RejectQueryRequest, RefinePrompt, AcceptedQuerySummary.
"""

from pydantic import BaseModel, Field, field_validator


class SubmitQuestionRequest(BaseModel):
    """POST /query/submit request body."""

    question: str = Field(..., min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def strip_and_check(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Question cannot be empty or whitespace")
        return stripped


class ColumnMeta(BaseModel):
    """Column metadata in QueryResult."""

    name: str
    type: str


class QueryResult(BaseModel):
    """Successful query execution response."""

    kind: str = Field(default="result", pattern="^result$")
    attempt_id: str
    question: str
    generated_sql: str
    columns: list[ColumnMeta]
    rows: list[list]
    row_count: int
    attempt_number: int
    is_last_auto_retry: bool


class Violation(BaseModel):
    """Single evaluator rule failure."""

    rule: str
    message_key: str
    message_params: dict | None = None


class EvaluatorRejection(BaseModel):
    """Evaluator rejection response (HTTP 422)."""

    message_key: str
    message_params: dict | None = None
    violations: list[Violation]


class AcceptQueryRequest(BaseModel):
    """POST /query/accept request body."""

    attempt_id: str = Field(..., min_length=1)


class RejectQueryRequest(BaseModel):
    """POST /query/reject request body."""

    attempt_id: str = Field(..., min_length=1)


class RegenerateQueryRequest(BaseModel):
    """POST /query/regenerate request body."""

    attempt_id: str = Field(..., min_length=1)


class RefinePrompt(BaseModel):
    """Max-retries-reached response (kind=refine)."""

    kind: str = Field(default="refine", pattern="^refine$")
    message_key: str
    message_params: dict | None = None
    should_refine: bool


class AcceptedQuerySummary(BaseModel):
    """Summary of an accepted query (used in history list and accept response)."""

    id: str
    question_text: str
    generated_sql: str
    accepted_at: str
