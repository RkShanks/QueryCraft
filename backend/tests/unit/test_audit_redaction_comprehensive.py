"""T-736 — Comprehensive audit redaction tests (Wave 17.4b).

Per FR-143 / SC-061: no secret, credential, token, or host /
schema / SQL / driver-error / stack-trace value may appear in
any audit entry ``context`` across all action types. The
shipped ``AuditService.log`` calls ``_redact_value(context)``
which performs a recursive, case-insensitive, snake-camel
normalizing walk of the dict and replaces the value of any
sensitive key with ``"[REDACTED]"``.

The previous wave's narrow smoke test
(``test_audit_redaction.py``) covers a handful of patterns for
one action type. This module expands that surface to:

1. **Per-action-type redaction** — for every shipped
   ``AuditActionType`` enum value (22), log an entry with a
   secret-laden context and assert every forbidden key is
   scrubbed. The redaction helper is action-type-agnostic; this
   parametrization catches a future special-case branch.
2. **Per-key redaction** — for every sensitive token in the
   shipped set (``password``, ``secret``, ``token``,
   ``apikey``, ``credential``, ``certificate``, ``privatekey``,
   ``assertion``, ``samlresponse``, ``authorization``,
   ``encryptionkey``, ``bearer``, ``jwt``), exercise the
   helper on each variant (snake, camel, capitalized, mixed).
3. **Case + format insensitivity** — the helper normalizes
   keys with ``.lower().replace("_","").replace("-","")`` so
   ``Authorization``, ``AUTHORIZATION``, ``saml-response``,
   and ``SAMLResponse`` all redact. The tests pin each
   variant explicitly.
4. **Deep nesting** — secrets at depth ≥3 (dict-in-list-in-dict)
   must still redact. The helper recurses; this test pins the
   depth contract.
5. **Safe-key preservation** — ``question``, ``dialect``,
   ``count``, ``name``, ``priority``, ``updated_fields``,
   ``reason`` etc. must NOT be touched. False-positive
   redaction would erase the diagnostic value of the audit
   log.
6. **Structural sweep** — every ``AuditService.log(...)`` call
   site in ``src/app/`` must not pass a literal value
   containing forbidden patterns (PEM cert marker, SAML XML
   base64 prefix, IP:port tuple, raw SQL fragment, driver
   name, stack-trace marker, raw secret string). The sweep
   is a backstop for the runtime key-based redaction.

The runtime helper is **key-based** — values in safe-named
keys are NOT scrubbed. That is by design (the helper
otherwise has to guess at value-shape, which is brittle and
forbiddingly slow on large contexts). The structural sweep
above enforces the inverse contract: callers MUST NOT pass
secrets under safe-named keys.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from app.db.models.enums import AuditActionType
from app.services.audit_service import AuditService

# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------


# Same forbidden tokens as the redaction helper. Keep this
# list in sync with ``_SENSITIVE_TOKENS`` in
# ``app/services/audit_service.py``. If you add a token to
# one, add it to the other.
_FORBIDDEN_KEY_TOKENS: tuple[str, ...] = (
    "password",
    "secret",
    "token",
    "apikey",
    "credential",
    "certificate",
    "privatekey",
    "assertion",
    "samlresponse",
    "authorization",
    "encryptionkey",
    "bearer",
    "jwt",
)


# Forbidden VALUE patterns that the structural sweep checks
# for. The runtime redaction is key-based, so these are
# checked at the source-code level only — they would only
# appear in ``context=`` literals if a future maintainer
# accidentally passes a raw secret / host / driver-error /
# stack-trace value.
_FORBIDDEN_VALUE_PATTERNS: tuple[str, ...] = (
    "-----BEGIN CERT-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----",
    "PHNhbWw+",  # base64 of "<saml"
    "PHNhbWxw",  # base64 of "<samlp"
    "asyncpg",
    "psycopg2",
    "pymysql",
    "pyodbc",
    "Traceback (most recent call last)",
    "SELECT password FROM",
    "DROP TABLE users",
    "192.168.1.1:5432",
    "10.0.0.42",
    "How many customer SSNs?",
    "supersecret",
    "sk-12345",
    "admin_pw",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",  # JWT header
)


# Keys that are explicitly safe — the redaction helper must
# leave their values untouched. If a future change makes the
# helper too aggressive, these tests will fail first.
_SAFE_KEYS: tuple[str, ...] = (
    "question",
    "dialect",
    "count",
    "name",
    "priority",
    "updated_fields",
    "reason",
    "outcome",
    "resource_type",
    "resource_id",
    "actor_identity",
    "llm_context_cap",
    "max_regenerate_attempts",
    "row_count",
    "duration_ms",
    # Keys in actual call sites today. Adding them to the
    # safe set makes the structural sweep (test below)
    # happy and pins the contract that they are not
    # redacted.
    "display_name",
    "database_type",
    "changed_fields",
    "question_length",
    "rules",
    "protocol",
    "action",
    "sso_group_value",
    "role_id",
    # T-738 audit.verify context: chain walk result metadata.
    # verified/entries_checked/first_break_at are safe — they describe
    # the audit chain walk outcome, not any sensitive value.
    "verified",
    "entries_checked",
    "first_break_at",
)


# Sample context with one forbidden key per sensitive token.
# Used by the per-action-type sweep.
_SECRET_LADEN_CONTEXT: dict[str, Any] = {
    "password": "p",
    "secret": "s",
    "token": "t",
    "api_key": "k",
    "credential": "c",
    "certificate": "-----BEGIN CERT-----",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----",
    "assertion": "<assertion/>",
    "saml_response": "PHNhbWw+",
    "Authorization": "Bearer xyz",
    "encryption_key": "k1",
    "bearer": "b",
    "jwt": "eyJ...",
    # Safe keys must survive.
    "question": "How many customers?",
    "dialect": "postgresql",
    "count": 42,
    "name": "alice",
}


# Application source root, used by the structural sweep.
_APP_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_shipped_log_call_literals() -> list[tuple[str, dict[str, Any]]]:
    """Return ``[(file, context_dict_literal), ...]`` for every
    ``AuditService.log(...)`` call site in ``src/app/``.

    Only call sites with a literal ``context={...}`` argument
    are returned; call sites that build the context dict
    dynamically cannot be statically verified and rely on
    the per-action-type runtime tests above.

    This is a static-AST scan, not an import. It walks
    ``src/app/**/*.py``, finds every ``AuditService.log(...)``
    call, and uses a small regex to extract the literal
    ``context=`` argument when it is a dict expression.

    The regex intentionally matches the most common shape
    ``context={"key": value, ...}`` — multi-line literals are
    not supported; those call sites are listed in the module
    docstring as known-dynamic.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    context_re = re.compile(r"context\s*=\s*\{([^{}]*)\}", re.MULTILINE | re.DOTALL)
    keyval_re = re.compile(r"['\"](?P<k>[^'\"]+)['\"]\s*:\s*(?P<v>[^,\n]+)")
    for py in _APP_SRC_ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="replace")
        if "AuditService.log" not in text:
            continue
        for match in context_re.finditer(text):
            body = match.group(1)
            entry: dict[str, Any] = {}
            for kv in keyval_re.finditer(body):
                k = kv.group("k")
                v = kv.group("v").strip()
                # Treat any non-numeric / non-bool / non-string
                # value as opaque.
                if v.startswith('"') or v.startswith("'"):
                    entry[k] = v.strip("'\"")
                else:
                    entry[k] = v
            if entry:
                out.append((str(py.relative_to(_APP_SRC_ROOT)), entry))
    return out


