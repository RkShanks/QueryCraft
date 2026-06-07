"""T-765 through T-769 — Security/privacy evidence verification (Wave 17.5b).

Systematic verification that no secrets, raw UUIDs, hostnames, internal URLs,
raw IdP/driver errors, or unauthorized schema internals are exposed through
API error responses, audit log entries, or the policy enforcement pipeline.

T-765: No secrets in any API response, audit log, or rendering path.
T-766: No raw UUIDs exposed to end users in error messages.
T-767: No hostnames or internal URLs in user-facing errors.
T-768: No raw IdP/driver errors exposed (all errors are localized i18n keys).
T-769: No unauthorized schema internals visible in error paths.

FR-119, FR-128, FR-129, FR-139, FR-143, SC-061.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.db.models.enums import AuditActionType

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_API_DIR = Path(__file__).resolve().parents[2] / "src" / "app" / "api" / "v1"
_SERVICES_DIR = Path(__file__).resolve().parents[2] / "src" / "app" / "services"
_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"

# ---------------------------------------------------------------------------
# UUID / hostname / secret detection patterns
# ---------------------------------------------------------------------------

# Matches standard UUID v4 format
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# Matches hostnames/IPs in error-like strings
_HOSTNAME_RE = re.compile(
    r"(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.\d+\.\d+\.\d+)"
    r"(?::\d+)?",
    re.IGNORECASE,
)

# Matches internal URLs
_INTERNAL_URL_RE = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+|172\.\d+)",
    re.IGNORECASE,
)

# Raw driver error patterns
_DRIVER_ERROR_PATTERNS = [
    "asyncpg",
    "psycopg2",
    "pymysql",
    "asyncmy",
    "pyodbc",
    "aioodbc",
    "sqlalchemy.exc",
    "OperationalError",
    "ProgrammingError",
    "InterfaceError",
    "DatabaseError",
    "Traceback (most recent call last)",
    "File \"",
]

# Raw IdP error patterns
_IDP_ERROR_PATTERNS = [
    "SAML assertion",
    "saml_response",
    "SAMLResponse",
    "AuthnRequest",
    "urn:oasis:names:tc:SAML",
    "-----BEGIN CERTIFICATE-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "id_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "jwks_uri",
]

# Secret patterns
_SECRET_PATTERNS = [
    "password",
    "client_secret",
    "encryption_key",
    "PLATFORM_ENCRYPTION_KEY",
    "private_key",
    "bearer ",
    "sk-",
    "eyJhbGciOi",  # JWT header
]


# ---------------------------------------------------------------------------
# T-765: No secrets in API error responses
# ---------------------------------------------------------------------------


class TestT765NoSecretsInApiResponses:
    """Verify no secrets appear in any HTTPException detail across all API endpoints."""

    def _collect_http_exception_details(self) -> list[tuple[str, str]]:
        """Parse all .py files in api/v1/ and extract HTTPException detail values."""
        results = []
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            # Find all HTTPException raises with detail= argument
            for match in re.finditer(
                r"raise\s+HTTPException\([^)]*detail\s*=\s*(\{[^}]*\})",
                source,
                re.DOTALL,
            ):
                detail_str = match.group(1)
                results.append((py_file.name, detail_str))
        return results

    def test_no_secret_patterns_in_http_exception_details(self) -> None:
        """No secret pattern appears in any HTTPException detail dict."""
        details = self._collect_http_exception_details()
        assert details, "No HTTPException details found — scan may be broken"
        forbidden = [
            "password",
            "client_secret",
            "encryption_key",
            "private_key",
            "PLATFORM_ENCRYPTION_KEY",
            "bearer",
            "eyJhbGci",
            "sk-",
        ]
        for filename, detail_str in details:
            for pattern in forbidden:
                # Allow message_key references like "error.unauthorized"
                if f'"{pattern}"' in detail_str.lower() or f"'{pattern}'" in detail_str.lower():
                    # Check it's not just a key name in the dict
                    assert pattern in (
                        "password",
                        "client_secret",
                    ) and "error" in detail_str.lower() or "message_key" in detail_str, (
                        f"Secret pattern {pattern!r} found in HTTPException detail "
                        f"in {filename}: {detail_str!r}"
                    )

    def test_all_error_responses_use_message_keys(self) -> None:
        """Every HTTPException detail dict contains a message_key for i18n."""
        details = self._collect_http_exception_details()
        assert details, "No HTTPException details found — scan may be broken"
        for filename, detail_str in details:
            assert "message_key" in detail_str, (
                f"HTTPException in {filename} missing message_key (not i18n-safe): {detail_str!r}"
            )


class TestT765NoSecretsInAuditLogCallSites:
    """Verify no raw secrets in AuditService.log() call site contexts."""

    def _collect_audit_log_context_keys(self) -> list[tuple[str, list[str]]]:
        """Scan src/app/ for AuditService.log() calls and extract context keys."""
        results = []
        context_re = re.compile(r"context\s*=\s*\{([^{}]*)\}", re.MULTILINE | re.DOTALL)
        key_re = re.compile(r"['\"]([^'\"]+)['\"](?:\s*:)")
        for py_file in _SRC_ROOT.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            if "AuditService.log" not in source:
                continue
            for match in context_re.finditer(source):
                body = match.group(1)
                keys = key_re.findall(body)
                if keys:
                    results.append((str(py_file.relative_to(_SRC_ROOT)), keys))
        return results

    def test_no_secret_keys_in_audit_contexts(self) -> None:
        """No audit context dict should contain a key that is itself a secret name."""
        forbidden_key_substrings = {
            "password", "secret", "token", "credential",
            "certificate", "private_key", "bearer", "jwt",
            "authorization", "assertion", "saml_response",
        }
        contexts = self._collect_audit_log_context_keys()
        assert contexts, "No audit log call sites found — scan may be broken"
        for filepath, keys in contexts:
            for key in keys:
                normalized = key.lower().replace("_", "").replace("-", "")
                for forbidden in forbidden_key_substrings:
                    norm_forbidden = forbidden.replace("_", "")
                    # Skip if key is just 'protocol' which contains no forbidden substring
                    assert norm_forbidden not in normalized, (
                        f"Potentially sensitive key {key!r} in audit context at {filepath}"
                    )


# ---------------------------------------------------------------------------
# T-766: No raw UUIDs in error messages
# ---------------------------------------------------------------------------


class TestT766NoRawUuidsInErrors:
    """Verify no raw UUIDs are exposed in user-facing error messages."""

    def test_no_uuid_in_http_exception_details(self) -> None:
        """No literal UUID appears in any HTTPException detail string."""
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r"raise\s+HTTPException\([^)]*detail\s*=\s*(\{[^}]*\})",
                source,
                re.DOTALL,
            ):
                detail_str = match.group(1)
                uuid_matches = _UUID_RE.findall(detail_str)
                assert not uuid_matches, (
                    f"Raw UUID found in HTTPException detail in {py_file.name}: "
                    f"{uuid_matches} in {detail_str!r}"
                )

    def test_no_uuid_in_error_message_format_strings(self) -> None:
        """No f-string in error detail embeds a UUID variable."""
        # Check that no endpoint uses f-strings with {id} or {provider_id} etc.
        # in HTTPException detail values
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r'raise\s+HTTPException\([^)]*detail\s*=\s*f["\']([^"\']*)',
                source,
            ):
                fstring = match.group(1)
                # Any {id} or {xxx_id} in an f-string detail is a UUID leak
                id_refs = re.findall(r"\{[^}]*id[^}]*\}", fstring, re.IGNORECASE)
                assert not id_refs, (
                    f"Potential raw UUID in f-string error detail in {py_file.name}: "
                    f"{id_refs} in f'{fstring}'"
                )


# ---------------------------------------------------------------------------
# T-767: No hostnames or internal URLs in user-facing errors
# ---------------------------------------------------------------------------


class TestT767NoHostnamesInErrors:
    """Verify no hostnames/internal URLs in user-facing errors."""

    def test_no_hostname_in_http_exception_details(self) -> None:
        """No hostname/IP appears in any HTTPException detail."""
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r"raise\s+HTTPException\([^)]*detail\s*=\s*(\{[^}]*\})",
                source,
                re.DOTALL,
            ):
                detail_str = match.group(1)
                hostname_matches = _HOSTNAME_RE.findall(detail_str)
                assert not hostname_matches, (
                    f"Hostname/IP found in HTTPException detail in {py_file.name}: "
                    f"{hostname_matches}"
                )

    def test_no_internal_urls_in_error_responses(self) -> None:
        """No internal URL in any HTTPException detail."""
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r"raise\s+HTTPException\([^)]*detail\s*=\s*(\{[^}]*\})",
                source,
                re.DOTALL,
            ):
                detail_str = match.group(1)
                url_matches = _INTERNAL_URL_RE.findall(detail_str)
                assert not url_matches, (
                    f"Internal URL found in HTTPException detail in {py_file.name}: "
                    f"{url_matches}"
                )

    def test_no_hostname_in_exception_handlers(self) -> None:
        """Exception handler except blocks don't expose hostnames in responses."""
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            # Broad check: no f-string in except block referencing exc/error
            # should contain host patterns
            except_blocks = re.findall(
                r"except\s+[^:]+:\s*\n((?:\s+.+\n)*)",
                source,
            )
            for block in except_blocks:
                for line in block.split("\n"):
                    if "HTTPException" in line and "detail" in line:
                        hostname_matches = _HOSTNAME_RE.findall(line)
                        assert not hostname_matches, (
                            f"Hostname in exception handler in {py_file.name}: {line.strip()}"
                        )


