"""Anthropic LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class AnthropicAdapter:
    """Adapter for the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", timeout_s: int = 30):
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=timeout_s,
        )

    async def generate(self, prompt: str) -> str:
        """Send prompt to Anthropic Messages API and return generated SQL."""
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = await self._client.post("/v1/messages", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="anthropic", timeout_s=self._timeout_s) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="anthropic") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="anthropic")

        response.raise_for_status()
        data = response.json()
        return data["content"][0]["text"]

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
    ) -> str:
        """Build prompt and generate SQL."""
        from app.llm.prompt_builder import build_prompt

        prompt = build_prompt(question, schema_context)
        if negative_examples:
            prompt += "\nAvoid generating these SQL variants:\n" + "\n".join(
                f"- {ex}" for ex in negative_examples
            )
        return await self.generate(prompt)