# ---------------------------------------------------------------------------
# 1. Per-action-type redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestRedactionRunsForEveryActionType:
    """For every shipped ``AuditActionType`` (22 values), log an
    entry whose ``context`` contains one forbidden key per
    sensitive token, and assert every forbidden key's value is
    ``"[REDACTED]"`` in the returned entry."""

    @pytest.mark.parametrize(
        "action",
        list(AuditActionType),
        ids=[a.name for a in AuditActionType],
    )
    async def test_all_forbidden_keys_redacted(self, db_session, action):
        entry = await AuditService.log(
            db_session,
            action=action,
            context=dict(_SECRET_LADEN_CONTEXT),
        )
        ctx = entry.context
        for forbidden_key in (
            "password",
            "secret",
            "token",
            "api_key",
            "credential",
            "certificate",
            "private_key",
            "assertion",
            "saml_response",
            "Authorization",
            "encryption_key",
            "bearer",
            "jwt",
        ):
            assert ctx[forbidden_key] == "[REDACTED]", (
                f"Forbidden key {forbidden_key!r} not redacted for action {action!r}: got {ctx[forbidden_key]!r}"
            )
        # Safe keys survive.
        assert ctx["question"] == "How many customers?"
        assert ctx["dialect"] == "postgresql"
        assert ctx["count"] == 42
        assert ctx["name"] == "alice"


