"""Schemathesis contract-test harness (T-016).

Validates that FastAPI responses match the OpenAPI 3.1 contract.
"""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import schemathesis
from schemathesis import checks
from schemathesis.experimental import OPEN_API_3_1

from app.main import create_app

# Enable experimental OpenAPI 3.1 support (T-226)
OPEN_API_3_1.enable()

# Load the OpenAPI schema from the running app
# In CI, this will be run against a live test server
schema_path = Path(__file__).resolve().parents[3] / "specs/001-core-text-to-sql/contracts/openapi.yaml"


@pytest.fixture
def api_schema():
    from app.db import base as db_base

    db_base._engine = None
    db_base._session_factory = None
    app = create_app()
    return schemathesis.from_path(str(schema_path), app=app)


# Load the OpenAPI schema from the running app using a fixture
# This ensures it uses the mocked test environment from conftest.py
schema = schemathesis.from_pytest_fixture("api_schema")


@schema.parametrize()
def test_api_contract(case, set_test_env, async_engine_fixture, redis_client, contract_session_cookie, monkeypatch):
    """Every endpoint must return a response matching the OpenAPI contract."""
    from app.api.v1 import admin as admin_api
    from app.core.security import SessionMiddleware
    from app.db import base as db_base

    class StubIntrospector:
        async def refresh(self):
            return SimpleNamespace(tables=[SimpleNamespace(columns=[object()])])

        def _count_tokens(self, schema):
            return 1

    db_base._engine = None
    db_base._session_factory = None
    for middleware in SessionMiddleware._instances:
        middleware._redis = None
    monkeypatch.setattr(admin_api, "_get_introspector", lambda: StubIntrospector())
    session_cookie = contract_session_cookie
    if case.path == "/auth/sign-out":
        session_cookie = uuid4().hex
    response = case.call_asgi(
        headers={
            "origin": "http://test",
            "Cookie": f"session_id={session_cookie}",
            "X-Admin-Key": "test-admin-key-123",
        }
    )
    case.validate_response(response, excluded_checks=(checks.ignored_auth,))
