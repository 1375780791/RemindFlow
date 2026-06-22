from datetime import date, datetime

from pydantic import BaseModel

from app.models.reminder_cycle import ReminderCycleStatus


class ReminderCycleResponse(BaseModel):
    id: int
    todo_id: int
    user_id: int
    sequence: int
    target_date: date
    reminder_start_date: date
    reminder_end_date: date
    status: ReminderCycleStatus
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
