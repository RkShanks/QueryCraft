"""LLMProvider protocol definition."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM adapters.

    All adapters must implement ``generate`` which takes a normalised prompt
    string and returns the generated SQL string.
    """

    async def generate(self, prompt: str) -> str:
        """Generate SQL from a normalised prompt.

        Raises:
            LLMUnavailable: on 5xx or 429 responses from the provider.
            LLMTimeout: when the request exceeds the adapter timeout.
        """
        ...
