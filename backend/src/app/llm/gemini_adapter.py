"""Gemini LLM adapter implementing LLMProvider."""

import httpx

from app.llm.exceptions import LLMTimeout, LLMUnavailable


class GeminiAdapter:
    """Adapter for the Google Gemini generateContent API."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro", timeout_s: int = 30):
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._client = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com",
            timeout=timeout_s,
            headers={"x-goog-api-key": api_key},
        )

    async def generate(self, prompt: str) -> str:
        """Send prompt to Gemini API and return generated SQL."""
        url = f"/v1beta/models/{self._model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        try:
            response = await self._client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeout(provider="gemini", timeout_s=self._timeout_s) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailable(provider="gemini") from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise LLMUnavailable(provider="gemini")

        try:
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailable(provider="gemini", message="Malformed response from provider") from exc
        except httpx.HTTPStatusError as exc:
            msg = "Provider returned an error"
            try:
                err_data = exc.response.json()
                msg = err_data.get("error", {}).get("message", msg)
            except Exception:
                pass
            raise LLMUnavailable(provider="gemini", message=msg) from exc

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
