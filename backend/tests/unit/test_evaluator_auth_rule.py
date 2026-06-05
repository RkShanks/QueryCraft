"""Tests for T-708: evaluator authorization rule.

Covers FR-130 / S-007 / SC-050. ``RoleAuthorizationRule`` runs inside the
evaluator pipeline BEFORE execution. It checks every table/column reference
in the SQL AST against the role's ``allowed_tables`` policy and blocks the
query with the constant ``"query_blocked_policy"`` reason if any reference
is outside the allowed set.

Config shapes (mirrors ``role_connection_policies``):
  allowed_tables: [{"table": "t", "columns": ["c1", "c2"]}]
  column_masks:   [{"table": "t", "columns": ["c1"]}]

Behaviour:
- Column must be in the role's ``allowed_columns`` to be referenced ANYWHERE
  (SELECT / WHERE / JOIN / ORDER BY / GROUP BY / HAVING). ``column_masks`` is
  an OUTPUT transform applied by ``apply_column_masks`` after execution; the
  auth rule treats masked columns the same as non-masked (no extra access
  granted, no access denied beyond what the policy already says).
- Disallowed table -> block.
- Disallowed column (qualified or unqualified) -> block.
- Unqualified column that appears in MORE than one allowed table referenced
  by the same query -> block (cannot safely resolve). If exactly one allowed
  table in the query owns the column -> allow.
- Case-insensitive identifier matching (postgres lower-folds, MSSQL
  case-insensitive, MySQL collation-dependent).
- Qualified columns: alias -> actual table via standard ``exp.Table`` walk.
- Malformed SQL or multi-statement input -> block with sanitized constant
  reason (defense in depth; upstream rules usually catch this).
- Inputs (schema, allowed_tables, column_masks) are never mutated.
- Reason text never contains the raw SQL, table name, column name, schema
  internals, user values, or any other leak. The pipeline maps
  ``"role_authorization"`` -> ``"error.queryBlockedPolicy"`` for i18n.
"""

from __future__ import annotations

import pytest

from app.evaluator.pipeline import Evaluator, EvaluatorPipeline
from app.evaluator.rules.read_only import ReadOnlyRule
from app.evaluator.rules.role_authorization import RoleAuthorizationRule
from app.evaluator.rules.schema_validation import SchemaValidationRule
from app.evaluator.rules.single_statement import SingleStatementRule
from app.evaluator.schema_context import Column, SchemaContext, Table


# Three-table schema reused across tests. The role policy varies per test
# so we re-build the SchemaContext inside each test for clarity.
def _schema() -> SchemaContext:
    return SchemaContext(
        tables=[
            Table(
                name="orders",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="customer_id", type="integer"),
                    Column(name="ssn", type="text"),
                ],
            ),
            Table(
                name="customers",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="name", type="text"),
                ],
            ),
            Table(
                name="payments",
                columns=[
                    Column(name="id", type="integer"),
                    Column(name="order_id", type="integer"),
                ],
            ),
        ]
    )


# Two common policies reused across tests.
_POLICY_ORDERS = [{"table": "orders", "columns": ["id", "customer_id", "ssn"]}]
_POLICY_ORDERS_CUSTOMERS = [
    {"table": "orders", "columns": ["id", "customer_id"]},
    {"table": "customers", "columns": ["id", "name"]},
]
_MASKS_ORDERS_SSN = [{"table": "orders", "columns": ["ssn"]}]


# ────────────────────── Allows allowed table/columns ──────────────────────


