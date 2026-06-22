from datetime import date

from app.services.todo_text_prompt import (
    TODO_TEXT_PARSE_JSON_SCHEMA,
    TODO_TEXT_PARSE_SYSTEM_PROMPT,
    build_todo_text_parse_messages,
)


def test_todo_text_parse_prompt_contains_core_rules() -> None:
    assert "只输出符合 JSON Schema 的 JSON" in TODO_TEXT_PARSE_SYSTEM_PROMPT
    assert "current_date" in TODO_TEXT_PARSE_SYSTEM_PROMPT
    assert "recurrence_type" in TODO_TEXT_PARSE_SYSTEM_PROMPT
    assert "农历" in TODO_TEXT_PARSE_SYSTEM_PROMPT


def test_todo_text_parse_schema_matches_todo_fields() -> None:
    schema = TODO_TEXT_PARSE_JSON_SCHEMA["schema"]
    properties = schema["properties"]

    for field in [
        "description",
        "recipient_email",
        "calendar_type",
        "task_date",
        "lunar_month",
        "lunar_day",
        "lunar_is_leap_month",
        "remind_days_before",
        "recurrence_type",
        "interval_days",
        "repeat_count",
    ]:
        assert field in properties
        assert field in schema["required"]

    assert schema["additionalProperties"] is False
    assert TODO_TEXT_PARSE_JSON_SCHEMA["strict"] is True


def test_build_todo_text_parse_messages_includes_runtime_context() -> None:
    messages = build_todo_text_parse_messages(
        "下周五提醒我交房租，提前一天提醒",
        current_date=date(2026, 6, 10),
        timezone="Asia/Shanghai",
        default_recipient_email="me@example.com",
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = str(messages[1]["content"])
    assert "2026-06-10" in user_content
    assert "Asia/Shanghai" in user_content
    assert "me@example.com" in user_content
    assert "下周五提醒我交房租，提前一天提醒" in user_content
