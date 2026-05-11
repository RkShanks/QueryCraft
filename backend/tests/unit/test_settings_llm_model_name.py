"""F-008: LLM_MODEL_NAME bound from environment variable."""

from app.core.config import get_settings


def test_llm_model_name_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_NAME", "custom-model")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.LLM_MODEL_NAME == "custom-model"
