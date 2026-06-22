from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Integer, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class EmailLogStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class EmailLog(SQLModel, table=True):
    __tablename__ = "email_logs"
    __table_args__ = (
        UniqueConstraint(
            "reminder_cycle_id",
            "sent_date",
            name="uq_email_logs_cycle_sent_date",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    todo_id: int = Field(foreign_key="todos.id", index=True)
    reminder_cycle_id: int = Field(foreign_key="reminder_cycles.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    recipient_email: str = Field(max_length=255, index=True)
    subject: str = Field(max_length=255)
    body_text: str = Field(sa_column=Column(Text))

    status: EmailLogStatus = Field(default=EmailLogStatus.SUCCESS, index=True)
    error_message: str | None = Field(default=None, sa_column=Column(Text))

    sent_date: date = Field(index=True)
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
