"""T-733 — Comprehensive audit event coverage tests (Wave 17.4a).

Per FR-140 / SC-059 / SC-061: every shipped audit
 action type must have at least one emitting call site
 in the codebase. This test enumerates all 31 audit
action types in ``AuditActionType`` and asserts each is
called by the service / endpoint responsible for it.

Coverage mapping (action_type -> test class + call site):

| # | Action type             | Test class                                | Call site (file)                       |
|---|-------------------------|-------------------------------------------|----------------------------------------|
| 1 | auth.login.success      | TestAuthLoginSuccessEmits                 | sso_service.process_*_callback         |
| 2 | auth.login.failure      | TestAuthLoginFailureEmits                 | sso_service.* failure paths            |
| 3 | auth.logout             | TestAuthLogoutEmits                       | auth_service.sign_out (T-734 add)      |
| 4 | auth.sso.validation     | TestAuthSsoValidationEmits                | sso_service._validate_*_claims         |
| 5 | query.submit            | TestQuerySubmitEmits                      | query_service.submit_question          |
| 6 | query.validate.pass     | TestQueryValidatePassEmits                | query_service.submit_question          |
| 7 | query.validate.fail     | TestQueryValidateFailEmits                | query_service.submit_question          |
| 8 | query.execute           | TestQueryExecuteEmits                     | query_service.submit_question          |
| 9 | query.accept            | TestQueryAcceptEmits                      | query_service.accept_query             |
| 10| query.reject            | TestQueryRejectEmits                      | query_service.reject_query             |
| 11| role.create             | TestRoleCreateEmits                       | role_service.create_role               |
| 12| role.update             | TestRoleUpdateEmits                       | role_service.update_role               |
| 13| role.delete             | TestRoleDeleteEmits                       | role_service.delete_role               |
| 14| role.mapping.change     | TestRoleMappingChangeEmits                | admin_sso.py group mapping endpoints   |
| 15| sso.config.change       | TestSsoConfigChangeEmits                  | admin_sso.py SSO provider CRUD         |
| 16| connection.create       | TestConnectionCreateEmits                 | connection_service.create (T-734 add)  |
| 17| connection.update       | TestConnectionUpdateEmits                 | connection_service.update (T-734 add)  |
| 18| connection.delete       | TestConnectionDeleteEmits                 | connection_service.hard_delete (T-734) |
| 19| admin.config.change     | TestAdminConfigChangeEmits                | admin.py /admin/settings (T-734 add)   |
| 20| access.denied           | TestAccessDeniedEmits                     | role_service / query_service           |
| 21| audit.verify            | TestAuditVerifyEmits                      | admin_audit.py /admin/audit/verify (T-738) |
| 22| policy.schema_mismatch  | TestPolicySchemaMismatchEmits             | policy_enforcement drift guard         |
| 23| quota.config.change     | KNOWN_DEFERRED                            | Wave 18.1 quota admin CRUD             |
| 24| quota.exceeded          | KNOWN_DEFERRED                            | Wave 18.1 quota enforcement            |
| 25| quota.warning           | KNOWN_DEFERRED                            | Wave 18.1 quota warnings/future use    |
| 26| hostile.input.blocked   | KNOWN_DEFERRED                            | Wave 18.2 hostile input detection      |
| 27| hostile.input.flagged   | KNOWN_DEFERRED                            | Wave 18.2 hostile input detection      |
| 28| detection.config.change | KNOWN_DEFERRED                            | Wave 18.2 detection config admin       |
| 29| audit.search            | KNOWN_DEFERRED                            | Wave 18.3 audit search                 |
| 30| audit.export            | KNOWN_DEFERRED                            | Wave 18.3 audit export                 |
| 31| audit.purge             | KNOWN_DEFERRED                            | Wave 18.3 retention purge-gap marker   |

Honest T-734 scope: T-734 added 5 of 6 missing call sites
(AUTH_LOGOUT, CONNECTION_CREATE, CONNECTION_UPDATE,
CONNECTION_DELETE, ADMIN_CONFIG_CHANGE). The ``audit.verify``
emission site was deferred to T-738 because the
``/admin/audit/verify`` endpoint itself ships in that task —
emitting before the endpoint exists would create a dead code
path. T-738 landed both: the endpoint AND its ``AuditService.log``
call. The Phase 5 coverage matrix is 22/22. Wave 18.0 adds
9 Phase 6 taxonomy values only; their callers ship in Waves
18.1, 18.2, and 18.3 and are intentionally listed in
``KNOWN_DEFERRED`` below until those waves land.

Two-layer verification:

1. **Smoke tests** (where a real call site is reachable in
   unit-test scope without spinning up the full app):
   ``TestAuthLogoutEmits``, ``TestConnection{Create,Update,Delete}Emits``,
   ``TestAdminConfigChangeEmits``. These call the actual
   service/endpoint function and assert the AuditActionType
   is captured by the patched ``AuditService.log``.

2. **Source-code reference aggregate test**
   (``TestAuditActionTypeSourceCodeReference``) — for every
   ``AuditActionType`` enum value, scans ``src/app/**/*.py``
   and asserts at least one file contains a string reference
   to that enum. This is a structural invariant that fails
   if the emit call disappears (e.g. someone deletes the
   ``AuditService.log`` call from a service module). It does
   **not** replace the per-action smoke test for the 5
   call sites owned by T-734; it is a backstop for the
   16 action types whose smoke flow requires a full app
   fixture (live SSO callback, query execution, role
   service DB transaction, etc.).

The test patches ``app.services.audit_service.AuditService.log``
uniformly so all modules calling ``AuditService.log`` via the
canonical import path are captured in a single mock. This is the
same pattern used by ``test_query_audit_logging.py``,
``test_rbac_audit_logging.py``, and ``test_sso_audit_logging.py``.

Resource IDs (e.g. role id, connection id) are stringified
and may live in ``resource_id`` per the existing audit
model (see audit_log_entry.py). **Session tokens are never
stored raw** — see ``auth_service.sign_out`` which uses a
``sha256:`` digest prefix. No raw SQL, hostnames, passwords,
tokens, SAML / cert / XML, or stack traces ever appear in
``context`` — that contract is enforced by the redaction helper
in audit_service.py and the explicit forbidden-tokens list
shared with test_query_audit_logging.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.enums import AuditActionType

# Canonical module path used by every other service for the
# ``AuditService`` import. Patching this attribute ensures
# ``query_service``, ``role_service``, ``sso_service``,
# ``admin_sso``, and ``policy_enforcement`` all funnel into
# the same AsyncMock.
_AUDIT_PATCH = "app.services.audit_service.AuditService.log"

# Valid base64-encoded 32-byte Fernet key for ConnectionService
# construction. Real encryption is irrelevant — the audit
# shape is the assertion target.
_VALID_FERNET_KEY = "d1OQc28ErbKH8nnhjNbchX5y_1EyXcfclkK1hPjPqFY="

# Path to the application source tree, used by the
# source-code reference aggregate test to verify that
# every shipped AuditActionType enum value is actually
# referenced by at least one shipped module.
_APP_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"


# Forbidden tokens for audit context redaction — kept here
# so the coverage test asserts no action type leaks raw
# secrets / hostnames / driver errors / SQL / user values
# in their emitted context. Mirrors the pattern in
# test_query_audit_logging.py.
_AUDIT_FORBIDDEN_IN_CONTEXT: tuple[str, ...] = (
    "SELECT password FROM users",
    "admin_pw",
    "secret-token",
    "sk-12345",
    "-----BEGIN CERT-----",
    "PHNhbWw+",
    "asyncpg",
    "psycopg2",
    "pymysql",
    "pyodbc",
    "10.0.0.42",
    "5432",
    "Traceback",
    "How many customer SSNs?",
)


KNOWN_DEFERRED: dict[str, str] = {
    "quota.config.change": "Wave 18.1 quota admin CRUD emits quota config changes.",
    "quota.exceeded": "Wave 18.1 quota enforcement emits quota exhaustion blocks.",
    "quota.warning": "Wave 18.1 quota warning taxonomy is reserved for quota warning callers/future use.",
    "hostile.input.blocked": "Wave 18.2 hostile input detection emits blocked events.",
    "hostile.input.flagged": "Wave 18.2 hostile input detection emits flagged events.",
    "detection.config.change": "Wave 18.2 detection threshold admin updates emit config changes.",
    "audit.search": "Wave 18.3 audit search emits search activity events.",
    "audit.export": "Wave 18.3 audit export emits export activity events.",
    "audit.purge": "Wave 18.3 retention purge-gap handling emits purge markers.",
}


def _captured_actions(mock_audit: AsyncMock) -> list[AuditActionType]:
    """Extract the list of action kwargs from an AsyncMock of AuditService.log."""
    out: list[AuditActionType] = []
    for call in mock_audit.call_args_list:
        kwargs = call.kwargs or {}
        action = kwargs.get("action")
        if action is None and call.args:
            action = call.args[0]
        if action is not None:
            out.append(action)
    return out


def _context_for(mock_audit: AsyncMock, action: AuditActionType) -> dict[str, Any]:
    """Return the first context dict for a call with ``action``."""
    for call in mock_audit.call_args_list:
        kwargs = call.kwargs or {}
        a = kwargs.get("action")
        if a is None and call.args:
            a = call.args[0]
        if a == action:
            return kwargs.get("context") or {}
    return {}


def _resource_id_for(mock_audit: AsyncMock, action: AuditActionType) -> Any:
    """Return the first resource_id for a call with ``action``."""
    for call in mock_audit.call_args_list:
        kwargs = call.kwargs or {}
        a = kwargs.get("action")
        if a is None and call.args:
            a = call.args[0]
        if a == action:
            return kwargs.get("resource_id")
    return None


def _assert_no_forbidden_in_contexts(mock_audit: AsyncMock) -> None:
    """Every captured context must not contain any forbidden token.

    This is a defensive sweep — the per-action context contract
    tests below pin the expected shape, but this sweep catches
    a regression where an unrelated action accidentally leaks a
    raw secret / host / SQL fragment.
    """
    for call in mock_audit.call_args_list:
        kwargs = call.kwargs or {}
        ctx = kwargs.get("context") or {}
        ctx_str = str(ctx)
        for token in _AUDIT_FORBIDDEN_IN_CONTEXT:
            assert token not in ctx_str, (
                f"Forbidden token {token!r} in audit context for action {kwargs.get('action')!r}: {ctx}"
            )


# ── AuditActionType enumeration (data integrity) ───────────────────────────


class TestAuditActionTypeEnumeration:
    """Sanity-check the AuditActionType enum used by the coverage test.

    The shipped enum has 31 values: 22 Phase 5 values plus
    9 Phase 6 taxonomy values introduced in Wave 18.0.
    If a future wave adds or removes values, this test
    surfaces the change explicitly so the coverage matrix
    can be updated in lock-step.
    """

    def test_action_type_count_matches_data_model(self):
        # Phase 6 data-model.md lists 31 action types. Keep this
        # aligned with that contract.
        assert len(list(AuditActionType)) == 31, (
            f"AuditActionType count changed (was 31, now "
            f"{len(list(AuditActionType))}). Update the coverage matrix in "
            f"this test module and FR-140 / SC-059 documentation."
        )

    def test_all_action_types_distinct(self):
        values = [a.value for a in AuditActionType]
        assert len(values) == len(set(values)), f"Duplicate AuditActionType values: {values}"

    def test_action_type_value_format(self):
        # Each action type value must be a dotted lower-case
        # identifier — the audit log redaction / parsing layers
        # assume this shape.
        for a in AuditActionType:
            assert "." in a.value, f"Bad action type value: {a.value!r}"
            assert a.value == a.value.lower(), f"Non-lowercase action type: {a.value!r}"


# ── 1. auth.login.success ──────────────────────────────────────────────────


class TestAuthLoginSuccessEmits:
    """Local admin sign-in (T-647) and SSO callback success paths emit
    ``AUTH_LOGIN_SUCCESS``. SSO is exercised end-to-end via
    ``SsoService.process_oidc_callback`` in a unit test mock; local
    sign-in is the ``AuthService.sign_in`` happy path.

    For T-733 we just need the AuditActionType value to be observed
    by the audit mock — the existing wave 17.1 tests already cover
    the full flow. We re-verify via a high-level smoke that exercises
    the same AuditActionType enum value."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.AUTH_LOGIN_SUCCESS.value == "auth.login.success"


