"""Schemathesis contract-test harness (T-016).

Validates that FastAPI responses match the OpenAPI 3.1 contract.
"""

import schemathesis
from pathlib import Path

# Load the OpenAPI schema from the running app
# In CI, this will be run against a live test server
schema_path = Path(__file__).resolve().parents[3] / "specs/001-core-text-to-sql/contracts/openapi.yaml"

import schemathesis
import pytest
from app.main import create_app

@pytest.fixture
def api_schema():
    app = create_app()
    return schemathesis.from_path(str(schema_path), app=app)

# Load the OpenAPI schema from the running app using a fixture
# This ensures it uses the mocked test environment from conftest.py
schema = schemathesis.from_pytest_fixture("api_schema")

@schema.parametrize()
def test_api_contract(case, set_test_env, async_engine_fixture, redis_client):
    """Every endpoint must return a response matching the OpenAPI contract."""
    response = case.call_asgi()
    case.validate_response(response)
