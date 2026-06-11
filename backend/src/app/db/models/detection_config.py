"""Detection threshold ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DetectionThresholdConfig(Base):
    """Singleton hostile-input detection threshold configuration."""

    __tablename__ = "detection_threshold_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    block_confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.8"))
    flag_confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.5"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
