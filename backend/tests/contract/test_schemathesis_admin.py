"""T-126: Schemathesis contract test for /admin/refresh-schema.

Loads the canonical OpenAPI 3.1 contract. Uses session cookie for admin auth.

The property-based sweep runs on demand to keep the default gate bounded.
"""

import os
import pathlib

import pytest
import schemathesis
from hypothesis import HealthCheck, settings

pytestmark = pytest.mark.contract

if not os.environ.get("SCHEMATHESIS_RUN"):
    pytest.skip(
        "Schemathesis tests run on demand: SCHEMATHESIS_RUN=1 pytest -m contract",
        allow_module_level=True,
    )

_schema_path = pathlib.Path(__file__).resolve().parents[2] / "openapi.json"
schema = schemathesis.openapi.from_path(
    str(_schema_path),
)


@schema.parametrize(endpoint="/api/v1/admin/refresh-schema")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_admin_contract(case, contract_session_cookie, contract_request):
    """Property-based contract test for Admin endpoints."""
    response = contract_request(case, cookies={"session_id": contract_session_cookie})
    case.validate_response(
        response,
        excluded_checks=(schemathesis.checks.ignored_auth,),
    )
