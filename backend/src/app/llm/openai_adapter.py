"""OpenAI LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class OpenAIAdapter:
    """Adapter for the OpenAI Chat Completions API."""

    def __init__(self, api_key: str, *, timeout_s: int, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
        )

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        """Send prompt to OpenAI Chat Completions and return generated SQL."""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            request_timeout = timeout if timeout is not None else self._timeout_s
            response = await self._client.post("/v1/chat/completions", json=payload, timeout=request_timeout)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="openai", timeout_s=request_timeout) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="openai") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="openai")

        try:
            response.raise_for_status()
            data = response.json()
            sql = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailable(provider="openai", message="Malformed response from provider") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="openai") from exc

        if not isinstance(sql, str):
            raise LLMUnavailable(provider="openai", message="Malformed response from provider")
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
