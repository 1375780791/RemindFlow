from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


class ReminderCycleStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


class ReminderCycle(SQLModel, table=True):
    __tablename__ = "reminder_cycles"
    __table_args__ = (
        UniqueConstraint("todo_id", "sequence", name="uq_reminder_cycles_todo_sequence"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    todo_id: int = Field(foreign_key="todos.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    sequence: int = Field(ge=1, index=True)
    target_date: date = Field(index=True)
    reminder_start_date: date = Field(index=True)
    reminder_end_date: date = Field(index=True)

    status: ReminderCycleStatus = Field(
        default=ReminderCycleStatus.PENDING,
        index=True,
    )
    completed_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
