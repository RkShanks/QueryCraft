"""Evaluator base types."""

from dataclasses import dataclass, field


@dataclass
class EvaluatorViolation:
    """Single rule failure."""

    rule_name: str
    message_key: str
    message_params: dict | None = None


@dataclass
class EvaluatorResult:
    """Result of evaluating SQL."""

    passed: bool
    violations: list[EvaluatorViolation] = field(default_factory=list)