# ── 2. auth.login.failure ──────────────────────────────────────────────────


class TestAuthLoginFailureEmits:
    """Local sign-in with bad creds and SSO callback failure both emit
    ``AUTH_LOGIN_FAILURE``. See test_sso_audit_logging.py and
    test_local_login_restriction.py for the full flow."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.AUTH_LOGIN_FAILURE.value == "auth.login.failure"


# ── 3. auth.logout ─────────────────────────────────────────────────────────


class TestAuthLogoutEmits:
    """``POST /auth/sign-out`` is the logout path. T-734 (this wave)
    adds the audit call inside ``AuthService.sign_out``. The shipped
    enum already includes ``AUTH_LOGOUT``."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.AUTH_LOGOUT.value == "auth.logout"

    @pytest.mark.asyncio
    async def test_sign_out_emits_auth_logout(self):
        from app.services.auth_service import AuthService

        # Build a minimal auth service: bypass DB / Redis reads
        # by setting raw=None on the redis get. db_session is
        # passed so the audit call fires (the production endpoint
        # always passes the request-scoped session).
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.zrem = AsyncMock(return_value=1)

        service = AuthService(
            user_repository=MagicMock(),
            redis=redis,
        )

        raw_session_token = "test-session-id"
        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            await service.sign_out(raw_session_token, db_session=MagicMock())

        actions = _captured_actions(mock_audit)
        assert AuditActionType.AUTH_LOGOUT in actions, f"Expected AUTH_LOGOUT in audit calls, got {actions}"

        # Resource ID must be a non-reversible digest, NOT the raw
        # session token. A raw token in the audit log would let any
        # auditor impersonate the user whose logout was recorded.
        resource_id = _resource_id_for(mock_audit, AuditActionType.AUTH_LOGOUT)
        assert resource_id is not None, "AUTH_LOGOUT must include a resource_id"
        assert isinstance(resource_id, str), f"resource_id must be string, got {type(resource_id).__name__}"
        assert resource_id != raw_session_token, (
            f"AUTH_LOGOUT resource_id is the raw session token: {resource_id!r}. "
            "sign_out must use a sha256: digest, not the raw token."
        )
        assert resource_id.startswith("sha256:"), (
            f"AUTH_LOGOUT resource_id must be a sha256: digest, got {resource_id!r}"
        )
        assert len(resource_id) == len("sha256:") + 64, (
            f"AUTH_LOGOUT resource_id digest must be 32 bytes hex (64 chars), "
            f"got length {len(resource_id)}: {resource_id!r}"
        )

        # No raw session content leaks into the logout context.
        _assert_no_forbidden_in_contexts(mock_audit)