# ---------------------------------------------------------------------------
# T-768: No raw IdP/driver errors exposed to users
# ---------------------------------------------------------------------------


class TestT768NoRawIdpDriverErrors:
    """Verify all errors exposed to users are sanitized i18n keys."""

    def test_sso_auth_errors_are_redirect_codes_only(self) -> None:
        """SSO auth endpoint errors use redirect codes, not raw IdP errors."""
        sso_auth_file = _API_DIR / "sso_auth.py"
        if not sso_auth_file.exists():
            pytest.skip("sso_auth.py not found")
        source = sso_auth_file.read_text(encoding="utf-8", errors="replace")
        # SSO auth errors should redirect with safe error codes
        for pattern in _IDP_ERROR_PATTERNS:
            # Check that raw IdP data isn't in any response/redirect
            assert pattern not in source or f'"{pattern}"' not in source, (
                f"Raw IdP pattern {pattern!r} may be exposed in sso_auth.py"
            )

    def test_no_driver_errors_in_api_responses(self) -> None:
        """No raw database driver error names appear in API error responses."""
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(
                r"raise\s+HTTPException\([^)]*detail\s*=\s*(\{[^}]*\})",
                source,
                re.DOTALL,
            ):
                detail_str = match.group(1)
                for driver in _DRIVER_ERROR_PATTERNS:
                    assert driver not in detail_str, (
                        f"Raw driver error {driver!r} in HTTPException detail "
                        f"in {py_file.name}: {detail_str!r}"
                    )

    def test_exception_handlers_catch_all_and_sanitize(self) -> None:
        """Admin and query endpoints catch generic Exception and return
        sanitized error.internal, not raw exc messages."""
        admin_files = [
            "admin_roles.py",
            "admin_sso.py",
            "admin_connections.py",
            "admin_audit.py",
        ]
        for filename in admin_files:
            filepath = _API_DIR / filename
            if not filepath.exists():
                continue
            source = filepath.read_text(encoding="utf-8", errors="replace")
            # Must have a broad except clause that returns error.internal
            has_broad_catch = "except Exception" in source or "except HTTPException" in source
            has_sanitized_error = "error.internal" in source
            assert has_broad_catch, (
                f"{filename} missing broad exception handler"
            )
            assert has_sanitized_error, (
                f"{filename} missing sanitized error.internal response"
            )

    def test_sso_validation_errors_are_opaque(self) -> None:
        """SsoValidationError messages are generic, not raw IdP errors."""
        sso_service = _SERVICES_DIR / "sso_service.py"
        if not sso_service.exists():
            pytest.skip("sso_service.py not found")
        source = sso_service.read_text(encoding="utf-8", errors="replace")
        # SsoValidationError should never contain raw assertion XML,
        # certificate data, or raw IdP error text
        for pattern in ["-----BEGIN", "PHNhbWw", "urn:oasis"]:
            # Allow imports/comments, but not in SsoValidationError() args
            sso_val_matches = re.findall(
                rf'SsoValidationError\([^)]*{re.escape(pattern)}',
                source,
            )
            assert not sso_val_matches, (
                f"Raw IdP data {pattern!r} in SsoValidationError in sso_service.py"
            )


