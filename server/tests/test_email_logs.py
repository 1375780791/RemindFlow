from datetime import date

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.email_log import EmailLog, EmailLogStatus
from app.models.reminder_cycle import ReminderCycle, ReminderCycleStatus
from app.services.email_sender import EmailSendResult
from app.services import reminder_engine


def test_scan_due_reminders_creates_one_success_log_per_day(
    client: TestClient,
    auth_headers: dict,
    session: Session,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "提醒日志测试",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 0,
        },
        headers=auth_headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    monkeypatch.setattr(
        reminder_engine,
        "send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )

    sent_count = reminder_engine.scan_due_reminders(session=session, today=date(2026, 6, 3))
    assert sent_count == 1

    logs = session.exec(select(EmailLog)).all()
    assert len(logs) == 1
    assert logs[0].status == EmailLogStatus.SUCCESS
    assert logs[0].sent_date == date(2026, 6, 3)

    sent_count_again = reminder_engine.scan_due_reminders(session=session, today=date(2026, 6, 3))
    assert sent_count_again == 0
    assert len(session.exec(select(EmailLog)).all()) == 1


def test_scan_due_reminders_records_failed_log(
    client: TestClient,
    auth_headers: dict,
    session: Session,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "失败日志测试",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 0,
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]
    cycle = session.exec(
        select(ReminderCycle).where(ReminderCycle.todo_id == todo_id)
    ).first()
    assert cycle is not None

    monkeypatch.setattr(
        reminder_engine,
        "send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(False, "SMTP error"),
    )

    sent_count = reminder_engine.scan_due_reminders(session=session, today=date(2026, 6, 3))
    assert sent_count == 0

    log = session.exec(select(EmailLog)).first()
    assert log is not None
    assert log.status == EmailLogStatus.FAILED
    assert log.error_message == "SMTP error"


def test_list_todo_email_logs(
    client: TestClient,
    auth_headers: dict,
    session: Session,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "日志查询测试",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 0,
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]
    cycle = session.exec(
        select(ReminderCycle).where(ReminderCycle.todo_id == todo_id)
    ).first()
    assert cycle is not None

    monkeypatch.setattr(
        reminder_engine,
        "send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )
    reminder_engine.scan_due_reminders(session=session, today=date(2026, 6, 3))

    response = client.get(f"/todos/{todo_id}/email-logs", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["todo_id"] == todo_id
    assert logs[0]["reminder_cycle_id"] == cycle.id
    assert logs[0]["recipient_email"] == "recipient@example.com"
    assert logs[0]["status"] == "success"
    assert "日志查询测试" in logs[0]["subject"]

    filtered_response = client.get(
        f"/todos/{todo_id}/email-logs?cycle_id={cycle.id}",
        headers=auth_headers,
    )
    assert filtered_response.status_code == status.HTTP_200_OK
    assert len(filtered_response.json()) == 1


def test_list_todo_email_logs_only_allows_owner(
    client: TestClient,
    auth_headers: dict,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "日志权限测试",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    client.post(
        "/auth/register",
        json={"email": "log_viewer@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "log_viewer@example.com", "password": "password123"},
    )
    other_headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}",
    }

    response = client.get(f"/todos/{todo_id}/email-logs", headers=other_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_send_todo_test_email_does_not_create_email_log(
    client: TestClient,
    auth_headers: dict,
    session: Session,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "测试邮件按钮",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2099-06-10",
            "remind_days_before": 2,
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    monkeypatch.setattr(
        "app.api.routes.todos.send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )

    response = client.post(f"/todos/{todo_id}/test-email", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "测试邮件发送成功"
    assert data["recipient_email"] == "recipient@example.com"
    assert "测试邮件按钮" in data["subject"]
    assert data["reminder_start_date"] == "2099-06-08"
    assert data["target_date"] == "2099-06-10"
    assert session.exec(select(EmailLog)).all() == []


def test_send_todo_test_email_returns_failure(
    client: TestClient,
    auth_headers: dict,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "测试邮件失败",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2099-06-10",
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]

    monkeypatch.setattr(
        "app.api.routes.todos.send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(False, "SMTP error"),
    )

    response = client.post(f"/todos/{todo_id}/test-email", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "测试邮件发送失败"
    assert data["error_message"] == "SMTP error"


def test_complete_cycle_requires_success_email_log(
    client: TestClient,
    auth_headers: dict,
    session: Session,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "未发送不能完成",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
        },
        headers=auth_headers,
    )
    todo_id = create_response.json()["id"]
    cycle = session.exec(
        select(ReminderCycle).where(ReminderCycle.todo_id == todo_id)
    ).first()
    assert cycle is not None

    response = client.post(
        f"/todos/{todo_id}/cycles/{cycle.id}/complete",
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "还没有成功发送邮件" in response.json()["detail"]
    session.refresh(cycle)
    assert cycle.status == ReminderCycleStatus.PENDING


def test_complete_cycle_after_success_email_log_stops_current_window(
    client: TestClient,
    auth_headers: dict,
    session: Session,
    monkeypatch,
):
    create_response = client.post(
        "/todos/",
        json={
            "description": "本轮完成测试",
            "recipient_email": "recipient@example.com",
            "calendar_type": "solar",
            "task_date": "2026-06-03",
            "remind_days_before": 2,
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
    assert len(cycles) == 2

    monkeypatch.setattr(
        reminder_engine,
        "send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )

    sent_count = reminder_engine.scan_due_reminders(session=session, today=date(2026, 6, 1))
    assert sent_count == 1

    complete_response = client.post(
        f"/todos/{todo_id}/cycles/{cycles[0].id}/complete",
        headers=auth_headers,
    )
    assert complete_response.status_code == status.HTTP_200_OK
    data = complete_response.json()
    assert data["status"] == "completed"
    assert data["completed_at"] is not None

    sent_count_after_complete = reminder_engine.scan_due_reminders(
        session=session,
        today=date(2026, 6, 2),
    )
    assert sent_count_after_complete == 0

    session.refresh(cycles[0])
    session.refresh(cycles[1])
    assert cycles[0].status == ReminderCycleStatus.COMPLETED
    assert cycles[1].status == ReminderCycleStatus.PENDING
