from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Integer
from sqlmodel import Field, SQLModel


class CalendarType(str, Enum):
    SOLAR = "solar"
    LUNAR = "lunar"


class RecurrenceType(str, Enum):
    NONE = "none"
    DAILY = "daily"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    INTERVAL_DAYS = "interval_days"


class Todo(SQLModel, table=True):
    __tablename__ = "todos"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    user_id: int = Field(foreign_key="users.id", index=True)

    description: str = Field(min_length=1, max_length=500)
    recipient_email: str = Field(max_length=255)

    calendar_type: CalendarType = Field(default=CalendarType.SOLAR, index=True)
    task_date: date
    lunar_month: int | None = Field(default=None, ge=1, le=12)
    lunar_day: int | None = Field(default=None, ge=1, le=30)
    lunar_is_leap_month: bool = False

    remind_days_before: int = Field(default=0, ge=0, le=365)
    recurrence_type: RecurrenceType = Field(default=RecurrenceType.NONE, index=True)
    interval_days: int | None = Field(default=None, ge=1)
    repeat_count: int | None = Field(default=None, ge=1, le=100)

    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
