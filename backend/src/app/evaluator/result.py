"""Evaluator result model."""

from pydantic import BaseModel


class EvaluatorResult(BaseModel):
    """Result returned by the evaluator pipeline.

    Attributes:
        passed: True when all rules passed.
        failed_rule: Name of the first rule that failed (None if passed).
        reason: Human-readable reason for failure (None if passed).
    """

    passed: bool
    failed_rule: str | None = None
    reason: str | None = None
