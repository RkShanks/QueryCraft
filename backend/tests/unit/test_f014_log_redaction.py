"""F-014 — Gemini API key leaks into INFO-level HTTP logs.

GeminiAdapter passes api_key as a URL query parameter (?key=...).
httpx's default INFO logger includes the full URL, leaking the key
into application logs.

Reproduction test (EXPECTED TO FAIL on current main — RED).
"""

import contextlib
import logging

import pytest
import respx
from httpx import Response

from app.llm.gemini_adapter import GeminiAdapter


@pytest.mark.integration
@pytest.mark.asyncio
async def test_f014_gemini_url_redacted_in_logs(caplog):
    """F-014: Gemini API key must NOT appear in any log record."""
    secret = "AIzaSyTESTSECRETPATTERN"
    adapter = GeminiAdapter(api_key=secret, model="gemini-1.5-pro")

    # Ensure httpx INFO logs are captured
    caplog.set_level(logging.INFO, logger="httpx")

    with respx.mock:
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
        ).mock(
            return_value=Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "SELECT 1"}],
                                "role": "model",
                            },
                            "finishReason": "STOP",
                            "index": 0,
                        }
                    ],
                },
            )
        )

        with contextlib.suppress(Exception):
            await adapter.generate("hi")

    leaked = []
    for r in caplog.records:
        msg = r.getMessage()
        if secret in msg or secret in str(r.args):
            leaked.append(r)

    assert leaked == [], f"F-014: API key leaked in {len(leaked)} log records"
