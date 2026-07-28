"""HostileInputDetector — runs all registered rules and aggregates outcome.

Outcome logic (per tasks.md T-825):
- "blocked"  if max_confidence >= block_confidence
- "flagged"  if max_confidence >= flag_confidence  (and < block)
- "allowed"  otherwise

All registered rules are always executed — no short-circuit.
"""

from __future__ import annotations

import dataclasses
from math import isfinite
from typing import TYPE_CHECKING

from app.core.exceptions import DetectionUnavailableError
from app.services.detection.normalization import normalize_detection_text
from app.services.detection.protocol import BUILTIN_RULE_NAMES, REGISTRY, DetectionResult, RuleRegistry

if TYPE_CHECKING:
    from app.db.models.detection_config import DetectionThresholdConfig


@dataclasses.dataclass
class DetectionOutcome:
    """Aggregated result from running all rules.

    Attributes:
        outcome: "blocked", "flagged", or "allowed".
        results: Individual DetectionResult from every rule.
        max_confidence: Highest confidence seen across all results.
    """

    outcome: str
    results: list[DetectionResult]
    max_confidence: float


class HostileInputDetector:
    """Runs all rules in a RuleRegistry and produces a DetectionOutcome.

    Args:
        registry: The rule registry to use. Defaults to the module-level
                  REGISTRY singleton so callers need not provide one.
    """

    def __init__(self, registry: RuleRegistry | None = None) -> None:
        self._registry = registry if registry is not None else REGISTRY
        self._requires_builtin_rules = registry is None or registry is REGISTRY

    async def detect(
        self,
        text: str,
        thresholds: DetectionThresholdConfig,
    ) -> DetectionOutcome:
        """Score ``text`` against all registered rules.

        Every rule is invoked regardless of earlier results.

        Args:
            text: The raw user input to evaluate.
            thresholds: DetectionThresholdConfig providing block/flag confidences.

        Returns:
            DetectionOutcome with aggregated outcome, all results, and max confidence.
        """
        rules = self._registry.list_rules()
        if self._requires_builtin_rules and {rule.name for rule in rules} != BUILTIN_RULE_NAMES:
            raise DetectionUnavailableError()
        if not self._thresholds_are_valid(thresholds):
            raise DetectionUnavailableError()

        detection_text = normalize_detection_text(text)
        results: list[DetectionResult] = []

        for rule in rules:
            try:
                result = rule.detect(detection_text)
            except Exception:
                raise DetectionUnavailableError() from None
            if not self._result_is_valid(result):
                raise DetectionUnavailableError()
            results.append(result)

        max_confidence = max((r.confidence for r in results), default=0.0)

        if max_confidence >= thresholds.block_confidence:
            outcome = "blocked"
        elif max_confidence >= thresholds.flag_confidence:
            outcome = "flagged"
        else:
            outcome = "allowed"

        return DetectionOutcome(
            outcome=outcome,
            results=results,
            max_confidence=max_confidence,
        )

    @staticmethod
    def _thresholds_are_valid(thresholds: DetectionThresholdConfig) -> bool:
        block = thresholds.block_confidence
        flag = thresholds.flag_confidence
        values_are_finite_numbers = all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
            for value in (block, flag)
        )
        return values_are_finite_numbers and 0.0 <= flag < block <= 1.0

    @staticmethod
    def _result_is_valid(result: DetectionResult) -> bool:
        return (
            isinstance(result, DetectionResult)
            and isinstance(result.category, str)
            and bool(result.category)
            and isinstance(result.confidence, (int, float))
            and not isinstance(result.confidence, bool)
            and isfinite(result.confidence)
            and 0.0 <= result.confidence <= 1.0
            and isinstance(result.explanation, str)
        )
