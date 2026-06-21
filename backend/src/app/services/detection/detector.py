"""HostileInputDetector — runs all registered rules and aggregates outcome.

Outcome logic (per tasks.md T-825):
- "blocked"  if max_confidence >= block_confidence
- "flagged"  if max_confidence >= flag_confidence  (and < block)
- "allowed"  otherwise

All registered rules are always executed — no short-circuit.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from app.services.detection.protocol import REGISTRY, DetectionResult, RuleRegistry

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
        results: list[DetectionResult] = []

        for rule in rules:
            result = rule.detect(text)
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
