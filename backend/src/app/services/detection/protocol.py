"""Detection protocol, registry, and core data types.

Defines:
- DetectionResult: single rule output (category, confidence, explanation)
- DetectionRule: Protocol — any object with ``name: str`` and ``detect(text) -> DetectionResult``
- RuleRegistry: register rules, list them, guard duplicates
- REGISTRY: module-level singleton used by HostileInputDetector
"""

from __future__ import annotations

import dataclasses
from typing import Protocol, runtime_checkable


@dataclasses.dataclass
class DetectionResult:
    """Output of a single detection rule.

    Attributes:
        category: Rule category label (e.g. "prompt_injection").
        confidence: Float in [0.0, 1.0] indicating match strength.
        explanation: Human-readable reason (not surfaced to end users).
    """

    category: str
    confidence: float
    explanation: str


@runtime_checkable
class DetectionRule(Protocol):
    """Protocol for hostile-input detection rules.

    All rules must expose:
    - ``name``: a unique string identifier.
    - ``detect(text)``: synchronous scoring of arbitrary text.
    """

    name: str

    def detect(self, text: str) -> DetectionResult:
        """Score ``text`` and return a DetectionResult."""
        ...


class RuleRegistry:
    """Registry of DetectionRule instances, keyed by name.

    Rules are stored insertion-ordered. Duplicate names raise ValueError.
    """

    def __init__(self) -> None:
        self._rules: dict[str, DetectionRule] = {}

    def register(self, rule: DetectionRule) -> None:
        """Register a rule.

        Args:
            rule: Any object satisfying the DetectionRule protocol.

        Raises:
            ValueError: If a rule with the same name is already registered.
        """
        if rule.name in self._rules:
            raise ValueError(f"Rule '{rule.name}' already registered in this registry.")
        self._rules[rule.name] = rule

    def list_rules(self) -> list[DetectionRule]:
        """Return all registered rules in registration order."""
        return list(self._rules.values())


#: Module-level singleton registry.  Import and register rules here so that
#: HostileInputDetector picks them up via REGISTRY.list_rules().
REGISTRY = RuleRegistry()
