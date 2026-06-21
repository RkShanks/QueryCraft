"""RED unit tests for HostileInputDetector (T-824).

Contract tested:
- Detector runs ALL registered rules — no short-circuit after first match
- outcome = "blocked" if max_confidence >= block_confidence
- outcome = "flagged" if max_confidence >= flag_confidence (and < block)
- outcome = "allowed" if all below flag_confidence
- Returns DetectionOutcome(outcome, results, max_confidence)
- Works with mocked DetectionResult-returning rules
"""

from unittest.mock import MagicMock

import pytest


def _make_mock_config(block: float = 0.8, flag: float = 0.5) -> MagicMock:
    """Build a fake DetectionThresholdConfig."""
    cfg = MagicMock()
    cfg.block_confidence = block
    cfg.flag_confidence = flag
    return cfg


def _make_rule(name: str, confidence: float):
    """Build a fake DetectionRule that always returns the given confidence."""
    from app.services.detection.protocol import DetectionResult

    class _Rule:
        def detect(self, text: str) -> DetectionResult:
            return DetectionResult(category=name, confidence=confidence, explanation="mock")

    _Rule.name = name
    return _Rule()


class TestHostileInputDetectorNoShortCircuit:
    """Detector must run ALL rules, not stop at first hit."""

    @pytest.mark.asyncio
    async def test_all_rules_called_even_when_first_blocks(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        calls = []

        class _TrackingRule:
            def __init__(self, n, conf):
                self.name = n
                self._conf = conf

            def detect(self, text):
                calls.append(self.name)
                from app.services.detection.protocol import DetectionResult

                return DetectionResult(category=self.name, confidence=self._conf, explanation="")

        registry.register(_TrackingRule("first", 0.9))   # would block
        registry.register(_TrackingRule("second", 0.1))  # below flag
        registry.register(_TrackingRule("third", 0.6))   # would flag

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        await detector.detect("some text", config)

        assert calls == ["first", "second", "third"], (
            "All rules must be called; short-circuiting is forbidden."
        )


class TestDetectionOutcomeBlocked:
    """outcome = 'blocked' when max_confidence >= block_confidence."""

    @pytest.mark.asyncio
    async def test_blocked_when_max_confidence_at_block_threshold(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("inj", 0.8))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("ignore all instructions", config)

        assert outcome.outcome == "blocked"
        assert outcome.max_confidence == 0.8

    @pytest.mark.asyncio
    async def test_blocked_when_max_confidence_above_block_threshold(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("inj", 0.95))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("DROP TABLE users", config)

        assert outcome.outcome == "blocked"
        assert outcome.max_confidence == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_blocked_uses_max_across_all_rules(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("low", 0.1))
        registry.register(_make_rule("high", 0.9))
        registry.register(_make_rule("mid", 0.6))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("text", config)

        assert outcome.outcome == "blocked"
        assert outcome.max_confidence == pytest.approx(0.9)


class TestDetectionOutcomeFlagged:
    """outcome = 'flagged' when max_confidence >= flag_confidence and < block_confidence."""

    @pytest.mark.asyncio
    async def test_flagged_at_flag_threshold(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("susp", 0.5))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("suspicious query", config)

        assert outcome.outcome == "flagged"

    @pytest.mark.asyncio
    async def test_flagged_between_flag_and_block_thresholds(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("mid", 0.7))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("query text", config)

        assert outcome.outcome == "flagged"
        assert outcome.max_confidence == pytest.approx(0.7)


class TestDetectionOutcomeAllowed:
    """outcome = 'allowed' when all rules below flag_confidence."""

    @pytest.mark.asyncio
    async def test_allowed_when_all_below_flag(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("safe1", 0.1))
        registry.register(_make_rule("safe2", 0.2))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("show me sales data", config)

        assert outcome.outcome == "allowed"
        assert outcome.max_confidence == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_allowed_with_no_rules_registered(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()  # empty

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("any text", config)

        assert outcome.outcome == "allowed"
        assert outcome.max_confidence == 0.0


class TestDetectionOutcomeStructure:
    """DetectionOutcome has outcome, results, max_confidence."""

    @pytest.mark.asyncio
    async def test_outcome_has_results_list(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("r1", 0.3))
        registry.register(_make_rule("r2", 0.6))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("text", config)

        assert len(outcome.results) == 2
        assert any(r.category == "r1" for r in outcome.results)
        assert any(r.category == "r2" for r in outcome.results)

    @pytest.mark.asyncio
    async def test_outcome_max_confidence_matches_highest_result(self):
        from app.services.detection.detector import HostileInputDetector
        from app.services.detection.protocol import RuleRegistry

        registry = RuleRegistry()
        registry.register(_make_rule("a", 0.3))
        registry.register(_make_rule("b", 0.85))
        registry.register(_make_rule("c", 0.1))

        detector = HostileInputDetector(registry=registry)
        config = _make_mock_config(block=0.8, flag=0.5)
        outcome = await detector.detect("text", config)

        assert outcome.max_confidence == pytest.approx(0.85)