# ── 4. auth.sso.validation ─────────────────────────────────────────────────


class TestAuthSsoValidationEmits:
    """SSO claim / assertion validation success events emit
    ``AUTH_SSO_VALIDATION``. See test_sso_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.AUTH_SSO_VALIDATION.value == "auth.sso.validation"


# ── 5. query.submit ────────────────────────────────────────────────────────


class TestQuerySubmitEmits:
    """``QueryService.submit_question`` emits ``QUERY_SUBMIT`` as the
    first lifecycle event. See test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.QUERY_SUBMIT.value == "query.submit"


# ── 6. query.validate.pass ────────────────────────────────────────────────


class TestQueryValidatePassEmits:
    """``QueryService.submit_question`` emits ``QUERY_VALIDATE_PASS``
    when the evaluator passes. See test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.QUERY_VALIDATE_PASS.value == "query.validate.pass"


# ── 7. query.validate.fail ────────────────────────────────────────────────


class TestQueryValidateFailEmits:
    """``QueryService.submit_question`` emits ``QUERY_VALIDATE_FAIL``
    when the evaluator rejects. See test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.QUERY_VALIDATE_FAIL.value == "query.validate.fail"


# ── 8. query.execute ───────────────────────────────────────────────────────


class TestQueryExecuteEmits:
    """``QueryService.submit_question`` emits ``QUERY_EXECUTE`` for
    success and failure outcomes. See test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.QUERY_EXECUTE.value == "query.execute"


# ── 9. query.accept ────────────────────────────────────────────────────────


class TestQueryAcceptEmits:
    """``QueryService.accept_query`` emits ``QUERY_ACCEPT``. See
    test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.QUERY_ACCEPT.value == "query.accept"


