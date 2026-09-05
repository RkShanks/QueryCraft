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
def test_api_contract(case, set_test_env, async_engine_fixture, redis_client, contract_request):
    """Every application operation returns a declared unauthenticated or public response."""
    response = contract_request(case)
    case.validate_response(response, excluded_checks=(checks.ignored_auth,))


def test_repeated_contract_cases_close_redis_on_their_owning_loop(
    api_schema, contract_request, async_engine_fixture, redis_client, event_loop
):
    """T-892 freeze blocker: repeated portals must not reuse or leak Redis sockets."""
    case = api_schema["/api/v1/admin/audit/filter-context"]["POST"].make_case(
        cookies={"session_id": "absent-contract-lifecycle-session"},
        body={"filters": {}},
        media_type="application/json",
    )
    connections_before = len(event_loop.run_until_complete(redis_client.client_list()))

    for _ in range(3):
        response = contract_request(case)
        assert response.status_code == 401
        assert response.json()["message_key"] == "error.unauthorized"
        case.validate_response(response, excluded_checks=(checks.ignored_auth,))

    assert len(event_loop.run_until_complete(redis_client.client_list())) == connections_before
