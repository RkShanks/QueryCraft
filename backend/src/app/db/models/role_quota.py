"""Role quota ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.role import Role


class RoleQuota(Base):
    """Per-role quota configuration."""

    __tablename__ = "role_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    daily_query_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_execution_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daily_export_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    role: Mapped[Role] = relationship("Role", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "daily_query_limit IS NULL OR daily_query_limit >= 0",
            name="ck_role_quotas_daily_query_limit_nonnegative",
        ),
        CheckConstraint(
            "daily_execution_limit IS NULL OR daily_execution_limit >= 0",
            name="ck_role_quotas_daily_execution_limit_nonnegative",
        ),
        CheckConstraint(
            "daily_export_limit IS NULL OR daily_export_limit >= 0",
            name="ck_role_quotas_daily_export_limit_nonnegative",
        ),
    )