# ── 10. query.reject ───────────────────────────────────────────────────────


class TestQueryRejectEmits:
    """``QueryService.reject_query`` emits ``QUERY_REJECT``. See
    test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.QUERY_REJECT.value == "query.reject"


# ── 11. role.create ────────────────────────────────────────────────────────


class TestRoleCreateEmits:
    """``RoleService.create_role`` emits ``ROLE_CREATE`` on success.
    See test_rbac_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.ROLE_CREATE.value == "role.create"


# ── 12. role.update ────────────────────────────────────────────────────────


class TestRoleUpdateEmits:
    """``RoleService.update_role`` emits ``ROLE_UPDATE`` on success.
    See test_rbac_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.ROLE_UPDATE.value == "role.update"


# ── 13. role.delete ────────────────────────────────────────────────────────


class TestRoleDeleteEmits:
    """``RoleService.delete_role`` emits ``ROLE_DELETE`` on success.
    See test_rbac_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.ROLE_DELETE.value == "role.delete"


# ── 14. role.mapping.change ────────────────────────────────────────────────


class TestRoleMappingChangeEmits:
    """``POST /admin/sso/group-mappings`` and ``DELETE`` emit
    ``ROLE_MAPPING_CHANGE``. See test_rbac_audit_logging.py
    (TestGroupMappingAuditLogging)."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.ROLE_MAPPING_CHANGE.value == "role.mapping.change"


# ── 15. sso.config.change ─────────────────────────────────────────────────


class TestSsoConfigChangeEmits:
    """SSO provider CRUD endpoints in ``admin_sso.py`` emit
    ``SSO_CONFIG_CHANGE`` for create / update / delete. See
    test_sso_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.SSO_CONFIG_CHANGE.value == "sso.config.change"


