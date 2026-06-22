import pytest
from datetime import date
from unittest.mock import patch
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.reminder_cycle import ReminderCycle, ReminderCycleStatus
from app.models.todo import Todo
from app.models.email_log import EmailLog
from app.services.reminder_engine import scan_due_reminders
from app.services.email_sender import EmailSendResult


def test_yearly_recurrence_may_first(client: TestClient, auth_headers: dict, session: Session):
    # 1. Create a Todo with yearly recurrence, task_date 2026-05-01, 12 repeats, 0 days before
    payload = {
        "description": "每年5月1日重要任务",
        "recipient_email": "yearly_task@example.com",
        "calendar_type": "solar",
        "task_date": "2026-05-01",
        "remind_days_before": 0,
        "recurrence_type": "yearly",
        "repeat_count": 12,
    }

    response = client.post("/todos/", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    todo_id = response.json()["id"]

    # 2. Verify that exactly 12 reminder cycles were created
    cycles = session.exec(
        select(ReminderCycle)
        .where(ReminderCycle.todo_id == todo_id)
        .order_by(ReminderCycle.sequence)
    ).all()
    assert len(cycles) == 12

    # 3. Verify the generated target dates are May 1st for each year from 2026 to 2037
    expected_dates = [date(2026 + i, 5, 1) for i in range(12)]
    for idx, cycle in enumerate(cycles):
        assert cycle.sequence == idx + 1
        assert cycle.target_date == expected_dates[idx]
        assert cycle.reminder_start_date == expected_dates[idx]
        assert cycle.reminder_end_date == expected_dates[idx]
        assert cycle.status == ReminderCycleStatus.PENDING

    # 4. Mock the send_email function to succeed
    with patch("app.services.reminder_engine.send_email") as mock_send_email:
        mock_send_email.return_value = EmailSendResult(success=True)

        for i in range(12):
            year = 2026 + i
            target_date = date(year, 5, 1)
            before_date = date(year, 4, 30)
            after_date = date(year, 5, 2)

            # Test A: Scanning on April 30th (1 day before) should NOT send an email
            sent_before = scan_due_reminders(session=session, today=before_date)
            assert sent_before == 0

            # Test B: Scanning on May 2nd (1 day after) should NOT send an email
            sent_after = scan_due_reminders(session=session, today=after_date)
            assert sent_after == 0

            # Test C: Scanning on May 1st (target date) should send exactly 1 email
            mock_send_email.reset_mock()
            sent_on_day = scan_due_reminders(session=session, today=target_date)
            assert sent_on_day == 1
            mock_send_email.assert_called_once()

            # Test D: Scanning again on the same May 1st should NOT duplicate the email
            mock_send_email.reset_mock()
            sent_again = scan_due_reminders(session=session, today=target_date)
            assert sent_again == 0
            mock_send_email.assert_not_called()

            # Test E: Verify email log was created in DB for this target date
            email_logs = session.exec(
                select(EmailLog)
                .where(EmailLog.todo_id == todo_id)
                .where(EmailLog.sent_date == target_date)
            ).all()
            assert len(email_logs) == 1
            assert email_logs[0].recipient_email == "yearly_task@example.com"
            assert "每年5月1日重要任务" in email_logs[0].subject
