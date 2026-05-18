"""Tests for CredentialProvider protocol and FernetCredentialProvider (T-405, SC-029)."""

import base64
import os

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.credential_provider import CredentialProvider, FernetCredentialProvider, ConfigurationError


class TestFernetCredentialProvider:
    """Verify FernetCredentialProvider encrypts/decrypts correctly."""

    @pytest.fixture
    def valid_key(self) -> str:
        return Fernet.generate_key().decode()

    @pytest.fixture
    def provider(self, valid_key: str) -> FernetCredentialProvider:
        return FernetCredentialProvider(valid_key)

    def test_encrypt_returns_non_empty_string(self, provider: FernetCredentialProvider):
        result = provider.encrypt("secret_password")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_decrypt_round_trip(self, provider: FernetCredentialProvider):
        plaintext = "my_secret_password"
        encrypted = provider.encrypt(plaintext)
        decrypted = provider.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext_each_time(self, provider: FernetCredentialProvider):
        encrypted1 = provider.encrypt("same_password")
        encrypted2 = provider.encrypt("same_password")
        assert encrypted1 != encrypted2  # Fernet includes timestamp/nonce

    def test_decrypt_wrong_key_raises(self, valid_key: str):
        provider1 = FernetCredentialProvider(valid_key)
        other_key = Fernet.generate_key().decode()
        provider2 = FernetCredentialProvider(other_key)

        encrypted = provider1.encrypt("secret")
        with pytest.raises(InvalidToken):
            provider2.decrypt(encrypted)

    def test_decrypt_invalid_token_raises(self, provider: FernetCredentialProvider):
        with pytest.raises(InvalidToken):
            provider.decrypt("not-a-valid-token")

    def test_encrypt_empty_string(self, provider: FernetCredentialProvider):
        result = provider.encrypt("")
        assert provider.decrypt(result) == ""

    def test_encrypt_unicode(self, provider: FernetCredentialProvider):
        plaintext = "password-with-unicode-\u00e9\u00e0\u00fc"
        encrypted = provider.encrypt(plaintext)
        assert provider.decrypt(encrypted) == plaintext


class TestFernetCredentialProviderValidation:
    """Verify key validation on construction."""

    def test_invalid_key_format_raises(self):
        with pytest.raises(ConfigurationError):
            FernetCredentialProvider("not-a-valid-fernet-key")

    def test_empty_key_raises(self):
        with pytest.raises(ConfigurationError):
            FernetCredentialProvider("")

    def test_valid_key_from_fernet_generate(self):
        key = Fernet.generate_key().decode()
        provider = FernetCredentialProvider(key)
        assert provider is not None


class TestCredentialProviderProtocol:
    """Verify FernetCredentialProvider implements CredentialProvider protocol."""

    def test_is_instance_of_protocol(self):
        key = Fernet.generate_key().decode()
        provider = FernetCredentialProvider(key)
        # Protocol is structural; verify methods exist
        assert hasattr(provider, "encrypt")
        assert hasattr(provider, "decrypt")
        assert callable(provider.encrypt)
        assert callable(provider.decrypt)