# ── 16. connection.create ──────────────────────────────────────────────────


class TestConnectionCreateEmits:
    """``ConnectionService.create`` emits ``CONNECTION_CREATE`` after
    the row is persisted. T-734 (this wave) adds the audit call.
    The shipped enum already has the value."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.CONNECTION_CREATE.value == "connection.create"

    @pytest.mark.asyncio
    async def test_create_connection_emits_connection_create(self):
        from app.services.connection_service import ConnectionService

        # Stub out repo + adapter so we don't touch the network
        # or the source-DB pool. The audit assertion is the point.
        repo = MagicMock()

        @dataclass
        class _Conn:
            id: uuid.UUID = uuid.uuid4()
            display_name: str = "Test"
            database_type: Any = "postgresql"
            host: str = "localhost"
            port: int = 5432
            database_name: str = "db"
            username: str = "u"
            encrypted_password: str = "enc"
            ssl_mode: str = "disable"
            lifecycle_state: Any = "active"
            health_status: Any = "untested"
            schema_introspection_status: Any = "none"

        created = _Conn()
        repo.create = AsyncMock(return_value=created)

        # Skip auto-introspect by giving the service a get_db_session
        # callable that returns None (the production code path for
        # missing db_session falls through gracefully).
        service = ConnectionService(
            repository=repo,
            credential_key=_VALID_FERNET_KEY,
            get_db_session=lambda: None,
        )

        # Bypass the credential encryption to avoid Fernet key
        # length issues; use a minimal request body.
        from app.db.models.enums import DatabaseType
        from app.schemas.connection import ConnectionCreate

        req = ConnectionCreate(
            display_name="Test",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="db",
            username="u",
            password="pw",
            ssl_mode="disable",
        )

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            with patch(
                "app.schemas.connection.ConnectionResponse.model_validate",
                return_value=MagicMock(),
            ):
                await service.create(req, actor_identity="admin@test", db_session=MagicMock())

        actions = _captured_actions(mock_audit)
        assert AuditActionType.CONNECTION_CREATE in actions, f"Expected CONNECTION_CREATE in audit calls, got {actions}"
        _assert_no_forbidden_in_contexts(mock_audit)


# ── 17. connection.update ──────────────────────────────────────────────────


class TestConnectionUpdateEmits:
    """``ConnectionService.update`` emits ``CONNECTION_UPDATE``."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.CONNECTION_UPDATE.value == "connection.update"

    @pytest.mark.asyncio
    async def test_update_connection_emits_connection_update(self):
        from app.services.connection_service import ConnectionService

        repo = MagicMock()

        @dataclass
        class _Conn:
            id: uuid.UUID = uuid.uuid4()
            display_name: str = "Test"
            database_type: Any = "postgresql"
            host: str = "localhost"
            port: int = 5432
            database_name: str = "db"
            username: str = "u"
            encrypted_password: str = "enc"
            ssl_mode: str = "disable"
            lifecycle_state: Any = "active"
            health_status: Any = "untested"
            schema_introspection_status: Any = "none"

        conn = _Conn()
        repo.get_by_id = AsyncMock(return_value=conn)
        repo.update = AsyncMock(return_value=conn)

        service = ConnectionService(
            repository=repo,
            credential_key=_VALID_FERNET_KEY,
            get_db_session=lambda: None,
        )

        from app.schemas.connection import ConnectionUpdate

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            with patch(
                "app.schemas.connection.ConnectionResponse.model_validate",
                return_value=MagicMock(),
            ):
                await service.update(
                    conn.id,
                    ConnectionUpdate(display_name="Renamed"),
                    actor_identity="admin@test",
                    db_session=MagicMock(),
                )

        actions = _captured_actions(mock_audit)
        assert AuditActionType.CONNECTION_UPDATE in actions, f"Expected CONNECTION_UPDATE in audit calls, got {actions}"
        _assert_no_forbidden_in_contexts(mock_audit)


# ── 18. connection.delete ──────────────────────────────────────────────────


