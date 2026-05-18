"""Tests for DB_CREDENTIAL_KEY settings and startup guard (T-406, FR-062, ADR-9)."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.credential_provider import init_credential_provider
from app.core.exceptions import ConfigurationError


class TestSettingsDBCredentialKey:
    """Verify DB_CREDENTIAL_KEY is in Settings."""

    def test_settings_has_db_credential_key(self):
        settings = Settings.model_construct(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            PLATFORM_ENCRYPTION_KEY="dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyExMjM=",
            DB_CREDENTIAL_KEY=Fernet.generate_key().decode(),
        )
        assert hasattr(settings, "DB_CREDENTIAL_KEY")

    def test_db_credential_key_default_empty(self):
        settings = Settings.model_construct(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
            PLATFORM_ENCRYPTION_KEY="dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyExMjM=",
        )
        assert settings.DB_CREDENTIAL_KEY == ""


class TestInitCredentialProvider:
    """Verify init_credential_provider behavior."""

    def test_init_with_valid_key(self):
        key = Fernet.generate_key().decode()
        init_credential_provider(key)
        # Provider should be initialized without error

    def test_init_with_empty_key_raises(self):
        with pytest.raises(ConfigurationError):
            init_credential_provider("")

    def test_init_with_none_raises(self):
        with pytest.raises(ConfigurationError):
            init_credential_provider(None)

    def test_init_with_invalid_key_raises(self):
        with pytest.raises(ConfigurationError):
            init_credential_provider("not-a-valid-key")
