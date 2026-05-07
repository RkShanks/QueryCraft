"""T-154: Evaluator extensibility — custom rule registration.

Tests that the pipeline exposes an ``add_rule()`` API allowing custom
rules to be registered without modifying built-in rules (FR-011).
"""

import pytest

from app.evaluator.pipeline import EvaluatorPipeline
from app.evaluator.protocol import EvaluatorRule
from app.evaluator.result import EvaluatorResult


class SecretRule:
    """Custom rule that rejects any SQL containing the word 'secret'."""

    name = "secret_rule"

    async def evaluate(self, sql: str, schema) -> tuple[bool, str | None]:
        if "secret" in sql.lower():
            return False, "SQL contains forbidden word: secret"
        return True, None


class NoNameRule:
    """A rule missing the required 'name' attribute."""

    async def evaluate(self, sql: str, schema) -> tuple[bool, str | None]:
        return True, None


class BadSignatureRule:
    """A rule with a non-async evaluate method."""

    name = "bad_sig"

    def evaluate(self, sql: str, schema) -> tuple[bool, str | None]:
        return True, None


@pytest.mark.asyncio
async def test_add_rule_rejects_secret():
    """Custom rule registered via add_rule() rejects 'secret' SQL."""
    pipeline = EvaluatorPipeline(rules=[])
    pipeline.add_rule(SecretRule())

    result = await pipeline.run("SELECT secret FROM customer", schema=None)
    assert isinstance(result, EvaluatorResult)
    assert result.passed is False
    assert result.failed_rule == "secret_rule"
    assert "secret" in (result.reason or "").lower()


@pytest.mark.asyncio
async def test_add_rule_does_not_fire_on_clean_sql():
    """Custom rule does not fire when SQL is clean."""
    pipeline = EvaluatorPipeline(rules=[])
    pipeline.add_rule(SecretRule())

    result = await pipeline.run("SELECT * FROM customer", schema=None)
    assert result.passed is True


@pytest.mark.asyncio
async def test_add_rule_preserves_builtin_rules():
    """Adding a custom rule does not remove existing built-in rules."""

    class BuiltInRule:
        name = "builtin"

        async def evaluate(self, sql: str, schema) -> tuple[bool, str | None]:
            if "DROP" in sql.upper():
                return False, "DROP not allowed"
            return True, None

    pipeline = EvaluatorPipeline(rules=[BuiltInRule()])
    pipeline.add_rule(SecretRule())

    # Built-in rule still fires
    result = await pipeline.run("DROP TABLE customer", schema=None)
    assert result.passed is False
    assert result.failed_rule == "builtin"

    # Custom rule also fires when built-in passes
    result = await pipeline.run("SELECT secret FROM customer", schema=None)
    assert result.passed is False
    assert result.failed_rule == "secret_rule"


def test_add_rule_validates_protocol():
    """Registering a non-conforming object raises a clear error."""
    pipeline = EvaluatorPipeline(rules=[])

    with pytest.raises(TypeError):
        pipeline.add_rule("not_a_rule")

    with pytest.raises(TypeError):
        pipeline.add_rule(42)

    with pytest.raises(TypeError):
        pipeline.add_rule(NoNameRule())

    with pytest.raises(TypeError):
        pipeline.add_rule(BadSignatureRule())
