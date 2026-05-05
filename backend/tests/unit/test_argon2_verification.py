"""Tests for Argon2id password verification (T-033).

Asserts verify_password returns True for correct password, False for wrong password,
and the hash uses Argon2id variant.
"""

from app.core.security import hash_password, verify_password


class TestArgon2Verification:
    """Verify Argon2id password hashing behavior."""

    def test_hash_uses_argon2id_variant(self):
        """hash_password must produce an Argon2id hash."""
        hashed = hash_password("correct_password")
        assert "$argon2id$" in hashed

    def test_verify_correct_password(self):
        """verify_password returns True for correct password."""
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_verify_wrong_password(self):
        """verify_password returns False for wrong password."""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_different_hash(self):
        """verify_password returns False against a hash from a different password."""
        hashed1 = hash_password("password_one")
        hashed2 = hash_password("password_two")
        assert verify_password("password_two", hashed1) is False
        assert verify_password("password_one", hashed2) is False
