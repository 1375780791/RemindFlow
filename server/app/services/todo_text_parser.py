import json
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from app.core.config import settings
from app.models.todo import CalendarType
from app.schemas.todo_text_parse_result import (
    TodoTextParseMissingField,
    TodoTextParseResult,
)
from app.services.calendar import lunar_to_solar
from app.services.llm import create_chat_completion
from app.services.todo_text_prompt import (
    TODO_TEXT_PARSE_JSON_SCHEMA,
    build_todo_text_parse_messages,
)

_llm_debug_logger: logging.Logger | None = None


class TodoTextParseError(RuntimeError):
    pass


class TodoTextParseOutputError(TodoTextParseError):
    pass


CompletionFn = Callable[
    [list[ChatCompletionMessageParam], dict[str, Any] | None],
    Awaitable[Any],
]


def get_current_date(timezone: str) -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def get_llm_debug_logger() -> logging.Logger:
    global _llm_debug_logger
    if _llm_debug_logger is not None:
        return _llm_debug_logger

    log_path = Path(settings.llm_debug_log_path)
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("remindflow.llm_debug")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)

    _llm_debug_logger = logger
    return logger


def write_llm_debug_log(event: str, payload: dict[str, Any]) -> None:
    if not settings.llm_debug_log_enabled:
        return

    logger = get_llm_debug_logger()
    logger.info(
        "%s %s",
        event,
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def build_todo_text_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": TODO_TEXT_PARSE_JSON_SCHEMA,
    }


def is_response_format_unsupported(exc: Exception) -> bool:
    message = str(exc).lower()
    return "response_format" in message and (
        "unavailable" in message
        or "unsupported" in message
        or "invalid_request" in message
    )


def extract_completion_content(completion: Any) -> str:
    try:
        content = completion.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise TodoTextParseOutputError("LLM response has no message content") from exc

    if not isinstance(content, str) or not content.strip():
        raise TodoTextParseOutputError("LLM response content is empty")
    return content


def parse_todo_text_result_content(content: str) -> TodoTextParseResult:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TodoTextParseOutputError("LLM response is not valid JSON") from exc

    try:
        return TodoTextParseResult.model_validate(payload)
    except ValidationError as exc:
        raise TodoTextParseOutputError(
            "LLM response does not match todo schema"
        ) from exc


def normalize_lunar_parse_result(
    result: TodoTextParseResult,
    *,
    current_date: date,
) -> TodoTextParseResult:
    if result.calendar_type != CalendarType.LUNAR:
        return result
    if result.lunar_month is None or result.lunar_day is None:
        return result

    year = result.task_date.year if result.task_date is not None else current_date.year
    try:
        solar_date = lunar_to_solar(
            year,
            result.lunar_month,
            result.lunar_day,
            result.lunar_is_leap_month,
        )
    except ValueError:
        solar_date = lunar_to_solar(
            current_date.year,
            result.lunar_month,
            result.lunar_day,
            result.lunar_is_leap_month,
        )

    if solar_date < current_date:
        solar_date = lunar_to_solar(
            solar_date.year + 1,
            result.lunar_month,
            result.lunar_day,
            result.lunar_is_leap_month,
        )

    if result.task_date != solar_date:
        write_llm_debug_log(
            "todo_text_parse.lunar_date_normalized",
            {
                "original_task_date": result.task_date,
                "normalized_task_date": solar_date,
                "lunar_month": result.lunar_month,
                "lunar_day": result.lunar_day,
                "lunar_is_leap_month": result.lunar_is_leap_month,
            },
        )
        result.task_date = solar_date

    result.missing_fields = [
        field
        for field in result.missing_fields
        if field != TodoTextParseMissingField.TASK_DATE
    ]
    if not result.missing_fields:
        result.clarification_question = None

    return result


def build_retry_messages(
    messages: list[ChatCompletionMessageParam],
) -> list[ChatCompletionMessageParam]:
    return [
        *messages,
        {
            "role": "user",
            "content": (
                "上一次输出不符合要求。请重新解析同一段 user_text，"
                "只输出符合 JSON Schema 的 JSON，不要输出任何解释。"
            ),
        },
    ]


async def parse_todo_text(
    text: str,
    *,
    current_date: date | None = None,
    timezone: str | None = None,
    default_recipient_email: str | None = None,
    actor_user_id: int | None = None,
    actor_email: str | None = None,
    max_retries: int = 1,
    completion_fn: CompletionFn | None = None,
) -> TodoTextParseResult:
    resolved_timezone = timezone or settings.scheduler_timezone
    resolved_current_date = current_date or get_current_date(resolved_timezone)
    messages = build_todo_text_parse_messages(
        text,
        current_date=resolved_current_date,
        timezone=resolved_timezone,
        default_recipient_email=default_recipient_email,
    )
    response_format = build_todo_text_response_format()
    write_llm_debug_log(
        "todo_text_parse.input",
        {
            "user_text": text,
            "current_date": resolved_current_date,
            "timezone": resolved_timezone,
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "has_default_recipient_email": bool(default_recipient_email),
        },
    )

    async def default_completion_fn(
        request_messages: list[ChatCompletionMessageParam],
        request_response_format: dict[str, Any] | None,
    ) -> Any:
        return await create_chat_completion(
            request_messages,
            response_format=request_response_format,
        )

    last_error: TodoTextParseOutputError | None = None
    structured_output_supported = True
    for attempt in range(max_retries + 1):
        request_messages = messages if attempt == 0 else build_retry_messages(messages)
        request_response_format = response_format if structured_output_supported else None
        write_llm_debug_log(
            "todo_text_parse.request",
            {
                "attempt": attempt + 1,
                "structured_output_enabled": request_response_format is not None,
                "messages": request_messages,
                "response_format": request_response_format,
            },
        )
        try:
            completion = await (completion_fn or default_completion_fn)(
                request_messages,
                request_response_format,
            )
        except Exception as exc:
            if request_response_format is not None and is_response_format_unsupported(exc):
                structured_output_supported = False
                write_llm_debug_log(
                    "todo_text_parse.response_format_fallback",
                    {
                        "attempt": attempt + 1,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                completion = await (completion_fn or default_completion_fn)(
                    request_messages,
                    None,
                )
            else:
                write_llm_debug_log(
                    "todo_text_parse.request_error",
                    {
                        "attempt": attempt + 1,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                raise TodoTextParseError("LLM request failed") from exc
        try:
            content = extract_completion_content(completion)
            write_llm_debug_log(
                "todo_text_parse.response",
                {
                    "attempt": attempt + 1,
                    "content": content,
                },
            )
            result = parse_todo_text_result_content(content)
            result = normalize_lunar_parse_result(
                result,
                current_date=resolved_current_date,
            )
            write_llm_debug_log(
                "todo_text_parse.parsed",
                {
                    "attempt": attempt + 1,
                    "result": result.model_dump(),
                },
            )
            return result
        except TodoTextParseOutputError as exc:
            last_error = exc
            write_llm_debug_log(
                "todo_text_parse.parse_error",
                {
                    "attempt": attempt + 1,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "will_retry": attempt < max_retries,
                },
            )

    if last_error is not None:
        raise last_error
    raise TodoTextParseError("Todo text parsing failed")