# ---------------------------------------------------------------------------
# 2. Per-key redaction (broaden the surface beyond the original T-623 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestEveryForbiddenKeyIsRedacted:
    """One test per sensitive token. Each test logs an entry whose
    context contains ONLY the forbidden key (plus a safe control
    key) and asserts the forbidden value becomes ``"[REDACTED]"``
    while the safe value is untouched."""

    @pytest.mark.parametrize(
        "key,sample",
        [
            ("password", "supersecret"),
            ("pass_word", "supersecret"),
            ("PASSWORD", "supersecret"),
            ("Password", "supersecret"),
            ("user_password", "supersecret"),
            ("secret", "shh"),
            ("client_secret", "shh"),
            ("SECRET", "shh"),
            ("token", "tok-abc"),
            ("access_token", "eyJ..."),
            ("id_token", "eyJid_token..."),
            ("refresh_token", "rt-123"),
            ("auth_token", "at-123"),
            ("api_key", "sk-12345"),
            ("apikey", "sk-67890"),
            ("API_KEY", "sk-99999"),
            ("api-key", "sk-11111"),
            ("credential", "cred-val"),
            ("credentials", "cred-val2"),
            ("certificate", "-----BEGIN CERT-----"),
            ("client_certificate", "-----BEGIN CERT-----"),
            ("private_key", "-----BEGIN RSA PRIVATE KEY-----"),
            ("privatekey", "-----BEGIN RSA PRIVATE KEY-----"),
            ("assertion", "<assertion/>"),
            ("saml_response", "PHNhbWw+"),
            ("SAMLResponse", "PHNhbWw+"),
            ("saml-response", "PHNhbWw+"),
            ("authorization", "Bearer xyz"),
            ("Authorization", "Bearer xyz"),
            ("AUTHORIZATION", "Bearer xyz"),
            ("encryption_key", "k1"),
            ("encryptionkey", "k2"),
            ("bearer", "b"),
            ("Bearer", "b"),
            ("jwt", "eyJhbGci..."),
            ("JWT", "eyJhbGci..."),
        ],
    )
    async def test_key_is_redacted(self, db_session, key, sample):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={key: sample, "control": "ok"},
        )
        assert entry.context[key] == "[REDACTED]", f"Key {key!r} should redact; got {entry.context[key]!r}"
        assert entry.context["control"] == "ok", f"Control key was touched by redaction: {entry.context['control']!r}"


# ---------------------------------------------------------------------------
# 3. Safe-key preservation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestSafeKeysAreNotRedacted:
    """The redaction helper must leave non-sensitive keys alone.
    False-positive redaction would erase the diagnostic value
    of the audit log. The shipped helper normalizes the key
    name with ``.lower().replace("_",""),replace("-","")`` and
    matches against the sensitive token set. None of the
    safe keys below contain a sensitive substring.
    """

    @pytest.mark.parametrize("key", _SAFE_KEYS)
    async def test_safe_key_preserved(self, db_session, key):
        sample_value = f"sample-{key}-value"
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={key: sample_value},
        )
        assert entry.context[key] == sample_value, (
            f"Safe key {key!r} was unexpectedly modified by redaction: "
            f"got {entry.context[key]!r}, expected {sample_value!r}"
        )


# ---------------------------------------------------------------------------
# 4. Deep nesting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestDeepNestingRedacts:
    """Secrets at depth ≥ 3 (dict-in-list-in-dict) must still be
    scrubbed. The shipped helper recurses through both dicts and
    lists, so any forbidden key — at any depth — is replaced
    with ``"[REDACTED]"``."""

    async def test_secret_at_depth_3(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={
                "outer": {
                    "middle": {
                        "password": "deep-secret",
                        "name": "alice",
                    }
                }
            },
        )
        assert entry.context["outer"]["middle"]["password"] == "[REDACTED]"
        assert entry.context["outer"]["middle"]["name"] == "alice"

    async def test_secret_in_list_at_depth_3(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={
                "events": [
                    {"type": "login", "token": "t1"},
                    {"type": "logout", "token": "t2"},
                ]
            },
        )
        assert entry.context["events"][0]["token"] == "[REDACTED]"
        assert entry.context["events"][1]["token"] == "[REDACTED]"
        assert entry.context["events"][0]["type"] == "login"
        assert entry.context["events"][1]["type"] == "logout"

    async def test_secret_in_dict_in_list_in_dict(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"headers": {"set-cookie": [{"name": "session", "value": "raw-token-value"}]}},
        )
        # ``value`` is not a sensitive key, so the helper does NOT
        # scrub it. Document the contract here: the structural
        # sweep below ensures callers do not pass raw tokens
        # under safe-named keys like ``value``.
        assert entry.context["headers"]["set-cookie"][0]["value"] == "raw-token-value"


