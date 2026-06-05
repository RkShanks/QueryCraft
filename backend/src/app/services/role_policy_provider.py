"""Role policy provider — production factory for the live /query/submit path.

T-712 follow-up: the QueryService constructor accepts an optional
``role_policy_provider`` callback. This module supplies the real
production callback used by the /query/submit, /query/regenerate,
/query/reject, and /query/accept factories in
``app/api/v1/query.py``.

The provider:

1. Loads the user's ``role_id`` from the ``users`` table. ``None`` →
   no policy applies (Phase 1-3 backward compat).
2. Loads the matching ``role_connection_policies`` row for
   ``(role_id, connection_id)``. Missing row → no policy applies.
3. Loads the user's ``user_identities`` row to populate the
   ``user_context`` dict with the values bound to ``{user.email}``,
   ``{user.subject_id}``, ``{user.role}`` placeholders by
   ``PolicyEnforcementService.bind_placeholders`` (T-702).

Sanitization: the provider never echoes the user value, role id,
or connection id in any error path. All failures resolve to
``None`` (no policy) so the request can fall through to the
un-authenticated flow.
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


def make_role_policy_provider(db: AsyncSession) -> RolePolicyProvider:
    """Build a real ``RolePolicyProvider`` bound to *db*.

    The returned closure looks up the user's role and the matching
    per-connection policy. Returns ``None`` (no policy) when:

    - the user has no ``role_id`` (Phase 1-3 backward compat), or
    - no ``role_connection_policies`` row exists for the connection, or
    - the ``user_identities`` lookup fails (placeholders will be
      empty strings; row filters using them will fail closed at
      ``bind_placeholders`` time — by design).

    The closure never raises. Any DB error is swallowed and surfaces
    as ``None`` so the request can fall through to the legacy flow
    rather than 500 on a transient DB hiccup. The audit log will
    capture the issue separately.
    """

    async def _provider(
        user_id: uuid.UUID,
        connection_id: uuid.UUID,
    ) -> RolePolicy | None:
        try:
            # 1. User and role.
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user is None or user.role_id is None:
                return None

            # 2. Per-connection policy.
            policy_result = await db.execute(
                select(RoleConnectionPolicy).where(
                    RoleConnectionPolicy.role_id == user.role_id,
                    RoleConnectionPolicy.connection_id == connection_id,
                )
            )
            policy_row = policy_result.scalar_one_or_none()
            if policy_row is None:
                return None

            # 3. User identity for placeholder binding.
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
            # Swallow DB errors. Provider failures must never 500 a
            # query; the request can fall through to the legacy
            # un-authenticated flow.
            return None

    return _provider
