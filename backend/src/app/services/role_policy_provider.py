"""Role policy provider — production factory for the live /query path.

T-712 follow-up: the ``QueryService`` constructor accepts an optional
``role_policy_provider`` callback. This module supplies the real
production callback used by the ``/query/submit``,
``/query/regenerate``, ``/query/reject``, and ``/query/accept``
factories in ``app/api/v1/query.py``.

The provider:

1. Loads the user's ``role_id`` from the ``users`` table.
2. Loads the matching ``role_connection_policies`` row for
   ``(role_id, connection_id)``.
3. Loads the user's ``user_identities`` row to populate the
   ``user_context`` dict with the values bound to ``{user.email}``,
   ``{user.subject_id}``, ``{user.role}`` placeholders by
   ``PolicyEnforcementService.bind_placeholders`` (T-702).

Fail-closed contract (FR-128 / FR-130 / FR-131 / FR-132,
api-contracts.md lines 351-356):

- User has no ``role_id`` (Phase 1-3 legacy admin): return ``None``.
  The query service treats ``None`` as "no policy applies" and the
  un-authenticated flow runs unchanged. This is the only path that
  can return ``None`` for a user that exists.
- User has a ``role_id`` but no ``role_connection_policies`` row for
  the connection: return a deny-all ``RolePolicy`` (``allowed_tables=[]``,
  ``row_filters=[]``, ``column_masks=[]``). The query service's
  pre-LLM check will surface a sanitized ``EvaluatorRejection`` with
  i18n key ``error.queryBlockedPolicy`` before the LLM is ever
  called.
- User has a ``role_id`` but the policy lookup raises a DB error:
  return a deny-all ``RolePolicy``. Provider errors never 500 a
  query; they fail-closed with a sanitized block.
- User has a ``role_id`` and a policy row but no ``user_identities``
  row: return a ``RolePolicy`` with empty-string
  ``email``/``subject_id`` in ``user_context``. Row filters that
  reference these placeholders will fail closed at
  ``bind_placeholders`` time (``placeholder_binding_failed``) — by
  design. Empty ``allowed_tables`` (deny-all) is also fail-closed.

Sanitization: the provider never echoes the user value, role id,
connection id, table name, column name, SQL, DB error, host/port,
username, driver name, stack trace, credential, token, cert, or
SAML/OIDC XML in any return value or error path.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.role_connection_policy import RoleConnectionPolicy
from app.db.models.user import User
from app.db.models.user_identity import UserIdentity
from app.services.query_service import RolePolicy

# Re-exported type alias so callers don't need to import query_service
# directly when wiring the provider.
RolePolicyProvider = Callable[[uuid.UUID, uuid.UUID], Awaitable[RolePolicy | None]]


def _deny_all_policy(user_id: uuid.UUID) -> RolePolicy:
    """Build a deny-all ``RolePolicy`` for a role-bearing user.

    The query service's pre-LLM check (line 366 of query_service.py)
    sees ``allowed_tables=[]`` and returns a sanitized
    ``EvaluatorRejection(error.queryBlockedPolicy)`` BEFORE the LLM
    is invoked. The LLM never sees the schema. No user value,
    table, column, role id, connection id, DB error, host/port,
    credential, token, cert, or SAML/OIDC XML is included in the
    returned policy.
    """
    return RolePolicy(
        user_id=user_id,
        role_id=uuid.UUID(int=0),
        connection_id=uuid.UUID(int=0),
        allowed_tables=[],
        row_filters=[],
        column_masks=[],
        user_context={"email": "", "subject_id": "", "role": ""},
    )


def make_role_policy_provider(db: AsyncSession) -> RolePolicyProvider:
    """Build a real ``RolePolicyProvider`` bound to *db*.

    Returns ``None`` ONLY when the user has no ``role_id`` (Phase
    1-3 backward compat path). For all other role-bearing users
    the provider returns a ``RolePolicy`` — either the resolved
    policy row or a deny-all — so the query service can enforce
    fail-closed semantics.

    The closure never raises. Any DB error in the policy lookup
    resolves to a deny-all ``RolePolicy`` for role-bearing users
    (provider failures never 500 a query; they fail closed).
    """

    async def _provider(
        user_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> RolePolicy | None:
        try:
            # 1. User and role. A user with no role_id is the
            #    Phase 1-3 legacy path; no policy applies.
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user is None or user.role_id is None:
                return None

            # 2. Per-connection policy. If no row exists for this
            #    (role_id, connection_id), the role-bearing user
            #    must fail closed — not fall through to the
            #    un-authenticated flow. The query service's
            #    pre-LLM check sees ``allowed_tables=[]`` and
            #    blocks with ``error.queryBlockedPolicy``.
            policy_result = await db.execute(
                select(RoleConnectionPolicy).where(
                    RoleConnectionPolicy.role_id == user.role_id,
                    RoleConnectionPolicy.connection_id == connection_id,
                )
            )
            policy_row = policy_result.scalar_one_or_none()
            if policy_row is None:
                return _deny_all_policy(user_id)

            # 3. User identity for placeholder binding. A
            #    missing row is fine — empty strings fail
            #    closed at bind_placeholders time.
            identity_result = await db.execute(select(UserIdentity).where(UserIdentity.user_id == user_id).limit(1))
            identity = identity_result.scalar_one_or_none()

            user_context: dict[str, Any] = {
                "email": (identity.email if identity and identity.email else ""),
                "subject_id": (identity.subject_id if identity else ""),
                "role": user.role,
            }

            return RolePolicy(
                user_id=user_id,
                role_id=user.role_id,
                connection_id=connection_id,
                allowed_tables=list(policy_row.allowed_tables or []),
                row_filters=list(policy_row.row_filters or []),
                column_masks=list(policy_row.column_masks or []),
                user_context=user_context,
            )
        except Exception:
            # DB error while resolving the policy for a
            # role-bearing user — fail closed with a deny-all
            # policy. Provider failures never 500 a query; they
            # never grant broader access than the user has.
            return _deny_all_policy(user_id)

    return _provider
