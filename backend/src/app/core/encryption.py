"""AES-256-GCM encryption/decryption for source-DB credentials (R-008)."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_IV_LENGTH = 12  # 96-bit nonce recommended for AES-GCM


def encrypt(plaintext: str, key_b64: str) -> str:
    """Encrypt plaintext using AES-256-GCM.

    Args:
        plaintext: The string to encrypt.
        key_b64: Base64-encoded 32-byte key.

    Returns:
        Base64-encoded string of ``iv || ciphertext || tag``.
    """
    key = base64.b64decode(key_b64)
    iv = os.urandom(_IV_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    # ciphertext includes the 16-byte tag appended by AESGCM
    return base64.b64encode(iv + ciphertext).decode("utf-8")


def decrypt(ciphertext_b64: str, key_b64: str) -> str:
    """Decrypt an AES-256-GCM ciphertext.

    Args:
        ciphertext_b64: Base64-encoded ``iv || ciphertext || tag``.
        key_b64: Base64-encoded 32-byte key.

    Returns:
        The original plaintext string.

    Raises:
        cryptography.exceptions.InvalidTag: If key is wrong or data is tampered.
    """
    key = base64.b64decode(key_b64)
    raw = base64.b64decode(ciphertext_b64)
    iv = raw[:_IV_LENGTH]
    ciphertext = raw[_IV_LENGTH:]
    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)
    return plaintext_bytes.decode("utf-8")
