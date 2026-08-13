"""T-124 + T-125: Schemathesis contract tests for /query endpoints.

Loads the canonical OpenAPI 3.1 contract. Uses a pre-authenticated session
cookie.

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


@schema.parametrize(endpoint="/api/v1/query/submit")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_query_submit_contract(case, contract_session_cookie):
    """Property-based contract test for POST /query/submit."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
        excluded_checks=(schemathesis.checks.ignored_auth,),
    )


@schema.parametrize(endpoint="/api/v1/query/reject")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_query_reject_contract(case, contract_session_cookie):
    """Property-based contract test for POST /query/reject."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
        excluded_checks=(schemathesis.checks.ignored_auth,),
    )


@schema.parametrize(endpoint="/api/v1/query/regenerate")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_query_regenerate_contract(case, contract_session_cookie):
    """Property-based contract test for POST /query/regenerate."""
    case.call_and_validate(
        cookies={"session_id": contract_session_cookie},
        headers={"origin": "http://test"},
        excluded_checks=(schemathesis.checks.ignored_auth,),
    )
