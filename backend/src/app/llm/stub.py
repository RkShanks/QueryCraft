"""Stub LLM provider for US-1 testing."""


class StubLLM:
    """Always returns a safe SELECT statement."""

    async def generate_sql(self, question: str, schema_context: str, negative_examples: list[str] | None = None) -> str:
        return "SELECT 1 AS id"
