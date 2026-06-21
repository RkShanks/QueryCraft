"""RED unit tests for DetectionRule protocol and RuleRegistry (T-822).

Contract tested:
- RuleRegistry.register() stores rules by name
- Duplicate name raises ValueError
- RuleRegistry.list_rules() returns all registered rules
- DetectionRule Protocol has required methods detect(text) -> DetectionResult
"""

import pytest


class TestDetectionResultDataclass:
    """DetectionResult is a dataclass with category, confidence, explanation."""

    def test_detection_result_has_required_fields(self):
        from app.services.detection.protocol import DetectionResult

        result = DetectionResult(
            category="test_category",
            confidence=0.9,
            explanation="Test explanation",
        )
        assert result.category == "test_category"
        assert result.confidence == 0.9
        assert result.explanation == "Test explanation"

    def test_detection_result_is_dataclass(self):
        import dataclasses

        from app.services.detection.protocol import DetectionResult

        assert dataclasses.is_dataclass(DetectionResult)


class TestDetectionRuleProtocol:
    """DetectionRule protocol has name property and detect() method."""

    def test_detection_rule_protocol_is_importable(self):
        from app.services.detection.protocol import DetectionRule  # noqa: F401

    def test_rule_implementing_protocol_must_have_name_property(self):
        from app.services.detection.protocol import DetectionResult, DetectionRule

        class _ConcreteRule:
            """A minimal rule implementing the protocol."""

            name = "test_rule"

            def detect(self, text: str) -> DetectionResult:
                return DetectionResult(category="test", confidence=0.0, explanation="ok")

        rule = _ConcreteRule()
        # Protocol check: name is a str, detect returns DetectionResult
        assert isinstance(rule.name, str)
        result = rule.detect("some text")
        assert isinstance(result, DetectionResult)

    def test_rule_detect_returns_detection_result(self):
        from app.services.detection.protocol import DetectionResult, DetectionRule

        class _LowConfRule:
            name = "low_conf"

            def detect(self, text: str) -> DetectionResult:
                return DetectionResult(category="low", confidence=0.1, explanation="low")

        rule = _LowConfRule()
        result = rule.detect("hello world")
        assert isinstance(result, DetectionResult)
        assert result.confidence == 0.1


class TestRuleRegistry:
    """RuleRegistry registers, retrieves, and guards against duplicates."""

    @pytest.fixture(autouse=True)
    def fresh_registry(self):
        """Create a fresh RuleRegistry for each test (avoid singleton bleed)."""
        from app.services.detection.protocol import RuleRegistry

        self.registry = RuleRegistry()

    def _make_rule(self, name: str, confidence: float = 0.0):
        from app.services.detection.protocol import DetectionResult

        class _Rule:
            def detect(self, text: str) -> DetectionResult:
                return DetectionResult(category=name, confidence=confidence, explanation="")

        _Rule.name = name
        return _Rule()

    def test_register_stores_rule_by_name(self):
        rule = self._make_rule("injection")
        self.registry.register(rule)
        rules = self.registry.list_rules()
        assert any(r.name == "injection" for r in rules)

    def test_duplicate_name_raises_value_error(self):
        rule1 = self._make_rule("dupe")
        rule2 = self._make_rule("dupe")
        self.registry.register(rule1)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(rule2)

    def test_list_rules_returns_all_registered(self):
        rule_a = self._make_rule("rule_a")
        rule_b = self._make_rule("rule_b")
        self.registry.register(rule_a)
        self.registry.register(rule_b)
        names = {r.name for r in self.registry.list_rules()}
        assert names == {"rule_a", "rule_b"}

    def test_list_rules_empty_when_no_rules_registered(self):
        assert self.registry.list_rules() == []

    def test_register_multiple_distinct_rules(self):
        for i in range(5):
            self.registry.register(self._make_rule(f"rule_{i}"))
        assert len(self.registry.list_rules()) == 5


class TestRegistrySingleton:
    """REGISTRY singleton is importable and is a RuleRegistry instance."""

    def test_registry_singleton_importable(self):
        from app.services.detection.protocol import REGISTRY, RuleRegistry

        assert isinstance(REGISTRY, RuleRegistry)

    def test_registry_singleton_is_same_object(self):
        from app.services.detection import protocol as p1
        from app.services.detection import protocol as p2

        assert p1.REGISTRY is p2.REGISTRY
