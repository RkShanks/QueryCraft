"""Ollama LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class OllamaAdapter:
    """Adapter for a local Ollama instance."""

    def __init__(self, host: str, *, timeout_s: int, model: str = "llama3.1"):
        self._host = host.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url=self._host,
            timeout=timeout_s,
        )

    async def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        """Send prompt to Ollama /api/generate and return generated SQL."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            request_timeout = timeout if timeout is not None else self._timeout_s
            response = await self._client.post("/api/generate", json=payload, timeout=request_timeout)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="ollama", timeout_s=request_timeout) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="ollama") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="ollama")

        try:
            response.raise_for_status()
            data = response.json()
            sql = data["response"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMUnavailable(provider="ollama", message="Malformed response from provider") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="ollama") from exc

        if not isinstance(sql, str):
            raise LLMUnavailable(provider="ollama", message="Malformed response from provider")
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
