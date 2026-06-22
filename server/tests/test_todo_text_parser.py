import json
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.todo import CalendarType, RecurrenceType
from app.services.todo_text_parser import (
    TodoTextParseError,
    parse_todo_text,
    parse_todo_text_result_content,
)


def build_completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def valid_payload() -> dict[str, Any]:
    return {
        "description": "交房租",
        "recipient_email": "me@example.com",
        "calendar_type": "solar",
        "task_date": "2026-06-19",
        "lunar_month": None,
        "lunar_day": None,
        "lunar_is_leap_month": False,
        "remind_days_before": 1,
        "recurrence_type": "none",
        "interval_days": None,
        "repeat_count": None,
        "confidence": 0.92,
        "missing_fields": [],
        "clarification_question": None,
        "assumptions": [],
    }


def missing_date_payload() -> dict[str, Any]:
    payload = valid_payload()
    payload["task_date"] = None
    payload["missing_fields"] = ["task_date"]
    payload["clarification_question"] = "你希望我什么时候提醒你交房租？"
    payload["confidence"] = 0.6
    return payload


def test_parse_todo_text_result_content_accepts_valid_json() -> None:
    result = parse_todo_text_result_content(json.dumps(valid_payload()))

    assert result.description == "交房租"
    assert result.recipient_email == "me@example.com"
    assert result.calendar_type == CalendarType.SOLAR
    assert result.task_date == date(2026, 6, 19)
    assert result.recurrence_type == RecurrenceType.NONE
    assert result.missing_field_details == []


def test_parse_todo_text_result_content_rejects_extra_sentence() -> None:
    content = f"好的，我现在执行。\n{json.dumps(valid_payload())}"

    with pytest.raises(TodoTextParseError, match="not valid JSON"):
        parse_todo_text_result_content(content)


def test_parse_todo_text_result_content_rejects_invalid_business_rule() -> None:
    payload = valid_payload()
    payload["recurrence_type"] = "monthly"
    payload["interval_days"] = 10

    with pytest.raises(TodoTextParseError, match="does not match todo schema"):
        parse_todo_text_result_content(json.dumps(payload))


def test_parse_todo_text_result_content_normalizes_safe_provider_variants() -> None:
    payload = valid_payload()
    payload["lunar_is_leap_month"] = None
    payload["assumptions"] = "未说明提前提醒，按当天提醒处理"

    result = parse_todo_text_result_content(json.dumps(payload))

    assert result.lunar_is_leap_month is False
    assert result.assumptions == ["未说明提前提醒，按当天提醒处理"]


def test_parse_todo_text_result_content_allows_lunar_without_task_date() -> None:
    payload = valid_payload()
    payload.update(
        {
            "description": "买月饼",
            "calendar_type": "lunar",
            "task_date": None,
            "lunar_month": 8,
            "lunar_day": 15,
            "lunar_is_leap_month": False,
            "missing_fields": [],
        }
    )

    result = parse_todo_text_result_content(json.dumps(payload))

    assert result.task_date is None
    assert result.missing_fields == []


@pytest.mark.anyio
async def test_parse_todo_text_uses_schema_response_format() -> None:
    calls = []

    async def completion_fn(messages, response_format):
        calls.append((messages, response_format))
        return build_completion(json.dumps(valid_payload()))

    result = await parse_todo_text(
        "下周五提醒我交房租，提前一天提醒",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
        completion_fn=completion_fn,
    )

    assert result.description == "交房租"
    assert calls[0][1]["type"] == "json_schema"
    assert calls[0][1]["json_schema"]["strict"] is True
    user_message = calls[0][0][1]["content"]
    assert "2026-06-10" in user_message
    assert "下周五提醒我交房租，提前一天提醒" in user_message


@pytest.mark.anyio
async def test_parse_todo_text_retries_invalid_json_output() -> None:
    calls = []

    async def completion_fn(messages, response_format):
        calls.append((messages, response_format))
        if len(calls) == 1:
            return build_completion("好的，我现在执行。")
        return build_completion(json.dumps(valid_payload()))

    result = await parse_todo_text(
        "下周五提醒我交房租，提前一天提醒",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
        completion_fn=completion_fn,
    )

    assert result.description == "交房租"
    assert len(calls) == 2
    assert "上一次输出不符合要求" in calls[1][0][-1]["content"]


@pytest.mark.anyio
async def test_parse_todo_text_falls_back_when_response_format_is_unsupported() -> None:
    calls = []

    async def completion_fn(messages, response_format):
        calls.append((messages, response_format))
        if response_format is not None:
            raise RuntimeError("This response_format type is unavailable now")
        return build_completion(json.dumps(valid_payload()))

    result = await parse_todo_text(
        "周五提醒我交话费",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
        completion_fn=completion_fn,
    )

    assert result.description == "交房租"
    assert calls[0][1]["type"] == "json_schema"
    assert calls[1][1] is None


@pytest.mark.anyio
async def test_parse_todo_text_normalizes_lunar_task_date() -> None:
    payload = valid_payload()
    payload.update(
        {
            "description": "买月饼",
            "calendar_type": "lunar",
            "task_date": "2026-09-15",
            "lunar_month": 8,
            "lunar_day": 15,
            "lunar_is_leap_month": False,
        }
    )

    async def completion_fn(messages, response_format):
        return build_completion(json.dumps(payload))

    result = await parse_todo_text(
        "农历八月十五提醒我买月饼",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
        completion_fn=completion_fn,
    )

    assert result.calendar_type == CalendarType.LUNAR
    assert result.task_date == date(2026, 9, 25)
    assert result.lunar_month == 8
    assert result.lunar_day == 15


@pytest.mark.anyio
async def test_parse_todo_text_fills_lunar_task_date_when_model_leaves_it_empty() -> None:
    payload = valid_payload()
    payload.update(
        {
            "description": "买月饼",
            "calendar_type": "lunar",
            "task_date": None,
            "lunar_month": 8,
            "lunar_day": 15,
            "lunar_is_leap_month": False,
        }
    )

    async def completion_fn(messages, response_format):
        return build_completion(json.dumps(payload))

    result = await parse_todo_text(
        "农历八月十五提醒我买月饼",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
        completion_fn=completion_fn,
    )

    assert result.task_date == date(2026, 9, 25)
    assert result.missing_fields == []


@pytest.mark.anyio
async def test_parse_todo_text_does_not_retry_valid_clarification_result() -> None:
    calls = []

    async def completion_fn(messages, response_format):
        calls.append((messages, response_format))
        return build_completion(json.dumps(missing_date_payload()))

    result = await parse_todo_text(
        "提醒我交房租",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
        completion_fn=completion_fn,
    )

    assert result.task_date is None
    assert result.clarification_question == "你希望我什么时候提醒你交房租？"
    assert result.missing_field_details[0].message == "用户未提供准确提醒日期"
    assert len(calls) == 1


@pytest.mark.anyio
async def test_parse_todo_text_raises_after_retry_limit() -> None:
    calls = []

    async def completion_fn(messages, response_format):
        calls.append((messages, response_format))
        return build_completion("好的，我现在执行。")

    with pytest.raises(TodoTextParseError, match="not valid JSON"):
        await parse_todo_text(
            "下周五提醒我交房租",
            current_date=date(2026, 6, 10),
            timezone="Asia/Shanghai",
            default_recipient_email="me@example.com",
            max_retries=1,
            completion_fn=completion_fn,
        )

    assert len(calls) == 2
