"""Tests for SsoProvider ORM model (T-605)."""

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.models.enums import SsoProtocol
from app.db.models.sso_provider import SsoProvider


class TestSsoProviderModel:
    """SsoProvider ORM model metadata and instantiation."""

    def test_table_name(self):
        assert SsoProvider.__tablename__ == "sso_providers"

    def test_can_instantiate_oidc(self):
        sp = SsoProvider(
            id=uuid4(),
            protocol=SsoProtocol.OIDC,
            display_name="Corp OIDC",
            issuer_url="https://idp.example.com",
            client_id="client-id",
            encrypted_client_secret="enc-secret",
            scopes="openid email profile groups",
            redirect_uri="https://app.example.com/callback",
            group_claim_name="groups",
        )
        assert sp.display_name == "Corp OIDC"
        assert sp.protocol == SsoProtocol.OIDC

    def test_can_instantiate_saml(self):
        sp = SsoProvider(
            id=uuid4(),
            protocol=SsoProtocol.SAML,
            display_name="Corp SAML",
            saml_entity_id="sp-entity-id",
            encrypted_saml_metadata_xml="<xml/>",
            encrypted_saml_certificate="cert",
            group_claim_name="groups",
        )
        assert sp.protocol == SsoProtocol.SAML

    def test_id_column_type(self):
        assert isinstance(SsoProvider.__table__.c.id.type, PG_UUID)

    def test_protocol_unique(self):
        assert SsoProvider.__table__.c.protocol.unique is True

    def test_is_active_default(self):
        col = SsoProvider.__table__.c.is_active
        assert col.server_default is not None or col.default is not None
