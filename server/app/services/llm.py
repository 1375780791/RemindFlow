from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from app.core.config import Settings, settings


class LLMConfigError(RuntimeError):
    pass


class LLMConnectionTestError(RuntimeError):
    pass


def is_llm_configured(app_settings: Settings = settings) -> bool:
    return bool(app_settings.openai_api_key.strip())


def get_llm_client(app_settings: Settings = settings) -> AsyncOpenAI:
    if not is_llm_configured(app_settings):
        raise LLMConfigError("OPENAI_API_KEY is not configured")

    return AsyncOpenAI(
        api_key=app_settings.openai_api_key,
        base_url=app_settings.openai_base_url,
        timeout=app_settings.openai_timeout_seconds,
    )


async def create_chat_completion(
    messages: Sequence[ChatCompletionMessageParam],
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
    app_settings: Settings = settings,
) -> ChatCompletion:
    client = get_llm_client(app_settings)
    payload: dict[str, Any] = {
        "model": model or app_settings.openai_model,
        "messages": list(messages),
        "temperature": (
            app_settings.openai_temperature if temperature is None else temperature
        ),
        "max_tokens": (
            app_settings.openai_max_tokens if max_tokens is None else max_tokens
        ),
    }
    if response_format is not None:
        payload["response_format"] = response_format

    return await client.chat.completions.create(**payload)


async def test_llm_connection(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    app_settings: Settings = settings,
) -> tuple[str, str]:
    resolved_api_key = (api_key or app_settings.openai_api_key).strip()
    resolved_base_url = (base_url or app_settings.openai_base_url).strip()
    resolved_model = (model or app_settings.openai_model).strip()

    if not resolved_api_key:
        raise LLMConfigError("OPENAI_API_KEY is not configured")
    if not resolved_base_url:
        raise LLMConfigError("OPENAI_BASE_URL is not configured")
    if not resolved_model:
        raise LLMConfigError("OPENAI_MODEL is not configured")

    client = AsyncOpenAI(
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        timeout=app_settings.openai_timeout_seconds,
    )

    try:
        await client.chat.completions.create(
            model=resolved_model,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with OK to confirm this connection works.",
                }
            ],
            temperature=0,
            max_tokens=8,
        )
    except OpenAIError as exc:
        raise LLMConnectionTestError(str(exc)) from exc

    return resolved_base_url, resolved_model