class TestAllowsAllowedReferences:
    @pytest.mark.asyncio
    async def test_allows_fully_qualified_allowed_columns(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT orders.id, orders.customer_id FROM orders",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_allows_unqualified_columns_in_single_table_query(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT id, customer_id FROM orders",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_allows_where_clause_with_allowed_columns(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT id FROM orders WHERE customer_id = 7",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_allows_join_across_allowed_tables(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS_CUSTOMERS)
        result = await rule.evaluate(
            "SELECT orders.id FROM orders JOIN customers ON orders.customer_id = customers.id",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_allows_with_empty_allowed_tables(self) -> None:
        """An empty allow-list (deny-all) blocks all queries.

        Per S-007 / FR-130 a role with no policy entries can run nothing.
        Implemented as fail-closed: every table/column is 'disallowed'.
        """
        rule = RoleAuthorizationRule(allowed_tables=[])
        result = await rule.evaluate(
            "SELECT id FROM orders",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_allows_with_none_allowed_tables(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=None)
        result = await rule.evaluate(
            "SELECT id FROM orders",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"


# ────────────────────── Blocks disallowed references ──────────────────────


class TestBlocksDisallowedReferences:
    @pytest.mark.asyncio
    async def test_blocks_disallowed_table(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT id FROM payments",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_blocks_disallowed_column_in_select(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=[{"table": "orders", "columns": ["id"]}])
        result = await rule.evaluate(
            "SELECT ssn FROM orders",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_blocks_disallowed_column_in_where(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=[{"table": "orders", "columns": ["id"]}])
        result = await rule.evaluate(
            "SELECT id FROM orders WHERE ssn = 'x'",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_blocks_disallowed_column_via_join(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id"]},
            ]
        )
        result = await rule.evaluate(
            "SELECT orders.id FROM orders JOIN customers ON orders.customer_id = customers.id",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_blocks_unqualified_ambiguous_column(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS_CUSTOMERS)
        # 'id' exists in BOTH orders and customers; without a qualifier
        # the rule cannot safely resolve the reference.
        result = await rule.evaluate(
            "SELECT id FROM orders, customers",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_blocks_column_not_in_schema(self) -> None:
        """A column that does not exist in the schema is blocked.

        In normal operation the schema_validation rule runs first and
        catches this. The auth rule is defense in depth: if the pipeline
        is configured with role_authorization only, the same fail-closed
        behaviour applies.
        """
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT ghost_column FROM orders",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"


# ────────────────────── Masked column interaction ──────────────────────


class TestMaskedColumnInteraction:
    @pytest.mark.asyncio
    async def test_allows_masked_column_in_where_when_role_allowed(self) -> None:
        """S-007: masked column may be referenced in WHERE if otherwise allowed."""
        rule = RoleAuthorizationRule(
            allowed_tables=_POLICY_ORDERS,
            column_masks=_MASKS_ORDERS_SSN,
        )
        result = await rule.evaluate(
            "SELECT id FROM orders WHERE ssn = '111-22-3333'",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_allows_masked_column_in_select_when_role_allowed(self) -> None:
        """The auth rule does not deny SELECT of a masked column.

        The masking service (``apply_column_masks``) handles the actual
        value replacement downstream. The auth rule's job is table/column
        permission, not output transform.
        """
        rule = RoleAuthorizationRule(
            allowed_tables=_POLICY_ORDERS,
            column_masks=_MASKS_ORDERS_SSN,
        )
        result = await rule.evaluate(
            "SELECT id, ssn FROM orders",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_blocks_masked_column_when_not_role_allowed(self) -> None:
        """Masking does not grant access: a masked column not in
        ``allowed_columns`` is still blocked (fail-closed)."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
            column_masks=_MASKS_ORDERS_SSN,
        )
        result = await rule.evaluate(
            "SELECT id, ssn FROM orders",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_blocked_table_even_with_masked_column(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=_POLICY_ORDERS,
            column_masks=[{"table": "payments", "columns": ["id"]}],
        )
        result = await rule.evaluate(
            "SELECT id FROM payments",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"


# ────────────────────── Aliases and qualified columns ──────────────────────


class TestAliasesAndQualifiers:
    @pytest.mark.asyncio
    async def test_qualified_column_with_alias(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT o.id, o.customer_id FROM orders o",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_qualified_column_with_alias_blocks_disallowed(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=[{"table": "orders", "columns": ["id"]}])
        result = await rule.evaluate(
            "SELECT o.id FROM orders o",
            _schema(),
        )
        assert result == (True, None)
        result2 = await rule.evaluate(
            "SELECT o.ssn FROM orders o",
            _schema(),
        )
        assert result2[0] is False
        assert result2[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_unqualified_column_resolved_against_aliased_from(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT id, ssn FROM orders o",
            _schema(),
        )
        assert result == (True, None)


# ────────────────────── Case-insensitive matching ──────────────────────


class TestCaseInsensitiveMatching:
    @pytest.mark.asyncio
    async def test_table_name_case_insensitive(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "ORDERS", "columns": ["id"]}],
        )
        result = await rule.evaluate(
            "SELECT id FROM orders",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_column_name_case_insensitive(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["ID", "Customer_ID"]}],
        )
        result = await rule.evaluate(
            "SELECT id, customer_id FROM orders",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_qualified_column_case_insensitive(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["ID"]}],
        )
        result = await rule.evaluate(
            "SELECT Orders.ID FROM Orders",
            _schema(),
        )
        assert result == (True, None)


# ────────────────────── Malformed / multi-statement / fail-closed ──────────────────────


class TestMalformedAndMultiStatement:
    @pytest.mark.asyncio
    async def test_malformed_sql_blocked_with_sanitized_reason(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT FROM WHERE 1 1 1 garbage",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_multi_statement_blocked_with_sanitized_reason(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "SELECT id FROM orders; SELECT id FROM customers",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_non_select_blocked_with_sanitized_reason(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate(
            "DELETE FROM orders",
            _schema(),
        )
        assert result[0] is False
        assert result[1] == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_empty_sql_blocked_with_sanitized_reason(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        result = await rule.evaluate("", _schema())
        assert result[0] is False
        assert result[1] == "query_blocked_policy"


# ────────────────────── Immutability ──────────────────────


class TestImmutability:
    @pytest.mark.asyncio
    async def test_does_not_mutate_schema(self) -> None:
        schema = _schema()
        original_tables = [t.name for t in schema.tables]
        original_cols = {t.name: [c.name for c in t.columns] for t in schema.tables}
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        await rule.evaluate("SELECT ssn FROM orders", schema)
        assert [t.name for t in schema.tables] == original_tables
        assert {t.name: [c.name for c in t.columns] for t in schema.tables} == original_cols

    @pytest.mark.asyncio
    async def test_does_not_mutate_policy(self) -> None:
        policy = [{"table": "orders", "columns": ["id"]}]
        masks = [{"table": "orders", "columns": ["ssn"]}]
        snapshot_policy = [dict(p) for p in policy]
        snapshot_masks = [dict(m) for m in masks]
        rule = RoleAuthorizationRule(allowed_tables=policy, column_masks=masks)
        await rule.evaluate("SELECT id FROM orders", _schema())
        await rule.evaluate("SELECT ssn FROM orders", _schema())
        assert policy == snapshot_policy
        assert masks == snapshot_masks

    @pytest.mark.asyncio
    async def test_does_not_mutate_sql(self) -> None:
        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        sql = "SELECT ssn FROM orders"
        await rule.evaluate(sql, _schema())
        # The caller passed a string; the rule must not mutate it.
        assert sql == "SELECT ssn FROM orders"


# ────────────────────── Sanitized error / no leak ──────────────────────


class TestSanitizedError:
    @pytest.mark.asyncio
    async def test_reason_is_constant_across_violations(self) -> None:
        # Restrictive policy so every SQL in the list violates a check.
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        cases = [
            "SELECT id FROM payments",
            "SELECT ssn FROM orders",
            "SELECT ghost FROM orders",
            "DROP TABLE orders",
            "SELECT id FROM orders; SELECT id FROM customers",
        ]
        for sql in cases:
            result = await rule.evaluate(sql, _schema())
            assert result[0] is False
            assert result[1] == "query_blocked_policy", f"reason leaked: {result[1]!r}"

    @pytest.mark.asyncio
    async def test_reason_does_not_include_raw_sql(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        sql = "SELECT ghost_column FROM orders"
        result = await rule.evaluate(sql, _schema())
        assert result[0] is False
        assert "ghost_column" not in (result[1] or "")

    @pytest.mark.asyncio
    async def test_reason_does_not_include_table_or_column_names(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        sql = "SELECT secret_table_name.col_x FROM secret_table_name"
        result = await rule.evaluate(sql, _schema())
        assert result[0] is False
        reason = result[1] or ""
        assert "secret_table_name" not in reason
        assert "col_x" not in reason

    @pytest.mark.asyncio
    async def test_reason_does_not_include_schema_or_user_values(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        sql = "SELECT id FROM orders WHERE customer_id = 99999"
        result = await rule.evaluate(sql, _schema())
        assert result[0] is False
        reason = result[1] or ""
        assert "99999" not in reason
        assert "orders" not in reason
        assert "customer_id" not in reason


# ────────────────────── Pipeline registration / message key (T-710) ──────────────────────


class TestPipelineRegistration:
    @pytest.mark.asyncio
    async def test_pipeline_includes_role_authorization_message_key(self) -> None:
        """The pipeline's _MESSAGE_KEY_MAP must include role_authorization
        so that ``Evaluator`` translates the failed rule into the
        ``error.queryBlockedPolicy`` i18n key for the API response."""
        from app.evaluator import pipeline as pipeline_module

        assert "role_authorization" in pipeline_module._MESSAGE_KEY_MAP
        assert pipeline_module._MESSAGE_KEY_MAP["role_authorization"] == "error.queryBlockedPolicy"

    @pytest.mark.asyncio
    async def test_evaluator_translates_role_authorization_to_query_blocked_policy(self) -> None:
        evaluator = Evaluator(
            rules=[
                ReadOnlyRule(dialect="postgres"),
                SingleStatementRule(),
                SchemaValidationRule(),
                RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS),
            ]
        )
        result = await evaluator.evaluate(
            "SELECT id FROM payments",
            _schema(),
        )
        assert result.passed is False
        assert len(result.violations) == 1
        violation = result.violations[0]
        assert violation.rule_name == "role_authorization"
        assert violation.message_key == "error.queryBlockedPolicy"

    @pytest.mark.asyncio
    async def test_rule_is_runtime_checkable_protocol(self) -> None:
        from app.evaluator.protocol import EvaluatorRule

        rule = RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS)
        assert isinstance(rule, EvaluatorRule)
        assert rule.name == "role_authorization"

    @pytest.mark.asyncio
    async def test_rule_order_in_pipeline_can_be_appended_via_add_rule(self) -> None:
        """The new rule can be added to an existing pipeline via add_rule(),
        matching the T-154 extensibility contract."""
        pipeline = EvaluatorPipeline(
            rules=[
                ReadOnlyRule(dialect="postgres"),
                SingleStatementRule(),
            ]
        )
        pipeline.add_rule(RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS))
        result = await pipeline.run("SELECT id FROM payments", _schema())
        assert result.passed is False
        assert result.failed_rule == "role_authorization"
        assert result.reason == "query_blocked_policy"

    @pytest.mark.asyncio
    async def test_rule_passes_when_query_within_policy(self) -> None:
        evaluator = Evaluator(
            rules=[
                ReadOnlyRule(dialect="postgres"),
                SingleStatementRule(),
                SchemaValidationRule(),
                RoleAuthorizationRule(allowed_tables=_POLICY_ORDERS),
            ]
        )
        result = await evaluator.evaluate(
            "SELECT id FROM orders",
            _schema(),
        )
        assert result.passed is True


# ────────────────────── Star expansion (SELECT * / table.*) ──────────────────────


class TestStarExpansion:
    """Star references must NOT silently leak columns outside the role policy.

    ``SELECT *`` and ``SELECT t.*`` expand to one expression per physical
    column of the target table. The auth rule must block the star unless
    every physical column of the target table is granted. ``COUNT(*)`` and
    other aggregate stars are exempted because no column value reaches
    the user.
    """

    @pytest.mark.asyncio
    async def test_unqualified_star_blocked_by_subset_policy(self) -> None:
        """SELECT * with a subset policy (id only, ssn not granted)
        must block — ssn would otherwise be leaked."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        result = await rule.evaluate("SELECT * FROM orders", _schema())
        assert result == (False, "query_blocked_policy")

    @pytest.mark.asyncio
    async def test_unqualified_star_allowed_when_all_columns_granted(self) -> None:
        """SELECT * is allowed when the role is granted every physical
        column of the target table (intentional wide access)."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id", "ssn"]}],
        )
        result = await rule.evaluate("SELECT * FROM orders", _schema())
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_qualified_star_blocked_by_subset_policy(self) -> None:
        """SELECT orders.* with a subset policy (id only) must block."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        result = await rule.evaluate("SELECT orders.* FROM orders", _schema())
        assert result == (False, "query_blocked_policy")

    @pytest.mark.asyncio
    async def test_qualified_star_allowed_when_all_columns_granted(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id", "ssn"]}],
        )
        result = await rule.evaluate("SELECT orders.* FROM orders", _schema())
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_aliased_star_blocked_by_subset_policy(self) -> None:
        """``SELECT o.*`` with a subset policy (id only) must block."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        result = await rule.evaluate("SELECT o.* FROM orders o", _schema())
        assert result == (False, "query_blocked_policy")

    @pytest.mark.asyncio
    async def test_aliased_star_allowed_when_all_columns_granted(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id", "ssn"]}],
        )
        result = await rule.evaluate("SELECT o.* FROM orders o", _schema())
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_count_star_allowed_for_allowed_table(self) -> None:
        """COUNT(*) returns a scalar; no column value reaches the user.
        Must be allowed when the underlying table is allowed, even if
        no individual columns are granted."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        result = await rule.evaluate("SELECT COUNT(*) FROM orders", _schema())
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_count_star_with_subset_policy_allowing_zero_columns(self) -> None:
        """The table is in the policy but no columns are granted
        (deny-all columns). ``COUNT(*)`` is still allowed because it
        returns a scalar, not a column value."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": []}],
        )
        result = await rule.evaluate("SELECT COUNT(*) FROM orders", _schema())
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_star_blocked_for_disallowed_table_even_with_count(self) -> None:
        """COUNT(*) on a table outside the policy is still blocked at
        the table level (the table itself is not allowed)."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id"]}],
        )
        result = await rule.evaluate("SELECT COUNT(*) FROM payments", _schema())
        assert result == (False, "query_blocked_policy")

    @pytest.mark.asyncio
    async def test_unqualified_star_with_join_blocked_by_subset_policy(self) -> None:
        """SELECT * FROM orders JOIN customers: star applies to every
        referenced allowed table. With a subset policy on either, the
        star is blocked (FR-130 — must not leak columns from either)."""
        rule = RoleAuthorizationRule(
            allowed_tables=[
                {"table": "orders", "columns": ["id"]},
                {"table": "customers", "columns": ["id"]},
            ],
        )
        result = await rule.evaluate(
            "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.id",
            _schema(),
        )
        assert result == (False, "query_blocked_policy")

    @pytest.mark.asyncio
    async def test_unqualified_star_with_join_allowed_when_all_granted(self) -> None:
        rule = RoleAuthorizationRule(
            allowed_tables=[
                {"table": "orders", "columns": ["id", "customer_id", "ssn"]},
                {"table": "customers", "columns": ["id", "name"]},
            ],
        )
        result = await rule.evaluate(
            "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.id",
            _schema(),
        )
        assert result == (True, None)

    @pytest.mark.asyncio
    async def test_qualified_star_with_unknown_qualifier_blocked(self) -> None:
        """A qualified star whose qualifier is not in the alias map is
        blocked (defence in depth — schema validation would normally
        catch the missing table, but a config-only pipeline should
        still fail closed)."""
        rule = RoleAuthorizationRule(
            allowed_tables=[{"table": "orders", "columns": ["id", "customer_id", "ssn"]}],
        )
        result = await rule.evaluate("SELECT ghost.* FROM orders", _schema())
        assert result == (False, "query_blocked_policy")
