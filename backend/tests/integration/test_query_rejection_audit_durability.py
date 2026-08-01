"""Durability regressions for query rejection audit events."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text


async def _durable_counts(async_engine_fixture, action_type: str) -> dict[str, int]:
    async with async_engine_fixture.connect() as connection:
        values = {}
        for name, statement, params in (
            (
                "audit",
                "SELECT count(*) FROM audit_log_entries WHERE action_type = :action_type",
                {"action_type": action_type},
            ),
            ("sessions", "SELECT count(*) FROM sessions", {}),
            ("history", "SELECT count(*) FROM accepted_queries", {}),
        ):
            values[name] = int((await connection.execute(text(statement), params)).scalar_one())
        return values


@pytest.mark.integration
async def test_evaluator_rejection_audit_is_durable_without_request_side_effects(
    authenticated_client,
    async_engine_fixture,
    ensure_db_connection,
):
    llm = AsyncMock()
    llm.generate_sql.return_value = "DELETE FROM customer"
    execute = AsyncMock()
    before = await _durable_counts(async_engine_fixture, "query.validate.fail")

    with (
        patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=llm),
        patch("app.source_db.adapters.PostgresAdapter.execute", new=execute),
    ):
        response = await authenticated_client.post(
            "/api/v1/query/submit",
            json={"question": "Show customers", "connection_id": ensure_db_connection},
        )

    assert response.status_code == 422
    assert response.json()["message_key"] == "query.evaluator.rejected"
    execute.assert_not_awaited()
    after = await _durable_counts(async_engine_fixture, "query.validate.fail")
    assert after == {
        "audit": before["audit"] + 1,
        "sessions": before["sessions"],
        "history": before["history"],
    }

    async with async_engine_fixture.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT outcome, context
                    FROM audit_log_entries
                    WHERE action_type = 'query.validate.fail'
                    ORDER BY sequence_number DESC
                    LIMIT 1
                    """
                )
            )
        ).one()
    assert row.outcome == "failure"
    assert row.context == {"rules": ["read_only"]}
    assert "DELETE" not in json.dumps(row.context)


@pytest.mark.integration
async def test_deny_all_policy_audit_is_durable_without_llm_or_request_side_effects(
    authenticated_client,
    async_engine_fixture,
    ensure_db_connection,
):
    async with async_engine_fixture.begin() as connection:
        policy = (
            await connection.execute(
                text(
                    """
                    SELECT role_id, allowed_tables, row_filters, column_masks
                    FROM role_connection_policies
                    WHERE connection_id = :connection_id
                      AND role_id = (SELECT role_id FROM users WHERE username = 'admin')
                    """
                ),
                {"connection_id": ensure_db_connection},
            )
        ).one()
        await connection.execute(
            text(
                """
                DELETE FROM role_connection_policies
                WHERE role_id = :role_id AND connection_id = :connection_id
                """
            ),
            {"role_id": policy.role_id, "connection_id": ensure_db_connection},
        )

    llm = AsyncMock()
    before = await _durable_counts(async_engine_fixture, "access.denied")
    try:
        with patch("app.api.v1.query.LLMProviderFactory.from_config", return_value=llm):
            response = await authenticated_client.post(
                "/api/v1/query/submit",
                json={"question": "Show customers", "connection_id": ensure_db_connection},
            )

        assert response.status_code == 422
        assert response.json()["message_key"] == "error.queryBlockedPolicy"
        llm.generate_sql.assert_not_awaited()
        after = await _durable_counts(async_engine_fixture, "access.denied")
        assert after == {
            "audit": before["audit"] + 1,
            "sessions": before["sessions"],
            "history": before["history"],
        }

        async with async_engine_fixture.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT outcome, context
                        FROM audit_log_entries
                        WHERE action_type = 'access.denied'
                        ORDER BY sequence_number DESC
                        LIMIT 1
                        """
                    )
                )
            ).one()
        assert row.outcome == "denied"
        assert row.context == {"reason": "deny_all"}
    finally:
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO role_connection_policies (
                        role_id, connection_id, allowed_tables, row_filters, column_masks
                    )
                    VALUES (
                        :role_id, :connection_id, CAST(:allowed_tables AS jsonb),
                        CAST(:row_filters AS jsonb), CAST(:column_masks AS jsonb)
                    )
                    ON CONFLICT (role_id, connection_id) DO UPDATE SET
                        allowed_tables = EXCLUDED.allowed_tables,
                        row_filters = EXCLUDED.row_filters,
                        column_masks = EXCLUDED.column_masks,
                        updated_at = now()
                    """
                ),
                {
                    "role_id": policy.role_id,
                    "connection_id": ensure_db_connection,
                    "allowed_tables": json.dumps(policy.allowed_tables),
                    "row_filters": json.dumps(policy.row_filters),
                    "column_masks": json.dumps(policy.column_masks),
                },
            )
