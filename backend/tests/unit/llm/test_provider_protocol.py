"""T-075 — LLMProvider protocol contract tests."""

import inspect
from typing import Protocol

from app.llm.provider import LLMProvider


class ValidAdapter:
    """A class that correctly implements LLMProvider."""

    async def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        return "SELECT 1"


class MissingGenerateSql:
    """A class that does NOT implement generate_sql."""

    async def something_else(self, prompt: str) -> str:
        return "SELECT 1"


class WrongSignature:
    """A class with a wrong generate_sql signature."""

    def generate_sql(
        self,
        question: str,
        schema_context: str,
        negative_examples: list[str] | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:  # not async
        return "SELECT 1"


def test_protocol_is_runtime_checkable():
    """LLMProvider must be decorated with @runtime_checkable."""
    assert issubclass(LLMProvider, Protocol)
    # runtime_checkable allows isinstance checks
    assert hasattr(LLMProvider, "__instancecheck__")


def test_valid_adapter_satisfies_protocol():
    """A class with the correct generate_sql method passes isinstance."""
    adapter = ValidAdapter()
    assert isinstance(adapter, LLMProvider)


def test_missing_generate_sql_raises_type_error():
    """A class missing generate_sql should fail isinstance / structural check."""
    adapter = MissingGenerateSql()
    assert not isinstance(adapter, LLMProvider)


def test_sync_generate_sql_passes_isinstance():
    """runtime_checkable only checks name+callable, not async-ness."""
    adapter = WrongSignature()
    # Documenting Python behaviour: sync generate_sql still passes isinstance.
    assert isinstance(adapter, LLMProvider)


def test_generate_sql_signature():
    """The protocol declares async def generate_sql(self, question, schema_context, negative_examples, conversation_history) -> str."""
    method = getattr(LLMProvider, "generate_sql", None)
    assert method is not None
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    assert params == ["self", "question", "schema_context", "negative_examples", "conversation_history"]
    assert sig.parameters["question"].annotation is str
    assert sig.parameters["schema_context"].annotation is str
    assert sig.return_annotation is str
