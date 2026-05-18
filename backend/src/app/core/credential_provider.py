"""Credential provider abstraction for database password encryption (ADR-9).

Uses Fernet symmetric encryption via the cryptography library.
The DB_CREDENTIAL_KEY environment variable holds the base64-encoded Fernet key.
"""

from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from app.core.exceptions import ConfigurationError


class CredentialProvider(Protocol):
    """Protocol for credential encryption/decryption providers.

    Implementations may use Fernet, Vault, KMS, etc.
    """

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext password.

        Returns:
            Encrypted string suitable for storage.
        """
        ...

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a stored ciphertext back to plaintext.

        Args:
            ciphertext: Previously encrypted password string.

        Returns:
            Original plaintext password.

        Raises:
            InvalidToken: If the ciphertext is invalid or key is wrong.
        """
        ...


class FernetCredentialProvider:
    """Fernet-based credential encryption provider (ADR-9).

    Uses a single symmetric key from DB_CREDENTIAL_KEY env var.
    """

    def __init__(self, key: str) -> None:
        """Initialize with a base64-encoded Fernet key.

        Args:
            key: Base64-encoded 32-byte Fernet key.

        Raises:
            ConfigurationError: If the key is not a valid Fernet key.
        """
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise ConfigurationError(
                error="credential_config",
                message_key="error.credential_config",
                detail=f"Invalid DB_CREDENTIAL_KEY: {e}",
            )

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext password using Fernet."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a Fernet ciphertext back to plaintext."""
        return self._fernet.decrypt(ciphertext.encode()).decode()


# Module-level singleton, initialized at app startup
_provider: CredentialProvider | None = None


def get_credential_provider() -> CredentialProvider:
    """Return the global credential provider singleton.

    Raises:
        ConfigurationError: If the provider has not been initialized.
    """
    if _provider is None:
        raise ConfigurationError(
            error="credential_config",
            message_key="error.credential_config",
            detail="Credential provider not initialized. Set DB_CREDENTIAL_KEY.",
        )
    return _provider


def init_credential_provider(key: str | None) -> None:
    """Initialize the global credential provider singleton.

    Args:
        key: Base64-encoded Fernet key from DB_CREDENTIAL_KEY env var.

    Raises:
        ConfigurationError: If key is missing or invalid.
    """
    global _provider
    if not key:
        raise ConfigurationError(
            error="credential_config",
            message_key="error.credential_config",
            detail="DB_CREDENTIAL_KEY is not set.",
        )
    _provider = FernetCredentialProvider(key)
