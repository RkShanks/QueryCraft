"""Tests for AES-256-GCM encryption/decryption (T-008).

These tests must FAIL before T-009 implementation exists.
"""

import base64

import pytest


class TestAES256GCMEncryption:
    """Test suite for core/encryption.py encrypt/decrypt functions."""

    @pytest.fixture
    def encryption_key(self) -> str:
        """A valid base64-encoded 32-byte key."""
        raw_key = b"0123456789abcdef0123456789abcdef"  # exactly 32 bytes
        return base64.b64encode(raw_key).decode()

    @pytest.fixture
    def wrong_key(self) -> str:
        """A different valid base64-encoded 32-byte key."""
        raw_key = b"fedcba9876543210fedcba9876543210"
        return base64.b64encode(raw_key).decode()

    def test_round_trip(self, encryption_key: str) -> None:
        """Encrypting then decrypting returns the original plaintext."""
        from app.core.encryption import decrypt, encrypt

        plaintext = "my-secret-database-password"
        ciphertext = encrypt(plaintext, encryption_key)
        result = decrypt(ciphertext, encryption_key)
        assert result == plaintext

    def test_ciphertext_differs_from_plaintext(self, encryption_key: str) -> None:
        """Ciphertext must not equal the plaintext."""
        from app.core.encryption import encrypt

        plaintext = "my-secret-database-password"
        ciphertext = encrypt(plaintext, encryption_key)
        assert ciphertext != plaintext

    def test_wrong_key_raises_error(self, encryption_key: str, wrong_key: str) -> None:
        """Decrypting with a different key must raise an error."""
        from app.core.encryption import decrypt, encrypt

        plaintext = "my-secret-database-password"
        ciphertext = encrypt(plaintext, encryption_key)
        with pytest.raises(Exception):
            decrypt(ciphertext, wrong_key)

    def test_tampered_ciphertext_raises_error(self, encryption_key: str) -> None:
        """Tampered ciphertext must raise an integrity error."""
        from app.core.encryption import decrypt, encrypt

        plaintext = "my-secret-database-password"
        ciphertext = encrypt(plaintext, encryption_key)
        # Tamper with the ciphertext by modifying a character
        raw = base64.b64decode(ciphertext)
        tampered = bytes([raw[0] ^ 0xFF]) + raw[1:]
        tampered_b64 = base64.b64encode(tampered).decode()
        with pytest.raises(Exception):
            decrypt(tampered_b64, encryption_key)

    def test_empty_plaintext_round_trip(self, encryption_key: str) -> None:
        """Empty string should round-trip successfully."""
        from app.core.encryption import decrypt, encrypt

        ciphertext = encrypt("", encryption_key)
        result = decrypt(ciphertext, encryption_key)
        assert result == ""
