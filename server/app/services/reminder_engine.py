from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.email_log import EmailLog, EmailLogStatus
from app.models.reminder_cycle import ReminderCycle
from app.models.reminder_cycle import ReminderCycleStatus
from app.models.todo import CalendarType, RecurrenceType, Todo
from lunardate import LunarDate
from app.services.calendar import lunar_to_solar, solar_to_lunar
from app.services.email_sender import build_reminder_email, send_email
from sqlmodel import Session, select


def add_months(source_date: date, months: int) -> date:
    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def get_next_lunar_month(y: int, m: int, is_leap: bool) -> tuple[int, int, bool]:
    if not is_leap:
        try:
            # Call toSolarDate() to force lunardate to validate if the leap month exists
            LunarDate(y, m, 1, True).toSolarDate()
            return y, m, True
        except ValueError:
            pass
    if m == 12:
        return y + 1, 1, False
    else:
        return y, m + 1, False


def get_lunar_date_safe(y: int, m: int, d: int, is_leap: bool) -> LunarDate:
    try:
        ld = LunarDate(y, m, d, is_leap)
        ld.toSolarDate()  # Force validation of day range
        return ld
    except ValueError:
        if d == 30:
            try:
                ld = LunarDate(y, m, 29, is_leap)
                ld.toSolarDate()  # Force validation of day range
                return ld
            except ValueError:
                pass
        raise ValueError(f"无效的农历日期：{y}年{m}月{d}日")


def get_cycle_count(todo: Todo) -> int:
    if todo.recurrence_type == RecurrenceType.NONE:
        return 1
    if todo.repeat_count is not None:
        return todo.repeat_count
    return settings.default_generated_cycle_count


def get_cycle_target_date(todo: Todo, sequence: int) -> date:
    offset = sequence - 1

    if todo.calendar_type == CalendarType.LUNAR and todo.recurrence_type == RecurrenceType.YEARLY:
        if todo.lunar_month is None or todo.lunar_day is None:
            raise ValueError("农历年度循环任务缺少 lunar_month 或 lunar_day")
        return lunar_to_solar(
            year=todo.task_date.year + offset,
            month=todo.lunar_month,
            day=todo.lunar_day,
            is_leap_month=todo.lunar_is_leap_month,
        )

    if todo.calendar_type == CalendarType.LUNAR and todo.recurrence_type == RecurrenceType.MONTHLY:
        base_lunar = solar_to_lunar(todo.task_date)
        y = base_lunar.year
        m = base_lunar.month
        is_leap = base_lunar.is_leap_month
        for _ in range(offset):
            y, m, is_leap = get_next_lunar_month(y, m, is_leap)
        return get_lunar_date_safe(y, m, base_lunar.day, is_leap).toSolarDate()

    if todo.recurrence_type == RecurrenceType.NONE:
        return todo.task_date
    if todo.recurrence_type == RecurrenceType.DAILY:
        return todo.task_date + timedelta(days=offset)
    if todo.recurrence_type == RecurrenceType.MONTHLY:
        return add_months(todo.task_date, offset)
    if todo.recurrence_type == RecurrenceType.YEARLY:
        return add_months(todo.task_date, offset * 12)
    if todo.recurrence_type == RecurrenceType.INTERVAL_DAYS:
        if todo.interval_days is None:
            raise ValueError("按天间隔循环任务缺少 interval_days")
        return todo.task_date + timedelta(days=todo.interval_days * offset)

    raise ValueError(f"不支持的循环类型：{todo.recurrence_type}")


def build_reminder_cycle(todo: Todo, sequence: int) -> ReminderCycle:
    target_date = get_cycle_target_date(todo, sequence)
    reminder_start_date = target_date - timedelta(days=todo.remind_days_before)
    return ReminderCycle(
        todo_id=todo.id,
        user_id=todo.user_id,
        sequence=sequence,
        target_date=target_date,
        reminder_start_date=reminder_start_date,
        reminder_end_date=target_date,
    )


def build_initial_reminder_cycles(todo: Todo) -> list[ReminderCycle]:
    if todo.id is None:
        raise ValueError("创建提醒周期前必须先保存待办事项")

    return [
        build_reminder_cycle(todo, sequence)
        for sequence in range(1, get_cycle_count(todo) + 1)
    ]


def get_today() -> date:
    return datetime.now(ZoneInfo(settings.scheduler_timezone)).date()


def is_cycle_due(cycle: ReminderCycle, today: date) -> bool:
    return (
        cycle.status == ReminderCycleStatus.PENDING
        and cycle.reminder_start_date <= today <= cycle.reminder_end_date
    )


def has_email_log_for_cycle(session: Session, reminder_cycle_id: int, sent_date: date) -> bool:
    stmt = select(EmailLog.id).where(
        EmailLog.reminder_cycle_id == reminder_cycle_id,
        EmailLog.sent_date == sent_date,
    )
    return session.exec(stmt).first() is not None


def create_email_log(
    session: Session,
    *,
    todo: Todo,
    cycle: ReminderCycle,
    subject: str,
    body_text: str,
    sent_date: date,
    success: bool,
    error_message: str | None = None,
) -> EmailLog:
    email_log = EmailLog(
        todo_id=todo.id,
        reminder_cycle_id=cycle.id,
        user_id=todo.user_id,
        recipient_email=todo.recipient_email,
        subject=subject,
        body_text=body_text,
        status=EmailLogStatus.SUCCESS if success else EmailLogStatus.FAILED,
        error_message=error_message,
        sent_date=sent_date,
        sent_at=datetime.now(timezone.utc),
    )
    session.add(email_log)
    session.commit()
    session.refresh(email_log)
    return email_log


def scan_due_reminders(session: Session | None = None, today: date | None = None) -> int:
    if session is None:
        from app.db.session import engine

        with Session(engine) as managed_session:
            return scan_due_reminders(managed_session, today)

    current_date = today or get_today()
    sent_count = 0

    stmt = (
        select(ReminderCycle, Todo)
        .join(Todo, ReminderCycle.todo_id == Todo.id)
        .where(Todo.is_active.is_(True))
        .order_by(ReminderCycle.target_date, ReminderCycle.sequence)
    )

    for cycle, todo in session.exec(stmt).all():
        if cycle.id is None or todo.id is None:
            continue

        if not is_cycle_due(cycle, current_date):
            continue

        if has_email_log_for_cycle(session, cycle.id, current_date):
            continue

        subject, body_text = build_reminder_email(todo, cycle)
        result = send_email(todo.recipient_email, subject, body_text)
        create_email_log(
            session,
            todo=todo,
            cycle=cycle,
            subject=subject,
            body_text=body_text,
            sent_date=current_date,
            success=result.success,
            error_message=result.error_message,
        )

        if result.success:
            sent_count += 1

    return sent_count
