"""T-251: Operator-effort assertion for SC-008.

SC-008 requires that switching the LLM provider via configuration and restarting
the platform takes under 5 minutes of operator effort. This test captures the
*technical* portion of that effort — factory re-init + first request resolution —
and asserts it completes in well under 30 seconds (a proxy for the 5-minute SLA).
"""

import time

import pytest
import respx
from httpx import Response

from app.llm.factory import LLMProviderFactory


class TestOperatorEffort:
    """SC-008: provider switch and first request resolve in < 30 seconds."""

    @pytest.mark.asyncio
    async def test_provider_switch_under_30_seconds(self, monkeypatch):
        """Factory re-init + first request against new provider < 30s."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_API_KEY_OPENAI", "fake-openai-key")
        from app.core.config import get_settings

        get_settings.cache_clear()

        with respx.mock:
            route = respx.post("https://api.openai.com/v1/chat/completions").mock(
                return_value=Response(
                    200,
                    json={"choices": [{"message": {"content": "SELECT 1 AS id"}}]},
                )
            )

            t0 = time.monotonic()
            settings = get_settings()
            provider = LLMProviderFactory.from_config(settings)

            # Assert no code change is required — factory accepts the new config
            assert provider is not None

            sql = await provider.generate_sql("What is 1+1?", "schema context")
            t1 = time.monotonic()

            assert sql == "SELECT 1 AS id"
            assert route.called
            assert (t1 - t0) < 30.0
