from datetime import date

from fastapi.testclient import TestClient

from app.models.todo import CalendarType, RecurrenceType
from app.schemas.todo_text_parse_result import TodoTextParseResult


def build_parse_result(**overrides) -> TodoTextParseResult:
    payload = {
        "description": "交话费",
        "recipient_email": "todo_user@example.com",
        "calendar_type": "solar",
        "task_date": "2026-06-12",
        "lunar_month": None,
        "lunar_day": None,
        "lunar_is_leap_month": False,
        "remind_days_before": 0,
        "recurrence_type": "none",
        "interval_days": None,
        "repeat_count": None,
        "confidence": 0.9,
        "missing_fields": [],
        "clarification_question": None,
        "assumptions": [],
    }
    payload.update(overrides)
    return TodoTextParseResult.model_validate(payload)


def test_parse_todo_from_text_returns_parsed_result(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_parse_todo_text(text: str, **kwargs):
        assert text == "周五提醒我交话费"
        assert kwargs["default_recipient_email"] == "todo_user@example.com"
        assert kwargs["actor_user_id"] == 1
        assert kwargs["actor_email"] == "todo_user@example.com"
        return build_parse_result()

    monkeypatch.setattr("app.api.routes.todos.parse_todo_text", fake_parse_todo_text)

    response = client.post(
        "/todos/parse-text",
        json={"text": "周五提醒我交话费"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "parsed"
    assert data["result"]["description"] == "交话费"
    assert data["result"]["calendar_type"] == CalendarType.SOLAR
    assert data["result"]["task_date"] == date(2026, 6, 12).isoformat()
    assert data["result"]["recurrence_type"] == RecurrenceType.NONE


def test_parse_todo_from_text_returns_missing_field_details(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    async def fake_parse_todo_text(text: str, **kwargs):
        return build_parse_result(
            task_date=None,
            missing_fields=["task_date"],
            clarification_question="你希望我什么时候提醒你交话费？",
        )

    monkeypatch.setattr("app.api.routes.todos.parse_todo_text", fake_parse_todo_text)

    response = client.post(
        "/todos/parse-text",
        json={"text": "提醒我交话费"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_clarification"
    assert data["result"]["missing_field_details"] == [
        {
            "field": "task_date",
            "message": "用户未提供准确提醒日期",
        }
    ]
