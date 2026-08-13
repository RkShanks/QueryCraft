"""T-161: Schemathesis-driven contract tests for /history and /history/{id}.

Loads the canonical OpenAPI 3.1 contract. Uses session cookie for auth.

The property-based sweep runs on demand to keep the default gate bounded.
"""

import os
import pathlib

import pytest
import schemathesis
from hypothesis import HealthCheck, settings

from app.main import create_app

pytestmark = pytest.mark.contract

if not os.environ.get("SCHEMATHESIS_RUN"):
    pytest.skip(
        "Schemathesis tests run on demand: SCHEMATHESIS_RUN=1 pytest -m contract",
        allow_module_level=True,
    )

_schema_path = pathlib.Path(__file__).resolve().parents[2] / "openapi.json"
schema = schemathesis.openapi.from_path(
    str(_schema_path),
    app=create_app(),
)


@schema.parametrize(endpoint="/api/v1/history")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_history_list_contract(case, contract_session_cookie):
    """Property-based contract test for GET /history."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
        excluded_checks=(schemathesis.checks.ignored_auth,),
    )


@schema.parametrize(endpoint="/api/v1/history/.*")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_history_detail_contract(case, contract_session_cookie):
    """Property-based contract test for GET /history/{id}."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
        excluded_checks=(schemathesis.checks.ignored_auth,),
    )
