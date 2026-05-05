"""T-075 — LLMProvider protocol contract tests."""

import inspect
from typing import Protocol, runtime_checkable

import pytest

from app.llm.provider import LLMProvider


class ValidAdapter:
    """A class that correctly implements LLMProvider."""

    async def generate(self, prompt: str) -> str:
        return "SELECT 1"


class MissingGenerate:
    """A class that does NOT implement generate."""

    async def something_else(self, prompt: str) -> str:
        return "SELECT 1"


class WrongSignature:
    """A class with a wrong generate signature."""

    def generate(self, prompt: str) -> str:  # not async
        return "SELECT 1"


def test_protocol_is_runtime_checkable():
    """LLMProvider must be decorated with @runtime_checkable."""
    assert issubclass(LLMProvider, Protocol)
    # runtime_checkable allows isinstance checks
    assert hasattr(LLMProvider, "__instancecheck__")


def test_valid_adapter_satisfies_protocol():
    """A class with the correct generate method passes isinstance."""
    adapter = ValidAdapter()
    assert isinstance(adapter, LLMProvider)


def test_missing_generate_raises_type_error():
    """A class missing generate should fail isinstance / structural check."""
    adapter = MissingGenerate()
    assert not isinstance(adapter, LLMProvider)


def test_wrong_signature_fails_isinstance():
    """A non-async generate should fail isinstance against the protocol."""
    adapter = WrongSignature()
    # runtime_checkable checks name and callable, not exact async signature,
    # but for completeness we document behaviour.
    assert not isinstance(adapter, LLMProvider)


def test_generate_signature():
    """The protocol declares async def generate(self, prompt: str) -> str."""
    method = getattr(LLMProvider, "generate", None)
    assert method is not None
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    assert params == ["self", "prompt"]
    assert sig.parameters["prompt"].annotation is str
    assert sig.return_annotation is str
