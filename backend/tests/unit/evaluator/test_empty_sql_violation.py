"""F-007: empty SQL produces distinct violation identity."""

import pytest

from app.evaluator.pipeline import Evaluator
from app.evaluator.rules.empty_sql import EmptySqlRule
from app.evaluator.rules.read_only import ReadOnlyRule
from app.evaluator.rules.single_statement import SingleStatementRule


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", ["", "   ", None])
async def test_empty_sql_violation_identity(sql):
    evaluator = Evaluator(
        rules=[
            EmptySqlRule(),
            ReadOnlyRule(),
            SingleStatementRule(),
        ]
    )
    result = await evaluator.evaluate(sql, None)
    assert not result.passed
    assert result.violations
    violation = result.violations[0]
    assert violation.rule_name == "empty_sql"
    assert violation.message_key == "evaluator.violation.emptySql"
