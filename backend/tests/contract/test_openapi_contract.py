"""Schemathesis contract-test harness (T-016).

Validates that FastAPI responses match the OpenAPI 3.1 contract.
"""

from pathlib import Path

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis import checks
from schemathesis.experimental import OPEN_API_3_1

from app.main import create_app

# Enable experimental OpenAPI 3.1 support (T-226)
OPEN_API_3_1.enable()

schema_path = Path(__file__).resolve().parents[2] / "openapi.json"


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
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_api_contract(case, set_test_env, async_engine_fixture, redis_client):
    """Every application operation returns a declared unauthenticated or public response."""
    from app.core.security import SessionMiddleware
    from app.db import base as db_base

    db_base._engine = None
    db_base._session_factory = None
    for middleware in SessionMiddleware._instances:
        middleware._redis = None
    response = case.call_asgi(headers={"origin": "http://test"})
    case.validate_response(response, excluded_checks=(checks.ignored_auth,))
