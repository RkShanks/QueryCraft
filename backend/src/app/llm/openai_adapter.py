"""OpenAI LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class OpenAIAdapter:
    """Adapter for the OpenAI Chat Completions API."""

    def __init__(self, api_key: str, model: str = "gpt-4o", timeout_s: int = 30):
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
        )

    async def generate(self, prompt: str) -> str:
        """Send prompt to OpenAI Chat Completions and return generated SQL."""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = await self._client.post("/v1/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="openai", timeout_s=self._timeout_s) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="openai") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="openai")

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Build prompt and generate SQL."""
        from app.llm.prompt_builder import build_prompt

        prompt = build_prompt(question, schema_context, conversation_history)
        if negative_examples:
            prompt += "\nAvoid generating these SQL variants:\n" + "\n".join(f"- {ex}" for ex in negative_examples)
        return await self.generate(prompt)
