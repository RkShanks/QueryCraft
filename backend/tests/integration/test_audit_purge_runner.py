"""Isolated runtime regression for the documented external purge runner."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

_BACKEND_ROOT = Path(__file__).parents[2]
_RUNNER = _BACKEND_ROOT / "scripts" / "purge_audit_logs.py"


def _invoke_runner() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_RUNNER)],
        cwd=_BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


async def _marker_count(async_engine_fixture) -> int:
    async with async_engine_fixture.connect() as connection:
        result = await connection.execute(
            text("SELECT count(*) FROM audit_log_entries WHERE action_type = 'audit.purge'")
        )
        return int(result.scalar_one())


@pytest.mark.usefixtures("clean_audit_table")
class TestAuditPurgeRunner:
    @pytest.mark.asyncio
    async def test_no_op_successful_purge_and_repeated_invocation(self, async_engine_fixture):
        no_op = _invoke_runner()
        assert no_op.returncode == 0
        assert await _marker_count(async_engine_fixture) == 0

        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO audit_log_entries (
                        sequence_number, timestamp, actor_identity, action_type,
                        outcome, context, prev_hash, row_hash
                    )
                    VALUES (
                        1, now() - interval '30 months', 'synthetic-runner',
                        'query.submit', 'success', '{}'::jsonb, 'GENESIS',
                        repeat('a', 64)
                    )
                    """
                )
            )

        successful = _invoke_runner()
        assert successful.returncode == 0
        assert await _marker_count(async_engine_fixture) == 1

        async with async_engine_fixture.connect() as connection:
            expired = await connection.execute(text("SELECT count(*) FROM audit_log_entries WHERE sequence_number = 1"))
            assert expired.scalar_one() == 0

        repeated = _invoke_runner()
        assert repeated.returncode == 0
        assert await _marker_count(async_engine_fixture) == 1

    @pytest.mark.asyncio
    async def test_delete_failure_rolls_back_marker_and_exits_safely(self, async_engine_fixture):
        async with async_engine_fixture.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO audit_log_entries (
                        sequence_number, timestamp, actor_identity, action_type,
                        outcome, context, prev_hash, row_hash
                    )
                    VALUES (
                        1, now() - interval '30 months', 'synthetic-rollback',
                        'query.submit', 'success', '{}'::jsonb, 'GENESIS',
                        repeat('b', 64)
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    CREATE FUNCTION fail_phase6c_audit_delete()
                    RETURNS trigger
                    LANGUAGE plpgsql
                    AS $$
                    BEGIN
                        RAISE EXCEPTION 'synthetic purge failure';
                    END;
                    $$
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    CREATE TRIGGER fail_phase6c_audit_delete_trigger
                    BEFORE DELETE ON audit_log_entries
                    FOR EACH STATEMENT
                    EXECUTE FUNCTION fail_phase6c_audit_delete()
                    """
                )
            )

        try:
            marker_count_before = await _marker_count(async_engine_fixture)
            failed = _invoke_runner()

            assert failed.returncode == 1
            assert await _marker_count(async_engine_fixture) == marker_count_before

            async with async_engine_fixture.connect() as connection:
                expired = await connection.execute(
                    text("SELECT count(*) FROM audit_log_entries WHERE sequence_number = 1")
                )
                assert expired.scalar_one() == 1

            combined_output = f"{failed.stdout}\n{failed.stderr}".lower()
            for forbidden in ("traceback", "asyncpg", "postgresql", "password", "127.0.0.1"):
                assert forbidden not in combined_output
        finally:
            async with async_engine_fixture.begin() as connection:
                await connection.execute(
                    text("DROP TRIGGER IF EXISTS fail_phase6c_audit_delete_trigger ON audit_log_entries")
                )
                await connection.execute(text("DROP FUNCTION IF EXISTS fail_phase6c_audit_delete()"))
