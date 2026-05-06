"""T-155 regression test — SourceDBConnector.decrypt() signature.

connector.py calls ``decrypt(raw_password)`` with a single argument, but
``encryption.decrypt()`` requires two: ``(ciphertext_b64, key_b64)``.
The ``# type: ignore[call-arg]`` comment masks the mismatch.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.source_db.connector import SourceDBConnector


@pytest.mark.asyncio
async def test_decrypt_called_with_key():
    """init_pool must call decrypt with both ciphertext and key."""
    connector = SourceDBConnector()
    with patch("app.source_db.connector.decrypt") as mock_decrypt:
        mock_decrypt.return_value = "decrypted_pwd"
        with patch("app.source_db.connector.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            await connector.init_pool()

    mock_decrypt.assert_called_once()
    args, kwargs = mock_decrypt.call_args
    assert len(args) == 2, f"decrypt() called with {len(args)} args, expected 2"
    assert args[0] == "pagila_dev_pwd"  # from test env
    assert args[1] != ""  # PLATFORM_ENCRYPTION_KEY must be passed
