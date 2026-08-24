"""CHUNK-24 / IS-GAP-015 — deterministic non-Gemini provider matrix.

Covers provider selection/normalization, factory routing, missing or malformed
configuration, unsupported providers, invalid configuration shapes, no
unintended fallback, no secret retention, and query-composition compatibility
across Anthropic/OpenAI/Ollama adapters (P1-FR-009, P1-FR-026, P2-FR-047,
XP-014).
"""

import socket

import httpx
import pytest
import respx
from httpx import Response

from app.llm.anthropic_adapter import AnthropicAdapter
from app.llm.exceptions import LLMConfigurationError
from app.llm.factory import LLMProviderFactory, _api_key_fingerprint
from app.llm.gemini_adapter import GeminiAdapter
from app.llm.ollama_adapter import OllamaAdapter
from app.llm.openai_adapter import OpenAIAdapter
from app.llm.stub import StubLLM


class MatrixSettings:
    """Minimal settings stand-in mirroring the factory's read surface."""

    def __init__(
        self,
        provider="ollama",
        model="",
        anthropic_key="",
        openai_key="",
        gemini_key="",
        host="http://localhost:11434",
        timeout=30,
    ):
        self.LLM_PROVIDER = provider
        self.LLM_MODEL_NAME = model
        self.LLM_API_KEY_ANTHROPIC = anthropic_key
        self.LLM_API_KEY_OPENAI = openai_key
        self.LLM_API_KEY_GEMINI = gemini_key
        self.LLM_BASE_URL_OLLAMA = host
        self.QUERY_TIMEOUT_SECONDS = timeout


@pytest.fixture(autouse=True)
def _hermetic_provider_env(monkeypatch):
    """Keep ambient provider credentials out of the matrix results."""
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    LLMProviderFactory.clear_cache()
    yield
    LLMProviderFactory.clear_cache()


# ─── 1. Provider selection and normalization ───


def test_provider_name_uppercase_normalized_to_openai():
    adapter = LLMProviderFactory.from_config(MatrixSettings(provider="OpenAI", openai_key="sk-matrix-key"))
    assert isinstance(adapter, OpenAIAdapter)


def test_provider_name_mixed_case_normalized_to_anthropic():
    adapter = LLMProviderFactory.from_config(MatrixSettings(provider="Anthropic", anthropic_key="sk-matrix-key"))
    assert isinstance(adapter, AnthropicAdapter)


def test_empty_provider_defaults_to_ollama():
    adapter = LLMProviderFactory.from_config(MatrixSettings(provider=""))
    assert isinstance(adapter, OllamaAdapter)


def test_none_provider_defaults_to_ollama():
    settings = MatrixSettings()
    settings.LLM_PROVIDER = None
    adapter = LLMProviderFactory.from_config(settings)
    assert isinstance(adapter, OllamaAdapter)


# ─── 2. Factory routing ───


def test_stub_provider_bypasses_key_requirements():
    adapter = LLMProviderFactory.from_config(MatrixSettings(provider="stub"))
    assert isinstance(adapter, StubLLM)


def test_routing_anthropic_openai_gemini_ollama_types():
    assert isinstance(
        LLMProviderFactory.from_config(MatrixSettings(provider="anthropic", anthropic_key="k-anthropic")),
        AnthropicAdapter,
    )
    assert isinstance(
        LLMProviderFactory.from_config(MatrixSettings(provider="openai", openai_key="k-openai")),
        OpenAIAdapter,
    )
    assert isinstance(
        LLMProviderFactory.from_config(MatrixSettings(provider="gemini", gemini_key="k-gemini")),
        GeminiAdapter,
    )
    assert isinstance(LLMProviderFactory.from_config(MatrixSettings(provider="ollama")), OllamaAdapter)


# ─── 3. Missing or malformed configuration ───


@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_missing_api_key_raises_configuration_error(provider):
    with pytest.raises(LLMConfigurationError):
        LLMProviderFactory.from_config(MatrixSettings(provider=provider))


def test_blank_settings_key_does_not_shadow_env_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")
    adapter = LLMProviderFactory.from_config(MatrixSettings(provider="openai"))
    assert isinstance(adapter, OpenAIAdapter)


def test_env_fallback_used_when_settings_attr_absent(monkeypatch):
    """The factory reads os.environ when the settings object lacks the key attribute."""

    class BareSettings:
        LLM_PROVIDER = "openai"
        LLM_MODEL_NAME = ""
        QUERY_TIMEOUT_SECONDS = 30

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-fallback")
    adapter = LLMProviderFactory.from_config(BareSettings())
    assert isinstance(adapter, OpenAIAdapter)


# ─── 4. Unsupported provider names ───


@pytest.mark.parametrize("provider", ["unknown", "azure", "mistral", "OPENAI2"])
def test_unsupported_provider_raises_without_fallback(provider):
    with pytest.raises(LLMConfigurationError) as excinfo:
        LLMProviderFactory.from_config(MatrixSettings(provider=provider))
    assert "Unknown LLM provider" in str(excinfo.value)


# ─── 5. Invalid base URLs / models ───


