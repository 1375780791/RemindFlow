import pytest

from app.core.config import Settings
from app.services.llm import LLMConfigError, get_llm_client, is_llm_configured


def test_llm_settings_defaults() -> None:
    app_settings = Settings(_env_file=None)

    assert app_settings.openai_base_url == "https://api.openai.com/v1"
    assert app_settings.openai_model == "gpt-4o-mini"
    assert app_settings.openai_timeout_seconds == 30.0
    assert app_settings.openai_temperature == 0.2
    assert app_settings.openai_max_tokens == 1024


def test_llm_settings_can_read_openai_compatible_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")

    app_settings = Settings(_env_file=None)

    assert app_settings.openai_api_key == "test-key"
    assert app_settings.openai_base_url == "https://llm.example.com/v1"
    assert app_settings.openai_model == "compatible-model"
    assert is_llm_configured(app_settings)


def test_get_llm_client_requires_api_key() -> None:
    app_settings = Settings(_env_file=None, openai_api_key="")

    with pytest.raises(LLMConfigError):
        get_llm_client(app_settings)
