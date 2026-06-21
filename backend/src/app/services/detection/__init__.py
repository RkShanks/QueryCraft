"""Hostile input detection package.

Exports:
- DetectionResult: dataclass for a single rule's output
- DetectionRule: Protocol for rule implementations
- RuleRegistry: registry class
- REGISTRY: module-level singleton registry
"""

from app.services.detection.protocol import REGISTRY, DetectionResult, DetectionRule, RuleRegistry

__all__ = [
    "REGISTRY",
    "DetectionResult",
    "DetectionRule",
    "RuleRegistry",
]
