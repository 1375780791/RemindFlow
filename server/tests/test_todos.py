from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.reminder_cycle import ReminderCycle, ReminderCycleStatus
from app.models.todo import Todo
from app.services import reminder_engine
from app.services.email_sender import EmailSendResult


def test_create_solar_todo_success(client: TestClient, auth_headers: dict, session: Session):
    payload = {
        "description": "充话费",
        "recipient_email": "recipient@example.com",
        "calendar_type": "solar",
        "task_date": "2026-06-03",
        "remind_days_before": 2,
        "recurrence_type": "interval_days",
        "interval_days": 30,
    }
    response = client.post("/todos/", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["description"] == "充话费"
    assert data["recipient_email"] == "recipient@example.com"
    assert data["calendar_type"] == "solar"
    assert data["task_date"] == "2026-06-03"
    assert data["remind_days_before"] == 2
    assert data["recurrence_type"] == "interval_days"
    assert data["interval_days"] == 30
    assert data["is_active"] is True
    assert "id" in data

    # Verify in DB
    db_todo = session.get(Todo, data["id"])
    assert db_todo is not None
    assert db_todo.description == "充话费"

    cycles = session.exec(
        select(ReminderCycle).where(ReminderCycle.todo_id == data["id"])
    ).all()
    assert len(cycles) == 12
    assert cycles[0].sequence == 1
    assert cycles[0].target_date.isoformat() == "2026-06-03"
    assert cycles[0].reminder_start_date.isoformat() == "2026-06-01"
    assert cycles[0].reminder_end_date.isoformat() == "2026-06-03"


def test_create_lunar_todo_success(client: TestClient, auth_headers: dict, session: Session):
    payload = {
        "description": "农历生日",
        "recipient_email": "recipient@example.com",
        "calendar_type": "lunar",
        "task_date": "2026-06-03",
        "lunar_month": 4,
        "lunar_day": 18,
        "lunar_is_leap_month": False,
        "remind_days_before": 3,
        "recurrence_type": "yearly",
    }
    response = client.post("/todos/", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["description"] == "农历生日"
    assert data["calendar_type"] == "lunar"
    assert data["lunar_month"] == 4
    assert data["lunar_day"] == 18
    assert data["lunar_is_leap_month"] is False


def test_create_lunar_todo_without_lunar_fields_auto_fills_rule(
    client: TestClient,
    auth_headers: dict,
):
    payload = {
        "description": "农历生日（自动换算）",
        "recipient_email": "recipient@example.com",
        "calendar_type": "lunar",
        "task_date": "2026-06-03",
        "recurrence_type": "yearly",
    }
    response = client.post("/todos/", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["lunar_month"] == 4
    assert data["lunar_day"] == 18
    assert data["lunar_is_leap_month"] is False


def test_create_lunar_todo_mismatched_lunar_fields_fails(
    client: TestClient,
    auth_headers: dict,
):
    payload = {
        "description": "农历生日（日期不匹配）",
        "recipient_email": "recipient@example.com",
        "calendar_type": "lunar",
        "task_date": "2026-06-03",
        "lunar_month": 4,
        "lunar_day": 19,
        "recurrence_type": "yearly",
    }
    response = client.post("/todos/", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "task_date 与填写的农历日期不匹配" in response.text


def test_list_todo_cycles(client: TestClient, auth_headers: dict):
    create_response = client.post(
        "/todos/",
        json={
            "description": "周期列表测试",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 2,
            "recurrence_type": "monthly",
            "repeat_count": 3,
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    response = client.get(f"/todos/{todo_id}/cycles", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    cycles = response.json()
    assert len(cycles) == 3
    assert cycles[0]["sequence"] == 1
    assert cycles[0]["target_date"] == "2026-06-03"
    assert cycles[1]["sequence"] == 2
    assert cycles[1]["target_date"] == "2026-07-03"
    assert cycles[2]["sequence"] == 3
    assert cycles[2]["target_date"] == "2026-08-03"


def test_create_todo_interval_days_validation_fails(client: TestClient, auth_headers: dict):
    # 1. recurrence_type is interval_days but interval_days is missing
    payload_missing_interval = {
        "description": "每隔几天提醒",
        "recipient_email": "recipient@example.com",
        "calendar_type": "solar",
        "task_date": "2026-06-03",
        "recurrence_type": "interval_days",
    }
    response = client.post("/todos/", json=payload_missing_interval, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "按天间隔循环时必须填写 interval_days" in response.text

    # 2. recurrence_type is NOT interval_days but interval_days is provided
    payload_invalid_interval = {
        "description": "不循环但提供了间隔天数",
        "recipient_email": "recipient@example.com",
        "calendar_type": "solar",
        "task_date": "2026-06-03",
        "recurrence_type": "none",
        "interval_days": 10,
    }
    response = client.post("/todos/", json=payload_invalid_interval, headers=auth_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "只有 recurrence_type 为 interval_days 时才能填写 interval_days" in response.text


def test_create_todo_unauthorized_fails(client: TestClient):
    payload = {
        "description": "未授权创建",
        "recipient_email": "recipient@example.com",
        "calendar_type": "solar",
        "task_date": "2026-06-03",
    }
    response = client.post("/todos/", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_todos_only_returns_own_todos(client: TestClient, auth_headers: dict):
    # Create a todo for user A (using auth_headers)
    client.post(
        "/todos/",
        json={
            "description": "用户A的待办",
            "recipient_email": "a@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
        },
        headers=auth_headers,
    )

    # Register & Login User B
    client.post(
        "/auth/register",
        json={"email": "user_b@example.com", "password": "password123"},
    )
    b_login = client.post(
        "/auth/login",
        json={"email": "user_b@example.com", "password": "password123"},
    )
    b_token = b_login.json()["access_token"]
    b_headers = {"Authorization": f"Bearer {b_token}"}

    # Create a todo for user B
    client.post(
        "/todos/",
        json={
            "description": "用户B的待办",
            "recipient_email": "b@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
        },
        headers=b_headers,
    )

    # List todos for User A
    response_a = client.get("/todos/", headers=auth_headers)
    assert response_a.status_code == status.HTTP_200_OK
    todos_a = response_a.json()
    assert len(todos_a) == 1
    assert todos_a[0]["description"] == "用户A的待办"

    # List todos for User B
    response_b = client.get("/todos/", headers=b_headers)
    assert response_b.status_code == status.HTTP_200_OK
    todos_b = response_b.json()
    assert len(todos_b) == 1
    assert todos_b[0]["description"] == "用户B的待办"


def test_get_todo_detail(client: TestClient, auth_headers: dict):
    # Create todo
    create_response = client.post(
        "/todos/",
        json={
            "description": "详情测试",
            "recipient_email": "me@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    # Get details
    response = client.get(f"/todos/{todo_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["description"] == "详情测试"

    # Register & Login User B to check permission
    client.post(
        "/auth/register",
        json={"email": "user_c@example.com", "password": "password123"},
    )
    c_login = client.post(
        "/auth/login",
        json={"email": "user_c@example.com", "password": "password123"},
    )
    c_token = c_login.json()["access_token"]
    c_headers = {"Authorization": f"Bearer {c_token}"}

    # User B tries to view User A's todo detail (should return 404)
    response_unauthorized = client.get(f"/todos/{todo_id}", headers=c_headers)
    assert response_unauthorized.status_code == status.HTTP_404_NOT_FOUND
    assert "待办事项不存在" in response_unauthorized.json()["detail"]


def test_get_non_existent_todo_fails(client: TestClient, auth_headers: dict):
    response = client.get("/todos/9999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_todo_rebuilds_pending_cycles(
    client: TestClient,
    auth_headers: dict,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "编辑前",
            "recipient_email": "old@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 2,
            "recurrence_type": "monthly",
            "repeat_count": 3,
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    response = client.patch(
        f"/todos/{todo_id}",
        json={
            "description": "编辑后",
            "recipient_email": "new@example.com",
            "task_date": "2026-06-10",
            "remind_days_before": 1,
            "repeat_count": 2,
        },
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["description"] == "编辑后"
    assert data["recipient_email"] == "new@example.com"
    assert data["task_date"] == "2026-06-10"
    assert data["remind_days_before"] == 1
    assert data["repeat_count"] == 2

    cycles_response = client.get(f"/todos/{todo_id}/cycles", headers=auth_headers)
    cycles = cycles_response.json()
    assert len(cycles) == 2
    assert cycles[0]["target_date"] == "2026-06-10"
    assert cycles[0]["reminder_start_date"] == "2026-06-09"
    assert cycles[1]["target_date"] == "2026-07-10"


def test_update_todo_preserves_sent_or_completed_cycles(
    client: TestClient,
    auth_headers: dict,
    session: Session,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "保留历史周期",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 0,
            "recurrence_type": "monthly",
            "repeat_count": 2,
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]
    cycles = session.exec(
        select(ReminderCycle)
        .where(ReminderCycle.todo_id == todo_id)
        .order_by(ReminderCycle.sequence)
    ).all()

    monkeypatch.setattr(
        reminder_engine,
        "send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )
    reminder_engine.scan_due_reminders(session=session, today=cycles[0].target_date)

    complete_response = client.post(
        f"/todos/{todo_id}/cycles/{cycles[0].id}/complete",
        headers=auth_headers,
    )
    assert complete_response.status_code == status.HTTP_200_OK

    response = client.patch(
        f"/todos/{todo_id}",
        json={"task_date": "2026-06-10"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_200_OK

    updated_cycles = session.exec(
        select(ReminderCycle)
        .where(ReminderCycle.todo_id == todo_id)
        .order_by(ReminderCycle.sequence)
    ).all()
    assert len(updated_cycles) == 2
    assert updated_cycles[0].sequence == 1
    assert updated_cycles[0].target_date.isoformat() == "2026-06-03"
    assert updated_cycles[0].status == ReminderCycleStatus.COMPLETED
    assert updated_cycles[1].sequence == 2
    assert updated_cycles[1].target_date.isoformat() == "2026-07-10"
    assert updated_cycles[1].status == ReminderCycleStatus.PENDING


def test_update_todo_interval_days_validation_fails(
    client: TestClient,
    auth_headers: dict,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "编辑间隔校验",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    response = client.patch(
        f"/todos/{todo_id}",
        json={"recurrence_type": "interval_days"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "按天间隔循环时必须填写 interval_days" in response.text


def test_create_lunar_monthly_recurrence_success(client: TestClient, auth_headers: dict, session: Session):
    payload = {
        "description": "农历每月初一循环测试",
        "recipient_email": "recipient@example.com",
        "calendar_type": "lunar",
        "task_date": "2026-06-15",
        "lunar_month": 5,
        "lunar_day": 1,
        "lunar_is_leap_month": False,
        "recurrence_type": "monthly",
        "repeat_count": 3,
    }
    response = client.post("/todos/", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["calendar_type"] == "lunar"
    assert data["recurrence_type"] == "monthly"

    # Get cycles
    cycles_response = client.get(f"/todos/{data['id']}/cycles", headers=auth_headers)
    assert cycles_response.status_code == status.HTTP_200_OK
    cycles = cycles_response.json()
    assert len(cycles) == 3
    assert cycles[0]["sequence"] == 1
    assert cycles[0]["target_date"] == "2026-06-15"
    assert cycles[1]["sequence"] == 2
    assert cycles[1]["target_date"] == "2026-07-14"
    assert cycles[2]["sequence"] == 3
    assert cycles[2]["target_date"] == "2026-08-13"
