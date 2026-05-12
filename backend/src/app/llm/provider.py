"""LLMProvider protocol definition."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM adapters.

    All adapters must implement ``generate`` which takes a normalised prompt
    string and returns the generated SQL string.
    """

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate SQL from a user question and schema context.

        Args:
            question: The user's natural-language question.
            schema_context: YAML/plain-text schema description.
            negative_examples: Previously rejected SQL variants to avoid.
            conversation_history: Optional list of prior Q&A dicts for context.

        Returns:
            The generated SQL string.

        Raises:
            LLMUnavailable: on 5xx or 429 responses from the provider.
            LLMTimeout: when the request exceeds the adapter timeout.
        """
        ...
