"""Hostile input detection package.

Exports:
- DetectionResult: dataclass for a single rule's output
- DetectionRule: Protocol for rule implementations
- RuleRegistry: registry class
- REGISTRY: module-level singleton registry

Importing this package also registers all built-in rules via their module-level
``REGISTRY.register()`` calls.  No further action is required by callers.
"""

from app.services.detection.protocol import REGISTRY, DetectionResult, DetectionRule, RuleRegistry

__all__ = [
    "REGISTRY",
    "DetectionResult",
    "DetectionRule",
    "RuleRegistry",
]

# --- Built-in rule registration ---
# Each module calls REGISTRY.register() at import time.  Importing them here
# ensures the singleton is populated whenever the detection package is used.
import app.services.detection.rules.destructive_sql  # noqa: E402, F401
import app.services.detection.rules.prompt_injection  # noqa: E402, F401
import app.services.detection.rules.rbac_bypass  # noqa: E402, F401
import app.services.detection.rules.schema_exposure  # noqa: E402, F401
import app.services.detection.rules.sql_injection  # noqa: E402, F401
