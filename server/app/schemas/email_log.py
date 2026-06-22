from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from app.models.email_log import EmailLogStatus


class EmailLogResponse(BaseModel):
    id: int
    todo_id: int
    reminder_cycle_id: int
    user_id: int
    recipient_email: EmailStr
    subject: str
    body_text: str
    status: EmailLogStatus
    error_message: str | None
    sent_date: date
    sent_at: datetime
    created_at: datetime
    updated_at: datetime