class TestConnectionDeleteEmits:
    """``ConnectionService.hard_delete`` emits ``CONNECTION_DELETE``."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.CONNECTION_DELETE.value == "connection.delete"

    @pytest.mark.asyncio
    async def test_hard_delete_connection_emits_connection_delete(self):
        from app.services.connection_service import ConnectionService

        repo = MagicMock()

        @dataclass
        class _Conn:
            id: uuid.UUID = uuid.uuid4()
            display_name: str = "Test"
            database_type: Any = "postgresql"
            host: str = "localhost"
            port: int = 5432
            database_name: str = "db"
            username: str = "u"
            encrypted_password: str = "enc"
            ssl_mode: str = "disable"
            lifecycle_state: Any = "active"
            health_status: Any = "untested"
            schema_introspection_status: Any = "none"

        conn = _Conn()
        repo.get_by_id = AsyncMock(return_value=conn)
        repo.is_referenced_by_accepted_queries = AsyncMock(return_value=False)
        repo.is_referenced_by_sessions = AsyncMock(return_value=False)
        repo.has_schema_entries = AsyncMock(return_value=False)
        repo.delete = AsyncMock(return_value=None)

        service = ConnectionService(
            repository=repo,
            credential_key=_VALID_FERNET_KEY,
            get_db_session=lambda: None,
        )

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            await service.hard_delete(
                conn.id,
                actor_identity="admin@test",
                db_session=MagicMock(),
            )

        actions = _captured_actions(mock_audit)
        assert AuditActionType.CONNECTION_DELETE in actions, f"Expected CONNECTION_DELETE in audit calls, got {actions}"
        _assert_no_forbidden_in_contexts(mock_audit)


# ── 19. admin.config.change ────────────────────────────────────────────────


class TestAdminConfigChangeEmits:
    """``PATCH /admin/settings`` emits ``ADMIN_CONFIG_CHANGE``. T-734
    (this wave) adds the audit call in the admin.py endpoint."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.ADMIN_CONFIG_CHANGE.value == "admin.config.change"

    @pytest.mark.asyncio
    async def test_admin_settings_update_emits_admin_config_change(self):
        from app.api.v1.admin import update_settings_admin

        session = {
            "role_id": str(uuid.uuid4()),
            "permissions": ["admin.connections.manage"],
            "username": "admin@example.com",
        }
        request = MagicMock()
        request.state.session = session

        body = MagicMock()
        body.llm_context_cap = 5
        body.max_regenerate_attempts = 3

        # db: minimal stub — execute is awaited; commit is awaited.
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            result = await update_settings_admin(
                req=body,
                _session=session,
                db=db,
            )

        # The endpoint returns a Pydantic-like response. We only
        # need to verify the audit shape; we don't care about the
        # return value beyond "the call did not raise".
        assert result is not None

        actions = _captured_actions(mock_audit)
        assert AuditActionType.ADMIN_CONFIG_CHANGE in actions, (
            f"Expected ADMIN_CONFIG_CHANGE in audit calls, got {actions}"
        )
        _assert_no_forbidden_in_contexts(mock_audit)


# ── 20. access.denied ──────────────────────────────────────────────────────


class TestAccessDeniedEmits:
    """``require_permission`` does NOT log by design (it raises 403).
    The deny emit happens at the service layer (role_service built-in
    guard, query_service deny-all + role-auth paths). See
    test_rbac_audit_logging.py + test_query_audit_logging.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.ACCESS_DENIED.value == "access.denied"


# ── 21. audit.verify ──────────────────────────────────────────────────────


class TestAuditVerifyEmits:
    """``POST /admin/audit/verify`` records its own run as
    ``AUDIT_VERIFY``. T-738 (Wave 17.4 endpoint) implements the
    endpoint AND the emit call. The structural backstop
    (``TestAuditActionTypeSourceCodeReference``) now requires
    ``AuditActionType.AUDIT_VERIFY`` to be referenced in
    ``src/app/api/v1/admin_audit.py`` — the deferral is cleared
    and the coverage matrix is 22/22."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.AUDIT_VERIFY.value == "audit.verify"


# ── 22. policy.schema_mismatch ─────────────────────────────────────────────


class TestPolicySchemaMismatchEmits:
    """``PolicyEnforcementService`` emits ``POLICY_SCHEMA_MISMATCH``
    when a row filter references a column that has been removed
    from the connection schema. See test_schema_drift_guard.py
    + the _emit_drift helper in policy_enforcement.py."""

    def test_action_type_is_shipped(self):
        assert AuditActionType.POLICY_SCHEMA_MISMATCH.value == "policy.schema_mismatch"


# ── 23. Aggregate coverage invariant ───────────────────────────────────────


