"""Ollama LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class OllamaAdapter:
    """Adapter for a local Ollama instance."""

    def __init__(self, host: str, model: str = "llama3.1", timeout_s: int = 30):
        self._host = host.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=timeout_s,
        )

    async def generate(self, prompt: str) -> str:
        """Send prompt to Ollama /api/generate and return generated SQL."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            response = await self._client.post("/api/generate", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="ollama", timeout_s=self._timeout_s) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="ollama") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="ollama")

        response.raise_for_status()
        data = response.json()
        return data["response"]

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
    ) -> str:
        """Build prompt and generate SQL."""
        from app.llm.prompt_builder import build_prompt

        prompt = build_prompt(question, schema_context, conversation_history, target_dialect=target_dialect)
        if negative_examples:
            prompt += "\nAvoid generating these SQL variants:\n" + "\n".join(f"- {ex}" for ex in negative_examples)
        return await self.generate(prompt)