async def test_unreachable_ollama_host_propagates_connect_error_raw():
    """Characterization: connect failures are not typed at the adapter boundary;
    they are sanitized by the service layer's generic provider-failure mapping."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        free_port = sock.getsockname()[1]
    adapter = OllamaAdapter(host=f"http://127.0.0.1:{free_port}", model="llama3.1", timeout_s=1)
    try:
        with pytest.raises(httpx.ConnectError):
            await adapter.generate("prompt")
    finally:
        await adapter.aclose()


def test_default_models_applied_when_model_name_empty():
    anthropic = LLMProviderFactory.from_config(MatrixSettings(provider="anthropic", anthropic_key="k1"))
    openai = LLMProviderFactory.from_config(MatrixSettings(provider="openai", openai_key="k2"))
    ollama = LLMProviderFactory.from_config(MatrixSettings(provider="ollama"))
    assert anthropic._model == "claude-3-5-sonnet-20241022"
    assert openai._model == "gpt-4o"
    assert ollama._model == "llama3.1"


# ─── 6. No unintended provider fallback ───


def test_no_silent_fallback_from_openai_to_other_providers():
    """Selecting openai without any usable key must fail closed, never fall back."""
    with pytest.raises(LLMConfigurationError):
        LLMProviderFactory.from_config(MatrixSettings(provider="openai"))


def test_no_silent_fallback_on_unknown_provider():
    with pytest.raises(LLMConfigurationError):
        LLMProviderFactory.from_config(MatrixSettings(provider="no-such-provider"))


# ─── 7. No secret retention ───


def test_fingerprint_hides_long_key_body():
    secret = "sk-verylongsecretvalue1234567890"
    fingerprint = _api_key_fingerprint(secret)
    assert secret not in fingerprint
    assert fingerprint == "sk-v..." + secret[-4:]


def test_missing_key_error_message_contains_no_secret_material():
    with pytest.raises(LLMConfigurationError) as excinfo:
        LLMProviderFactory.from_config(MatrixSettings(provider="openai", openai_key=""))
    assert "sk-" not in str(excinfo.value)
    assert excinfo.value.message_key == "error.llmUnavailable"


def test_cached_adapter_reused_per_config_and_isolated_across_keys():
    key_a1 = "sk-aaaaaaaaaaaaaaaaaa1"
    first = LLMProviderFactory.from_config(MatrixSettings(provider="openai", openai_key=key_a1, model="gpt-4o"))
    same = LLMProviderFactory.from_config(MatrixSettings(provider="openai", openai_key=key_a1, model="gpt-4o"))
    other_model = LLMProviderFactory.from_config(
        MatrixSettings(provider="openai", openai_key=key_a1, model="gpt-4o-mini")
    )
    other_key = LLMProviderFactory.from_config(
        MatrixSettings(provider="openai", openai_key="sk-bbbbbbbbbbbbbbbbbb2", model="gpt-4o")
    )
    assert first is same
    assert first is not other_model
    assert first is not other_key


# ─── 8. Query composition compatibility (P1-FR-009/026, P2-FR-047) ───


COMPOSITION_CASES = [
    ("anthropic", "https://api.anthropic.com/v1/messages"),
    ("openai", "https://api.openai.com/v1/chat/completions"),
    ("ollama", "http://localhost:11434/api/generate"),
]


def _composition_adapter(name: str):
    if name == "anthropic":
        return AnthropicAdapter(api_key="matrix-key", model="claude-model", timeout_s=30)
    if name == "openai":
        return OpenAIAdapter(api_key="matrix-key", model="gpt-model", timeout_s=30)
    return OllamaAdapter(host="http://localhost:11434", model="ollama-model", timeout_s=30)


def _success_body(name: str) -> dict:
    if name == "anthropic":
        return {"content": [{"type": "text", "text": "SELECT 1 AS id"}]}
    if name == "openai":
        return {"choices": [{"message": {"role": "assistant", "content": "SELECT 1 AS id"}}]}
    return {"response": "SELECT 1 AS id", "done": True}


@pytest.mark.parametrize(("name", "url"), COMPOSITION_CASES)
@respx.mock
async def test_generate_sql_composition_matches_shared_builder(name, url):
    """Each adapter composes the identical prompt structure from shared inputs."""
    adapter = _composition_adapter(name)
    route = respx.post(url).mock(return_value=Response(200, json=_success_body(name)))

    sql = await adapter.generate_sql(
        "matrix-question",
        "matrix-schema",
        negative_examples=["SELECT 0"],
        conversation_history=[{"question": "prior-q", "sql": "SELECT prior"}],
        target_dialect="mysql",
        timeout=5,
    )
    assert sql == "SELECT 1 AS id"

    body = route.calls.last.request.content.decode()
    assert "Question: matrix-question" in body
    assert "matrix-schema" in body
    assert "TARGET_DIALECT: mysql" in body
    assert "Conversation history:" in body
    assert "Avoid generating these SQL variants:" in body
    assert "- SELECT 0" in body
    await adapter.aclose()


@pytest.mark.parametrize(("name", "url"), COMPOSITION_CASES)
@respx.mock
async def test_generate_sql_minimal_composition_has_no_optional_blocks(name, url):
    """Without history/negatives/dialect, optional blocks are absent for every provider."""
    adapter = _composition_adapter(name)
    route = respx.post(url).mock(return_value=Response(200, json=_success_body(name)))

    sql = await adapter.generate_sql("matrix-question", "matrix-schema", timeout=5)
    assert sql == "SELECT 1 AS id"

    body = route.calls.last.request.content.decode()
    assert "TARGET_DIALECT" not in body
    assert "Conversation history:" not in body
    assert "Avoid generating these SQL variants:" not in body
    await adapter.aclose()