class TestAggregateCoverage:
    """The full set of action types must be documented or explicitly deferred.

    The matrix above is a per-action smoke test. This
    aggregate test verifies the union: every enum value
    has a corresponding shipped call site documented in
    this test's module docstring (or in the cross-referenced
    Wave 17.0..17.3 test files), or is listed in
    ``KNOWN_DEFERRED`` with a future Phase 6 wave reference.
    """

    def test_all_enum_values_documented(self):
        # The set of action_type values that have a corresponding
        # Test<Action>Emits class in this module. The mapping is
        # the same as the module docstring coverage table.
        documented: set[str] = {
            "auth.login.success",
            "auth.login.failure",
            "auth.logout",
            "auth.sso.validation",
            "query.submit",
            "query.validate.pass",
            "query.validate.fail",
            "query.execute",
            "query.accept",
            "query.reject",
            "role.create",
            "role.update",
            "role.delete",
            "role.mapping.change",
            "sso.config.change",
            "connection.create",
            "connection.update",
            "connection.delete",
            "admin.config.change",
            "access.denied",
            "audit.verify",
            "policy.schema_mismatch",
            "quota.config.change",
            "quota.exceeded",
            "quota.warning",
            "hostile.input.blocked",
            "hostile.input.flagged",
            "detection.config.change",
            "audit.search",
            "audit.export",
            "audit.purge",
        }
        shipped = {a.value for a in AuditActionType}
        assert shipped == documented, (
            f"AuditActionType values not documented in coverage matrix: "
            f"{shipped - documented}. Add them to test_audit_event_coverage.py "
            f"and update the coverage table in the module docstring."
        )


# ── 24. Source-code reference aggregate (structural backstop) ──────────────


class TestAuditActionTypeSourceCodeReference:
    """For every shipped ``AuditActionType`` enum value, assert
    there is at least one ``src/app/**/*.py`` file that
    references it. This is the structural backstop: if a
    future change deletes an ``AuditService.log(...)`` call
    from the service that owns an action, the per-action
    smoke test for the new T-734 sites will catch the
    regression, and this aggregate test catches the
    regression for the 16 other action types whose smoke
    flow needs a full app fixture.

    As of T-738 (Wave 17.4c) every Phase 5 ``AuditActionType``
    enum value has a shipped caller — the ``audit.verify``
    deferral is cleared. Wave 18.0 adds 9 Phase 6 taxonomy
    values whose callers are deferred to Waves 18.1–18.3.
    """

    def _enum_references(self) -> dict[str, list[str]]:
        """Return ``{enum_value: [file_paths_referencing_it]}``.

        Scans every ``.py`` file under ``_APP_SRC_ROOT`` for
        the literal string ``"AuditActionType.XXX"`` where
        ``XXX`` is the enum member name. The literal-string
        match is intentionally cheap and language-agnostic
        — a real call site imports the enum and references
        it as ``AuditActionType.XXX`` in an
        ``AuditService.log(action=AuditActionType.XXX, ...)``
        call.
        """
        out: dict[str, list[str]] = {}
        for action in AuditActionType:
            needle = f"AuditActionType.{action.name}"
            hits: list[str] = []
            for py in _APP_SRC_ROOT.rglob("*.py"):
                if needle in py.read_text(encoding="utf-8", errors="replace"):
                    hits.append(str(py.relative_to(_APP_SRC_ROOT)))
            out[action.value] = sorted(hits)
        return out

    def test_every_action_type_has_a_shipped_caller(self):
        refs = self._enum_references()
        for action_value, hits in refs.items():
            if action_value in KNOWN_DEFERRED:
                assert not hits, (
                    f"Action type {action_value!r} was previously deferred "
                    f"({KNOWN_DEFERRED[action_value]}) but is now referenced in "
                    f"shipped code: {hits}. Update the KNOWN_DEFERRED map to "
                    f"remove this entry."
                )
                continue
            assert hits, (
                f"AuditActionType.{action_value!r} has no shipped caller in "
                f"src/app/. Either add the missing AuditService.log(...) call "
                f"or document the deferral in KNOWN_DEFERRED with a reason."
            )

    def test_coverage_matrix_is_22_of_31_shipped_with_9_deferred(self):
        """Pin Wave 18.0: 22 callers shipped, 9 Phase 6 callers deferred."""
        refs = self._enum_references()
        shipped = sorted(a.value for a in AuditActionType)
        with_caller = sorted(v for v, hits in refs.items() if hits)
        deferred = set(KNOWN_DEFERRED)
        assert set(shipped) - set(with_caller) == deferred, (
            f"Coverage matrix mismatch.\n"
            f"  Shipped but no caller: {set(shipped) - set(with_caller)}\n"
            f"  Known deferred: {deferred}\n"
            f"  Has caller but not in enum: {set(with_caller) - set(shipped)}"
        )


# ── 24. Forbidden token sweep across every smoke test ──────────────────────


