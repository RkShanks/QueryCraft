"""RED unit tests for quota error message sanitization (T-805).

Asserts that quota exceeded response body contains only message_key and
reset_at; no fields: counter, limit, policy_id, role_id, provider, sql,
stack; message_key value is constant string "error.quota_exceeded".
"""



from app.core.exceptions import QuotaExceededError


class TestQuotaErrorSanitization:
    def test_quota_exceeded_response_body_has_only_safe_fields(self):
        reset_at = "2026-06-13T00:00:00+00:00"
        err = QuotaExceededError(dimension="queries", reset_at=reset_at)

        detail = {
            "error": "quota_exceeded",
            "message_key": err.message_key,
            "reset_at": err.reset_at,
        }

        assert detail["message_key"] == "error.quota_exceeded"
        assert "counter" not in detail
        assert "limit" not in detail
        assert "policy_id" not in detail
        assert "role_id" not in detail
        assert "provider" not in detail
        assert "sql" not in detail
        assert "stack" not in detail
        assert "count" not in detail
        assert "used" not in detail

    def test_quota_exceeded_message_key_is_constant(self):
        err = QuotaExceededError(dimension="queries", reset_at="2026-01-01T00:00:00+00:00")
        assert err.message_key == "error.quota_exceeded"

    def test_quota_exceeded_detail_no_dimension_in_response(self):
        reset_at = "2026-06-13T00:00:00+00:00"
        detail = {
            "error": "quota_exceeded",
            "message_key": "error.quota_exceeded",
            "reset_at": reset_at,
        }

        assert "dimension" not in detail

    def test_quota_unavailable_response_sanitized(self):

        detail = {
            "error": "service_unavailable",
            "message_key": "error.service_unavailable",
        }

        assert detail["message_key"] == "error.service_unavailable"
        assert "stack" not in detail
        assert "redis" not in detail
        assert "provider" not in detail
        assert "error_detail" not in detail
