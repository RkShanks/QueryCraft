"""Tests that all built-in rule modules are registered when importing the detection package.

Blocking finding: rule modules self-register on import, but importing
``app.services.detection`` alone left REGISTRY empty in a fresh process.
Fix verified here: importing the package must populate REGISTRY with all 5 built-in rules.
"""

from __future__ import annotations

EXPECTED_RULE_NAMES = {
    "prompt_injection",
    "sql_injection",
    "rbac_bypass",
    "schema_exposure",
    "destructive_sql",
}


class TestPackageRegistration:
    """Importing app.services.detection populates REGISTRY with all built-in rules."""

    def test_all_five_rules_registered_after_package_import(self):
        """Package import alone must register all 5 built-in rules."""
        # Fresh import of the top-level detection package — no manual rule imports.
        import app.services.detection  # noqa: F401
        from app.services.detection.protocol import REGISTRY

        registered_names = {r.name for r in REGISTRY.list_rules()}
        missing = EXPECTED_RULE_NAMES - registered_names
        assert not missing, f"Built-in rules not registered after package import: {sorted(missing)}"

    def test_registry_contains_exactly_five_builtin_rules(self):
        """All 5 expected rule names present (extra rules are ok, missing are not)."""
        import app.services.detection  # noqa: F401
        from app.services.detection.protocol import REGISTRY

        registered_names = {r.name for r in REGISTRY.list_rules()}
        for name in EXPECTED_RULE_NAMES:
            assert name in registered_names, f"Missing built-in rule: {name!r}"

    def test_registry_not_empty_after_package_import(self):
        """Sanity: REGISTRY must have at least one rule after package import."""
        import app.services.detection  # noqa: F401
        from app.services.detection.protocol import REGISTRY

        assert REGISTRY.list_rules(), "REGISTRY is empty after importing app.services.detection"
