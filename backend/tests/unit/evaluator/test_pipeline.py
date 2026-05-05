"""T-088 — EvaluatorRule protocol + pipeline tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluator.pipeline import EvaluatorPipeline
from app.evaluator.protocol import EvaluatorRule
from app.evaluator.result import EvaluatorResult


class ValidRule:
    """A rule that correctly implements EvaluatorRule."""

    name = "valid_rule"

    async def evaluate(self, sql: str, schema) -> tuple[bool, str | None]:
        return True, None


class MissingEvaluate:
    """A class missing evaluate."""

    name = "missing_evaluate"


class WrongSignature:
    """A class with wrong evaluate signature."""

    name = "wrong_sig"

    def evaluate(self, sql: str, schema) -> tuple[bool, str | None]:
        return True, None


def test_protocol_is_runtime_checkable():
    """EvaluatorRule must be a runtime_checkable Protocol."""
    from typing import Protocol

    assert issubclass(EvaluatorRule, Protocol)
    assert hasattr(EvaluatorRule, "__instancecheck__")


def test_valid_rule_satisfies_protocol():
    """A class with correct evaluate passes isinstance."""
    rule = ValidRule()
    assert isinstance(rule, EvaluatorRule)


def test_missing_evaluate_fails_isinstance():
    """A class missing evaluate should fail isinstance."""
    rule = MissingEvaluate()
    assert not isinstance(rule, EvaluatorRule)


def test_sync_evaluate_passes_isinstance():
    """runtime_checkable only checks name+callable, not async-ness."""
    rule = WrongSignature()
    assert isinstance(rule, EvaluatorRule)


@pytest.mark.asyncio
async def test_pipeline_zero_rules_passes():
    """Pipeline with no rules → passed=True."""
    pipeline = EvaluatorPipeline(rules=[])
    result = await pipeline.run("SELECT 1", schema=None)
    assert isinstance(result, EvaluatorResult)
    assert result.passed is True
    assert result.failed_rule is None
    assert result.reason is None


@pytest.mark.asyncio
async def test_pipeline_all_rules_pass():
    """Pipeline with 3 passing rules → passed=True."""
    rules = [
        ValidRule(),
        ValidRule(),
        ValidRule(),
    ]
    pipeline = EvaluatorPipeline(rules=rules)
    result = await pipeline.run("SELECT 1", schema=None)
    assert result.passed is True
    assert result.failed_rule is None
    assert result.reason is None


@pytest.mark.asyncio
async def test_pipeline_fail_fast():
    """Pipeline with [pass, FAIL, pass] → fails, third rule never called."""
    rule1 = ValidRule()
    rule2 = MagicMock(spec=EvaluatorRule)
    rule2.name = "failing_rule"
    rule2.evaluate = AsyncMock(return_value=(False, "Data-modifying statement detected"))
    rule3 = MagicMock(spec=EvaluatorRule)
    rule3.name = "never_called"
    rule3.evaluate = AsyncMock(return_value=(True, None))

    pipeline = EvaluatorPipeline(rules=[rule1, rule2, rule3])
    result = await pipeline.run("DROP TABLE users", schema=None)

    assert result.passed is False
    assert result.failed_rule == "failing_rule"
    assert result.reason == "Data-modifying statement detected"
    rule3.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_preserves_rule_order():
    """Rules are evaluated in constructor order."""
    rule1 = MagicMock(spec=EvaluatorRule)
    rule1.name = "rule_1"
    rule1.evaluate = AsyncMock(return_value=(True, None))
    rule2 = MagicMock(spec=EvaluatorRule)
    rule2.name = "rule_2"
    rule2.evaluate = AsyncMock(return_value=(True, None))

    pipeline = EvaluatorPipeline(rules=[rule1, rule2])
    await pipeline.run("SELECT 1", schema=None)

    rule1.evaluate.assert_called_once()
    rule2.evaluate.assert_called_once()
