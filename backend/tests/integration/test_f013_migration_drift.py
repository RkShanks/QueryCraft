"""F-013 — Silent migration drift at startup.

If alembic current < head, the backend starts cleanly (no warning) and
produces opaque 500s when endpoints hit missing columns.

Reproduction test (EXPECTED TO FAIL on current main — RED).
"""

import logging

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f013_startup_refuses_or_warns_on_alembic_drift(async_engine_fixture, caplog):
    """F-013: app startup should refuse, auto-upgrade, or emit a loud
    warning when alembic current < head.

    Test scenario: roll the alembic_version table back to '001', then
    create a fresh app via `create_app()` and trigger lifespan.
    Assert that EITHER:
    - app refuses to start (raises RuntimeError), OR
    - app emits a structured WARN log with event='migration_drift_detected'
    """
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    head_revision = script.get_current_head()

    # 1. Roll back alembic_version to '001'
    async with async_engine_fixture.connect() as conn:
        await conn.execute(text("UPDATE alembic_version SET version_num = '001'"))
        await conn.commit()

    # 2. Capture WARN+ logs
    caplog.set_level(logging.WARNING)

    # 3. Create fresh app and trigger lifespan (startup)
    # NOTE: httpx.ASGITransport does not send lifespan events; we drive the
    # lifespan context manager directly so the startup hook runs.
    from app.main import create_app

    app = create_app()

    runtime_error_raised = False
    try:
        async with app.router.lifespan_context(app):
            pass
    except RuntimeError:
        runtime_error_raised = True

    # 4. Restore alembic_version so subsequent tests are not broken
    async with async_engine_fixture.connect() as conn:
        await conn.execute(text("UPDATE alembic_version SET version_num = :head"), {"head": head_revision})
        await conn.commit()

    # 5. Assert desired behaviour
    drift_logs = [
        r for r in caplog.records if r.levelno >= logging.WARNING and "migration_drift_detected" in r.getMessage()
    ]

    assert runtime_error_raised or drift_logs, (
        "F-013: startup allowed drift without warning or refusal. "
        f"RuntimeError={runtime_error_raised}, drift_logs={len(drift_logs)}"
    )