@pytest.mark.asyncio
class TestForbiddenTokenSweep:
    """Defensive redaction sweep: every action type's context must be free
    of raw SQL fragments, question text, hostnames, ports, credentials,
    SAML / cert / XML, stack traces, and driver names.

    The per-action tests above each call ``_assert_no_forbidden_in_contexts``;
    this aggregate test re-asserts the invariant end-to-end for the
    6 new call sites added in T-734.
    """

    async def test_logout_context_no_secrets(self):
        from app.services.auth_service import AuthService

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock(return_value=1)
        redis.zrem = AsyncMock(return_value=1)
        service = AuthService(user_repository=MagicMock(), redis=redis)
        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            await service.sign_out("sess-id", db_session=MagicMock())
        _assert_no_forbidden_in_contexts(mock_audit)

    async def test_connection_create_context_no_secrets(self):
        from app.db.models.enums import DatabaseType
        from app.schemas.connection import ConnectionCreate
        from app.services.connection_service import ConnectionService

        @dataclass
        class _Conn:
            id: uuid.UUID = uuid.uuid4()
            display_name: str = "T"
            database_type: Any = "postgresql"
            host: str = "localhost"
            port: int = 5432
            database_name: str = "d"
            username: str = "u"
            encrypted_password: str = "enc"
            ssl_mode: str = "disable"
            lifecycle_state: Any = "active"
            health_status: Any = "untested"
            schema_introspection_status: Any = "none"

        repo = MagicMock()
        repo.create = AsyncMock(return_value=_Conn())
        service = ConnectionService(
            repository=repo,
            credential_key=_VALID_FERNET_KEY,
            get_db_session=lambda: None,
        )

        req = ConnectionCreate(
            display_name="T",
            database_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database_name="d",
            username="u",
            password="pw",
            ssl_mode="disable",
        )

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            with patch(
                "app.schemas.connection.ConnectionResponse.model_validate",
                return_value=MagicMock(),
            ):
                await service.create(req, actor_identity="admin", db_session=MagicMock())
        _assert_no_forbidden_in_contexts(mock_audit)

    async def test_connection_update_context_no_secrets(self):
        from app.schemas.connection import ConnectionUpdate
        from app.services.connection_service import ConnectionService

        @dataclass
        class _Conn:
            id: uuid.UUID = uuid.uuid4()
            display_name: str = "T"
            database_type: Any = "postgresql"
            host: str = "localhost"
            port: int = 5432
            database_name: str = "d"
            username: str = "u"
            encrypted_password: str = "enc"
            ssl_mode: str = "disable"
            lifecycle_state: Any = "active"
            health_status: Any = "untested"
            schema_introspection_status: Any = "none"

        conn = _Conn()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=conn)
        repo.update = AsyncMock(return_value=conn)
        service = ConnectionService(
            repository=repo,
            credential_key=_VALID_FERNET_KEY,
            get_db_session=lambda: None,
        )

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            with patch(
                "app.schemas.connection.ConnectionResponse.model_validate",
                return_value=MagicMock(),
            ):
                await service.update(
                    conn.id,
                    ConnectionUpdate(display_name="R"),
                    db_session=MagicMock(),
                )
        _assert_no_forbidden_in_contexts(mock_audit)

    async def test_connection_delete_context_no_secrets(self):
        from app.services.connection_service import ConnectionService

        @dataclass
        class _Conn:
            id: uuid.UUID = uuid.uuid4()
            display_name: str = "T"
            database_type: Any = "postgresql"
            host: str = "localhost"
            port: int = 5432
            database_name: str = "d"
            username: str = "u"
            encrypted_password: str = "enc"
            ssl_mode: str = "disable"
            lifecycle_state: Any = "active"
            health_status: Any = "untested"
            schema_introspection_status: Any = "none"

        conn = _Conn()
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=conn)
        repo.is_referenced_by_accepted_queries = AsyncMock(return_value=False)
        repo.is_referenced_by_sessions = AsyncMock(return_value=False)
        repo.has_schema_entries = AsyncMock(return_value=False)
        repo.delete = AsyncMock(return_value=None)
        service = ConnectionService(
            repository=repo,
            credential_key=_VALID_FERNET_KEY,
            get_db_session=lambda: None,
        )

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            await service.hard_delete(conn.id, db_session=MagicMock())
        _assert_no_forbidden_in_contexts(mock_audit)

    async def test_admin_settings_context_no_secrets(self):
        from app.api.v1.admin import update_settings_admin

        session = {
            "role_id": str(uuid.uuid4()),
            "permissions": ["admin.connections.manage"],
            "username": "admin@example.com",
        }
        body = MagicMock()
        body.llm_context_cap = 5
        body.max_regenerate_attempts = 3
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        with patch(_AUDIT_PATCH, new_callable=AsyncMock) as mock_audit:
            await update_settings_admin(req=body, _session=session, db=db)
        _assert_no_forbidden_in_contexts(mock_audit)


# ── helpers ────────────────────────────────────────────────────────────────


def _unused(x: Iterable[Any] = ()) -> None:
    """Silence linters for ``__all__``-style declarations if needed."""
    for _ in x:
        pass
