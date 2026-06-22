from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.todo import CalendarType, RecurrenceType


class TodoCreateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    recipient_email: EmailStr
    calendar_type: CalendarType = CalendarType.SOLAR
    task_date: date
    lunar_month: int | None = Field(default=None, ge=1, le=12)
    lunar_day: int | None = Field(default=None, ge=1, le=30)
    lunar_is_leap_month: bool = False
    remind_days_before: int = Field(default=0, ge=0, le=365)
    recurrence_type: RecurrenceType = RecurrenceType.NONE
    interval_days: int | None = Field(default=None, ge=1)
    repeat_count: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def validate_calendar_and_recurrence(self) -> "TodoCreateRequest":
        if self.recurrence_type == RecurrenceType.INTERVAL_DAYS:
            if self.interval_days is None:
                raise ValueError("按天间隔循环时必须填写 interval_days")
        elif self.interval_days is not None:
            raise ValueError("只有 recurrence_type 为 interval_days 时才能填写 interval_days")

        return self


class TodoUpdateRequest(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    recipient_email: EmailStr | None = None
    calendar_type: CalendarType | None = None
    task_date: date | None = None
    lunar_month: int | None = Field(default=None, ge=1, le=12)
    lunar_day: int | None = Field(default=None, ge=1, le=30)
    lunar_is_leap_month: bool | None = None
    remind_days_before: int | None = Field(default=None, ge=0, le=365)
    recurrence_type: RecurrenceType | None = None
    interval_days: int | None = Field(default=None, ge=1)
    repeat_count: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class TodoResponse(BaseModel):
    id: int
    user_id: int
    description: str
    recipient_email: EmailStr
    calendar_type: CalendarType
    task_date: date
    lunar_month: int | None
    lunar_day: int | None
    lunar_is_leap_month: bool
    remind_days_before: int
    recurrence_type: RecurrenceType
    interval_days: int | None
    repeat_count: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TodoPreviewItem(BaseModel):
    sequence: int
    solar_date: date
    lunar_date: str
    lunar_month: int
    lunar_day: int
    lunar_is_leap_month: bool
    reminder_start_date: date
    reminder_end_date: date


class DateConversionRequest(BaseModel):
    calendar_type: CalendarType
    solar_date: date | None = None
    lunar_year: int | None = None
    lunar_month: int | None = None
    lunar_day: int | None = None
    lunar_is_leap_month: bool = False


class DateConversionResponse(BaseModel):
    solar_date: date
    lunar_year: int
    lunar_month: int
    lunar_day: int
    lunar_is_leap_month: bool
    lunar_date_str: str
    solar_date_str: str


class TestEmailResponse(BaseModel):
    success: bool
    message: str
    recipient_email: EmailStr
    subject: str
    reminder_cycle_id: int
    reminder_start_date: date
    reminder_end_date: date
    target_date: date
    error_message: str | None = None
