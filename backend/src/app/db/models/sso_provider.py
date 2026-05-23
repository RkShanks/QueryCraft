"""SsoProvider ORM model (T-606)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SsoProvider(Base):
    """SSO identity provider configuration."""

    __tablename__ = "sso_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    protocol: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    issuer_url: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_client_secret: Mapped[str | None] = mapped_column(String, nullable=True)
    scopes: Mapped[str | None] = mapped_column(
        String, nullable=True, server_default=text("'openid email profile groups'")
    )
    redirect_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    group_claim_name: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'groups'")
    )
    saml_entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    saml_metadata_url: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_saml_metadata_xml: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_saml_certificate: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