# ---------------------------------------------------------------------------
# 5. Idempotence and edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("clean_audit_table")
class TestRedactionEdgeCases:
    """The redaction helper is called on the context dict once
    per ``AuditService.log`` call. Calling it on an
    already-redacted dict must be a no-op (the redacted
    sentinel is itself a string, not a sensitive value, so a
    second pass must not turn it into ``"[REDACTED][REDACTED]"``).
    """

    async def test_redaction_is_idempotent(self, db_session):
        from app.services.audit_service import _redact_value

        once = _redact_value({"password": "x", "ok": "y"})
        twice = _redact_value(once)
        assert once == twice, f"Redaction is not idempotent: {once!r} vs {twice!r}"
        assert twice["password"] == "[REDACTED]"
        assert twice["ok"] == "y"

    async def test_none_context_defaults_to_empty_dict(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context=None,
        )
        assert entry.context == {}

    async def test_empty_context_does_not_crash(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={},
        )
        assert entry.context == {}

    async def test_list_of_primitives_passes_through(self, db_session):
        entry = await AuditService.log(
            db_session,
            action=AuditActionType.QUERY_SUBMIT,
            context={"tags": ["alpha", "beta", "gamma"]},
        )
        assert entry.context["tags"] == ["alpha", "beta", "gamma"]


# ---------------------------------------------------------------------------
# 6. Structural forbidden-value sweep
# ---------------------------------------------------------------------------


class TestNoLiteralSecretsInEmitSiteContexts:
    """Every ``AuditService.log(...)`` call site in ``src/app/``
    that passes a literal ``context={...}`` dict must not embed
    a forbidden value pattern (PEM cert, SAML base64 prefix,
    raw SQL fragment, IP:port, driver name, stack-trace
    marker, raw secret string). The runtime helper is
    key-based, so this static sweep is the only guard against
    a future maintainer passing a secret under a safe-named
    key like ``notes`` or ``description``.

    Call sites that build the context dict dynamically
    (e.g. ``context=audit_context``) are NOT covered by this
    static sweep; the per-action-type runtime tests above
    cover those paths.
    """

    def test_no_forbidden_pattern_in_literal_contexts(self):
        literals = _collect_shipped_log_call_literals()
        assert literals, (
            "Static scan found no AuditService.log(...) call sites with "
            "literal context={...} dicts. Either the codebase has migrated "
            "to dynamic contexts (in which case the per-action-type runtime "
            "sweep is the only defense), or this scan is broken."
        )
        for path, ctx in literals:
            serialized = str(ctx)
            for pattern in _FORBIDDEN_VALUE_PATTERNS:
                assert pattern not in serialized, (
                    f"Forbidden pattern {pattern!r} found in literal context at {path}: {ctx!r}"
                )

    def test_every_literal_key_is_safe_or_known_sensitive(self):
        """Every key that appears in a literal ``context=`` dict at
        a shipped call site must be either (a) in the safe-keys
        list above, or (b) explicitly a known sensitive key
        (which the redaction helper scrubs). New keys in
        shipped call sites trigger this test so the reviewer
        can decide whether the key needs redaction or
        preservation."""
        literals = _collect_shipped_log_call_literals()
        safe: set[str] = set(_SAFE_KEYS)
        for path, ctx in literals:
            for key in ctx:
                if key in safe:
                    continue
                # If not in safe, it must contain a sensitive
                # substring (lowercased, stripped of ``_``/``-``).
                normalized = key.lower().replace("_", "").replace("-", "")
                is_sensitive = any(tok in normalized for tok in _FORBIDDEN_KEY_TOKENS)
                assert is_sensitive, (
                    f"Unknown context key {key!r} at {path}. Add it to "
                    f"_SAFE_KEYS in this test module if it is intentionally "
                    f"safe, or to _FORBIDDEN_KEY_TOKENS if it should be "
                    f"scrubbed by the redaction helper."
                )
