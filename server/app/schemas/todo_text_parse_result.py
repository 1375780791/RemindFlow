from datetime import date
from enum import Enum
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models.todo import CalendarType, RecurrenceType


class TodoTextParseMissingField(str, Enum):
    DESCRIPTION = "description"
    RECIPIENT_EMAIL = "recipient_email"
    CALENDAR_TYPE = "calendar_type"
    TASK_DATE = "task_date"
    LUNAR_MONTH = "lunar_month"
    LUNAR_DAY = "lunar_day"
    REMIND_DAYS_BEFORE = "remind_days_before"
    RECURRENCE_TYPE = "recurrence_type"
    INTERVAL_DAYS = "interval_days"
    REPEAT_COUNT = "repeat_count"


class TodoTextParseMissingFieldDetail(BaseModel):
    field: TodoTextParseMissingField
    message: str


MISSING_FIELD_MESSAGES = {
    TodoTextParseMissingField.DESCRIPTION: "用户未提供提醒事项",
    TodoTextParseMissingField.RECIPIENT_EMAIL: "用户未提供收件邮箱",
    TodoTextParseMissingField.CALENDAR_TYPE: "用户未提供明确的日期类型",
    TodoTextParseMissingField.TASK_DATE: "用户未提供准确提醒日期",
    TodoTextParseMissingField.LUNAR_MONTH: "用户未提供准确农历月份",
    TodoTextParseMissingField.LUNAR_DAY: "用户未提供准确农历日期",
    TodoTextParseMissingField.REMIND_DAYS_BEFORE: "用户未提供提前提醒天数",
    TodoTextParseMissingField.RECURRENCE_TYPE: "用户未提供明确的重复规则",
    TodoTextParseMissingField.INTERVAL_DAYS: "用户未提供准确间隔天数",
    TodoTextParseMissingField.REPEAT_COUNT: "用户未提供准确重复次数",
}


class TodoTextParseResult(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    recipient_email: EmailStr | None = None
    calendar_type: CalendarType | None = None
    task_date: date | None = None
    lunar_month: int | None = Field(default=None, ge=1, le=12)
    lunar_day: int | None = Field(default=None, ge=1, le=30)
    lunar_is_leap_month: bool = False
    remind_days_before: int = Field(ge=0, le=365)
    recurrence_type: RecurrenceType
    interval_days: int | None = Field(default=None, ge=1)
    repeat_count: int | None = Field(default=None, ge=1, le=100)
    confidence: float = Field(ge=0, le=1)
    missing_fields: list[TodoTextParseMissingField] = Field(default_factory=list)
    clarification_question: str | None = Field(default=None, max_length=300)
    assumptions: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("lunar_is_leap_month", mode="before")
    @classmethod
    def normalize_lunar_is_leap_month(cls, value):
        if value is None:
            return False
        return value

    @field_validator("assumptions", mode="before")
    @classmethod
    def normalize_assumptions(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @computed_field
    @property
    def missing_field_details(self) -> list[TodoTextParseMissingFieldDetail]:
        return [
            TodoTextParseMissingFieldDetail(
                field=field,
                message=MISSING_FIELD_MESSAGES[field],
            )
            for field in self.missing_fields
        ]

    @model_validator(mode="after")
    def validate_parse_result(self) -> "TodoTextParseResult":
        missing = set(self.missing_fields)
        has_complete_lunar_rule = (
            self.calendar_type == CalendarType.LUNAR
            and self.lunar_month is not None
            and self.lunar_day is not None
        )

        if self.description is None:
            missing.add(TodoTextParseMissingField.DESCRIPTION)
        if self.recipient_email is None:
            missing.add(TodoTextParseMissingField.RECIPIENT_EMAIL)
        if self.calendar_type is None:
            missing.add(TodoTextParseMissingField.CALENDAR_TYPE)
        if has_complete_lunar_rule:
            missing.discard(TodoTextParseMissingField.TASK_DATE)
        elif self.task_date is None:
            missing.add(TodoTextParseMissingField.TASK_DATE)

        if self.calendar_type == CalendarType.LUNAR:
            if self.lunar_month is None:
                missing.add(TodoTextParseMissingField.LUNAR_MONTH)
            if self.lunar_day is None:
                missing.add(TodoTextParseMissingField.LUNAR_DAY)
        elif self.lunar_month is not None or self.lunar_day is not None:
            raise ValueError("只有 calendar_type 为 lunar 时才能填写农历月日")

        if self.recurrence_type == RecurrenceType.INTERVAL_DAYS:
            if self.interval_days is None:
                missing.add(TodoTextParseMissingField.INTERVAL_DAYS)
        elif self.interval_days is not None:
            raise ValueError("只有 recurrence_type 为 interval_days 时才能填写 interval_days")

        if missing and self.clarification_question is None:
            raise ValueError("缺少必要字段时必须提供 clarification_question")

        self.missing_fields = sorted(missing, key=lambda field: field.value)
        return self


class TodoTextParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class TodoTextParseResponse(BaseModel):
    status: Literal["parsed", "needs_clarification"]
    result: TodoTextParseResult