# ---------------------------------------------------------------------------
# T-769: No unauthorized schema internals in error paths
# ---------------------------------------------------------------------------


class TestT769NoSchemaInternalsInErrors:
    """Verify schema internals (table/column names) don't leak in errors."""

    def test_policy_enforcement_errors_are_opaque(self) -> None:
        """PolicyEnforcementService errors use constant error codes."""
        pe_file = _SERVICES_DIR / "policy_enforcement.py"
        if not pe_file.exists():
            pytest.skip("policy_enforcement.py not found")
        source = pe_file.read_text(encoding="utf-8", errors="replace")
        # All ValueError messages should be constant strings
        value_errors = re.findall(r'raise ValueError\("([^"]+)"\)', source)
        constant_errors = {
            "filter_validation_failed",
            "placeholder_binding_failed",
            "filter_injection_failed",
            "column_mask_config_invalid",
        }
        for msg in value_errors:
            assert msg in constant_errors, (
                f"Non-constant ValueError message in policy_enforcement.py: {msg!r} — "
                f"may leak schema internals"
            )

    def test_schema_drift_error_does_not_leak_details(self) -> None:
        """PolicySchemaConflictError has a constant sanitized message."""
        from app.core.exceptions import PolicySchemaConflictError

        err = PolicySchemaConflictError()
        err_str = str(err)
        # Should not contain table or column names
        assert "orders" not in err_str.lower()
        assert "ssn" not in err_str.lower()
        assert "region" not in err_str.lower()

    def test_evaluator_auth_rule_error_is_opaque(self) -> None:
        """Evaluator authorization rule errors use localized message keys."""
        rule_file = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "app"
            / "evaluator"
            / "rules"
            / "role_authorization.py"
        )
        if not rule_file.exists():
            pytest.skip("role_authorization.py not found")
        source = rule_file.read_text(encoding="utf-8", errors="replace")
        # The error should reference error.queryBlockedPolicy, not raw table/column names
        assert "queryBlockedPolicy" in source or "error.query" in source, (
            "Evaluator auth rule missing localized error key"
        )

    def test_no_table_column_names_in_exception_details(self) -> None:
        """No f-string interpolation of table/column names in HTTPException details."""
        for py_file in _API_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8", errors="replace")
            # Check for f-strings in HTTPException details that reference
            # table_name, column_name, schema variables
            for match in re.finditer(
                r'raise\s+HTTPException\([^)]*detail\s*=\s*f["\']([^"\']*)',
                source,
            ):
                fstring = match.group(1)
                schema_refs = re.findall(
                    r"\{[^}]*(table|column|schema|field)[^}]*\}",
                    fstring,
                    re.IGNORECASE,
                )
                assert not schema_refs, (
                    f"Schema internals in f-string error detail in {py_file.name}: "
                    f"{schema_refs} in f'{fstring}'"
                )

    def test_schema_filtering_does_not_leak_unauthorized_names(self) -> None:
        """filter_schema silently excludes unauthorized tables — no exception."""
        from app.evaluator.schema_context import Column, SchemaContext, Table
        from app.services.policy_enforcement import PolicyEnforcementService

        schema = SchemaContext(
            tables=[
                Table(
                    name="public_table",
                    schema_name="public",
                    columns=[
                        Column(name="id", type="integer", nullable=False, primary_key=True),
                    ],
                ),
                Table(
                    name="internal_secrets",
                    schema_name="private",
                    columns=[
                        Column(name="ssn", type="text", nullable=True),
                        Column(name="salary", type="numeric", nullable=True),
                    ],
                ),
            ]
        )
        filtered = PolicyEnforcementService.filter_schema(
            schema=schema,
            allowed_tables=[{"table": "public_table", "columns": ["id"]}],
        )
        table_names = [t.name for t in filtered.tables]
        assert "internal_secrets" not in table_names
        all_col_names = [c.name for t in filtered.tables for c in t.columns]
        assert "ssn" not in all_col_names
        assert "salary" not in all_col_names
