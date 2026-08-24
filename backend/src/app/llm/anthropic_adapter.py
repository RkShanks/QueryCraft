"""Anthropic LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class AnthropicAdapter:
    """Adapter for the Anthropic Messages API."""

    def __init__(self, api_key: str, *, timeout_s: int, model: str = "claude-3-5-sonnet-20241022"):
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=timeout_s,
        )

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        """Send prompt to Anthropic Messages API and return generated SQL."""
        payload = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            request_timeout = timeout if timeout is not None else self._timeout_s
            response = await self._client.post("/v1/messages", json=payload, timeout=request_timeout)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="anthropic", timeout_s=request_timeout) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="anthropic") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="anthropic")

        try:
            response.raise_for_status()
            data = response.json()
            sql = data["content"][0]["text"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailable(provider="anthropic", message="Malformed response from provider") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="anthropic") from exc

        if not isinstance(sql, str):
            raise LLMUnavailable(provider="anthropic", message="Malformed response from provider")
        return sql

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
        conversation_history: list[dict] | None = None,
        target_dialect: str | None = None,
        timeout: float | None = None,
    ) -> str:
        """Build prompt and generate SQL."""
        from app.llm.prompt_builder import build_prompt

        prompt = build_prompt(question, schema_context, conversation_history, target_dialect=target_dialect)
        if negative_examples:
            prompt += "\nAvoid generating these SQL variants:\n" + "\n".join(f"- {ex}" for ex in negative_examples)
        return await self.generate(prompt, timeout=timeout)
