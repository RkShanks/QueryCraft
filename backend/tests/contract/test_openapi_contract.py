"""Schemathesis contract-test harness (T-016).

Validates that FastAPI responses match the OpenAPI 3.1 contract.
"""

import schemathesis

# Load the OpenAPI schema from the running app
# In CI, this will be run against a live test server
schema = schemathesis.from_path(
    "../../specs/001-core-text-to-sql/contracts/openapi.yaml",
    base_url="http://localhost:8000",
)


@schema.parametrize()
def test_api_contract(case):
    """Every endpoint must return a response matching the OpenAPI contract."""
    response = case.call()
    case.validate_response(response)
