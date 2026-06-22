from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, select

from app.api.deps import CurrentUserDep, SessionDep
from app.models.email_log import EmailLog, EmailLogStatus
from app.models.reminder_cycle import ReminderCycle, ReminderCycleStatus
from app.models.todo import CalendarType, RecurrenceType
from app.models.todo import Todo
from app.schemas.email_log import EmailLogResponse
from app.schemas.reminder_cycle import ReminderCycleResponse
from app.schemas.todo import (
    TodoCreateRequest,
    TodoUpdateRequest,
    TodoResponse,
    TodoPreviewItem,
    DateConversionRequest,
    DateConversionResponse,
    TestEmailResponse,
)
from app.schemas.todo_text_parse_result import (
    TodoTextParseRequest,
    TodoTextParseResponse,
)
from app.services.calendar import lunar_to_solar, solar_to_lunar
from app.services.email_sender import send_email
from app.services.llm import LLMConfigError
from app.services.reminder_engine import (
    build_initial_reminder_cycles,
    get_today,
    get_cycle_count,
    get_cycle_target_date,
)
from app.services.todo_text_parser import TodoTextParseError, parse_todo_text

router = APIRouter()


SCHEDULE_FIELDS = {
    "calendar_type",
    "task_date",
    "lunar_month",
    "lunar_day",
    "lunar_is_leap_month",
    "remind_days_before",
    "recurrence_type",
    "interval_days",
    "repeat_count",
}


def has_any_email_log(session: Session, cycle_id: int | None) -> bool:
    if cycle_id is None:
        return False

    return session.exec(
        select(EmailLog.id).where(EmailLog.reminder_cycle_id == cycle_id)
    ).first() is not None


def rebuild_editable_cycles(session: Session, todo: Todo) -> None:
    cycles = session.exec(
        select(ReminderCycle)
        .where(ReminderCycle.todo_id == todo.id)
        .order_by(ReminderCycle.sequence)
    ).all()
    protected_sequences = set()

    for cycle in cycles:
        if (
            cycle.status != ReminderCycleStatus.PENDING
            or has_any_email_log(session, cycle.id)
        ):
            protected_sequences.add(cycle.sequence)
            continue

        session.delete(cycle)

    session.flush()

    for cycle in build_initial_reminder_cycles(todo):
        if cycle.sequence in protected_sequences:
            continue
        session.add(cycle)


@router.post(
    "/",
    response_model=TodoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建待办事项",
    description="创建当前登录用户的待办事项，支持阳历/农历、提前提醒天数和循环规则。",
)
def create_todo(
    payload: TodoCreateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Todo:
    lunar_month = payload.lunar_month
    lunar_day = payload.lunar_day
    lunar_is_leap_month = payload.lunar_is_leap_month

    if payload.calendar_type == CalendarType.LUNAR:
        lunar_rule = solar_to_lunar(payload.task_date)
        if lunar_month is None and lunar_day is None:
            lunar_month = lunar_rule.month
            lunar_day = lunar_rule.day
            lunar_is_leap_month = lunar_rule.is_leap_month
        elif lunar_month is None or lunar_day is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="农历任务需要同时填写 lunar_month 和 lunar_day",
            )
        else:
            try:
                solar_date = lunar_to_solar(
                    payload.task_date.year,
                    lunar_month,
                    lunar_day,
                    lunar_is_leap_month,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

            if solar_date != payload.task_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="task_date 与填写的农历日期不匹配",
                )

    todo = Todo(
        user_id=current_user.id,
        description=payload.description,
        recipient_email=str(payload.recipient_email).lower(),
        calendar_type=payload.calendar_type,
        task_date=payload.task_date,
        lunar_month=lunar_month,
        lunar_day=lunar_day,
        lunar_is_leap_month=lunar_is_leap_month,
        remind_days_before=payload.remind_days_before,
        recurrence_type=payload.recurrence_type,
        interval_days=payload.interval_days,
        repeat_count=payload.repeat_count,
    )
    session.add(todo)
    session.commit()
    session.refresh(todo)

    cycles = build_initial_reminder_cycles(todo)
    session.add_all(cycles)
    session.commit()

    return todo


@router.post(
    "/parse-text",
    response_model=TodoTextParseResponse,
    summary="从自然语言解析待办事项",
    description="使用 OpenAI 协议兼容的大模型把用户输入文本解析为待办事项草稿，不写入数据库。",
)
async def parse_todo_from_text(
    payload: TodoTextParseRequest,
    current_user: CurrentUserDep,
) -> TodoTextParseResponse:
    try:
        result = await parse_todo_text(
            payload.text,
            default_recipient_email=current_user.email,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except LLMConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM 服务未配置，请检查 OPENAI_API_KEY",
        ) from exc
    except TodoTextParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="暂时无法解析这段提醒文本，请稍后重试或手动填写",
        ) from exc

    response_status = "needs_clarification" if result.missing_fields else "parsed"
    return TodoTextParseResponse(status=response_status, result=result)


@router.post(
    "/preview",
    response_model=list[TodoPreviewItem],
    summary="预览提醒周期",
    description="根据提交的提醒设置预览未来周期的起止日期与农历信息（不存入数据库）。",
)
def preview_todo(
    payload: TodoCreateRequest,
    current_user: CurrentUserDep,
) -> list[TodoPreviewItem]:
    lunar_month = payload.lunar_month
    lunar_day = payload.lunar_day
    lunar_is_leap_month = payload.lunar_is_leap_month

    if payload.calendar_type == CalendarType.LUNAR:
        lunar_rule = solar_to_lunar(payload.task_date)
        if lunar_month is None and lunar_day is None:
            lunar_month = lunar_rule.month
            lunar_day = lunar_rule.day
            lunar_is_leap_month = lunar_rule.is_leap_month
        elif lunar_month is None or lunar_day is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="农历任务需要同时填写 lunar_month 和 lunar_day",
            )
        else:
            try:
                solar_date = lunar_to_solar(
                    payload.task_date.year,
                    lunar_month,
                    lunar_day,
                    lunar_is_leap_month,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

            if solar_date != payload.task_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="task_date 与填写的农历日期不匹配",
                )

    todo = Todo(
        user_id=current_user.id,
        description=payload.description,
        recipient_email=str(payload.recipient_email).lower(),
        calendar_type=payload.calendar_type,
        task_date=payload.task_date,
        lunar_month=lunar_month,
        lunar_day=lunar_day,
        lunar_is_leap_month=lunar_is_leap_month,
        remind_days_before=payload.remind_days_before,
        recurrence_type=payload.recurrence_type,
        interval_days=payload.interval_days,
        repeat_count=payload.repeat_count,
    )

    def get_lunar_name(m: int, d: int, is_leap: bool) -> str:
        m_names = ["", "正月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "腊月"]
        m_str = m_names[m] if 1 <= m <= 12 else f"{m}月"
        if is_leap:
            m_str = f"闰{m_str}"
            
        if d <= 10:
            d_names = ["", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十"]
            d_str = d_names[d]
        elif d < 20:
            d_names = ["", "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九"]
            d_str = d_names[d - 10]
        elif d == 20:
            d_str = "二十"
        elif d < 30:
            d_names = ["", "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九"]
            d_str = d_names[d - 20]
        elif d == 30:
            d_str = "三十"
        else:
            d_str = f"{d}日"
            
        return f"{m_str}{d_str}"

    preview_items = []
    # Cap preview to a maximum of 100 items to prevent server overhead and client DOM overload
    count = min(get_cycle_count(todo), 100)
    for seq in range(1, count + 1):
        target_date = get_cycle_target_date(todo, seq)
        l_rule = solar_to_lunar(target_date)
        lunar_str = f"{l_rule.year}年{get_lunar_name(l_rule.month, l_rule.day, l_rule.is_leap_month)}"
        
        preview_items.append(
            TodoPreviewItem(
                sequence=seq,
                solar_date=target_date,
                lunar_date=lunar_str,
                lunar_month=l_rule.month,
                lunar_day=l_rule.day,
                lunar_is_leap_month=l_rule.is_leap_month,
                reminder_start_date=target_date - timedelta(days=todo.remind_days_before),
                reminder_end_date=target_date,
            )
        )

    return preview_items


@router.post(
    "/convert-date",
    response_model=DateConversionResponse,
    summary="公农历日期双向转换",
    description="支持公历转农历，或农历转公历，并返回中文字符格式描述。",
)
def convert_date(
    payload: DateConversionRequest,
    current_user: CurrentUserDep,
) -> DateConversionResponse:
    def get_lunar_name(m: int, d: int, is_leap: bool) -> str:
        m_names = ["", "正月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "腊月"]
        m_str = m_names[m] if 1 <= m <= 12 else f"{m}月"
        if is_leap:
            m_str = f"闰{m_str}"
            
        if d <= 10:
            d_names = ["", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十"]
            d_str = d_names[d]
        elif d < 20:
            d_names = ["", "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九"]
            d_str = d_names[d - 10]
        elif d == 20:
            d_str = "二十"
        elif d < 30:
            d_names = ["", "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九"]
            d_str = d_names[d - 20]
        elif d == 30:
            d_str = "三十"
        else:
            d_str = f"{d}日"
            
        return f"{m_str}{d_str}"

    if payload.calendar_type == CalendarType.SOLAR:
        if not payload.solar_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="公历转换模式下必须提供 solar_date",
            )
        l_rule = solar_to_lunar(payload.solar_date)
        lunar_str = f"{l_rule.year}年{get_lunar_name(l_rule.month, l_rule.day, l_rule.is_leap_month)}"
        solar_str = f"{payload.solar_date.year}年{payload.solar_date.month}月{payload.solar_date.day}日"
        return DateConversionResponse(
            solar_date=payload.solar_date,
            lunar_year=l_rule.year,
            lunar_month=l_rule.month,
            lunar_day=l_rule.day,
            lunar_is_leap_month=l_rule.is_leap_month,
            lunar_date_str=lunar_str,
            solar_date_str=solar_str,
        )
    else:  # LUNAR
        if payload.lunar_month is None or payload.lunar_day is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="农历转换模式下必须提供 lunar_month 和 lunar_day",
            )
        from datetime import datetime
        year = payload.lunar_year if payload.lunar_year else datetime.now().year
        try:
            solar_date = lunar_to_solar(
                year,
                payload.lunar_month,
                payload.lunar_day,
                payload.lunar_is_leap_month,
            )
        except ValueError as exc:
            try:
                # If calculations fail in the current year, check next year
                year += 1
                solar_date = lunar_to_solar(
                    year,
                    payload.lunar_month,
                    payload.lunar_day,
                    payload.lunar_is_leap_month,
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                )
        
        lunar_str = f"{year}年{get_lunar_name(payload.lunar_month, payload.lunar_day, payload.lunar_is_leap_month)}"
        solar_str = f"{solar_date.year}年{solar_date.month}月{solar_date.day}日"
        return DateConversionResponse(
            solar_date=solar_date,
            lunar_year=year,
            lunar_month=payload.lunar_month,
            lunar_day=payload.lunar_day,
            lunar_is_leap_month=payload.lunar_is_leap_month,
            lunar_date_str=lunar_str,
            solar_date_str=solar_str,
        )


@router.get(
    "/",
    response_model=list[TodoResponse],
    summary="获取待办事项列表",
    description="获取当前登录用户创建的待办事项列表。",
)
def list_todos(session: SessionDep, current_user: CurrentUserDep) -> list[Todo]:
    return list(
        session.exec(
            select(Todo)
            .where(Todo.user_id == current_user.id)
            .order_by(Todo.created_at.desc())
        )
    )


@router.get(
    "/{todo_id}",
    response_model=TodoResponse,
    summary="获取待办事项详情",
    description="获取当前登录用户的单个待办事项详情。",
)
def get_todo(
    todo_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Todo:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )
    return todo


@router.patch(
    "/{todo_id}",
    response_model=TodoResponse,
    summary="编辑待办事项",
    description="编辑当前登录用户的待办事项。修改提醒规则后，会重建尚未发送、尚未完成的提醒周期。",
)
def update_todo(
    todo_id: int,
    payload: TodoUpdateRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Todo:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return todo

    calendar_type = updates.get("calendar_type", todo.calendar_type)
    task_date = updates.get("task_date", todo.task_date)
    lunar_month = updates.get("lunar_month", todo.lunar_month)
    lunar_day = updates.get("lunar_day", todo.lunar_day)
    lunar_is_leap_month = updates.get(
        "lunar_is_leap_month",
        todo.lunar_is_leap_month,
    )
    recurrence_type = updates.get("recurrence_type", todo.recurrence_type)
    interval_days = updates.get("interval_days", todo.interval_days)

    if calendar_type == CalendarType.LUNAR:
        should_auto_fill_lunar_rule = (
            ("calendar_type" in updates or "task_date" in updates)
            and "lunar_month" not in updates
            and "lunar_day" not in updates
        )
        if should_auto_fill_lunar_rule or (lunar_month is None and lunar_day is None):
            lunar_rule = solar_to_lunar(task_date)
            lunar_month = lunar_rule.month
            lunar_day = lunar_rule.day
            lunar_is_leap_month = lunar_rule.is_leap_month
        elif lunar_month is None or lunar_day is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="农历任务需要同时填写 lunar_month 和 lunar_day",
            )
        else:
            try:
                solar_date = lunar_to_solar(
                    task_date.year,
                    lunar_month,
                    lunar_day,
                    bool(lunar_is_leap_month),
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc

            if solar_date != task_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="task_date 与填写的农历日期不匹配",
                )
    else:
        lunar_month = None
        lunar_day = None
        lunar_is_leap_month = False

    if recurrence_type == RecurrenceType.INTERVAL_DAYS:
        if interval_days is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="按天间隔循环时必须填写 interval_days",
            )
    else:
        interval_days = None

    if "description" in updates:
        todo.description = updates["description"]
    if "recipient_email" in updates:
        todo.recipient_email = str(updates["recipient_email"]).lower()

    todo.calendar_type = calendar_type
    todo.task_date = task_date
    todo.lunar_month = lunar_month
    todo.lunar_day = lunar_day
    todo.lunar_is_leap_month = bool(lunar_is_leap_month)
    if "remind_days_before" in updates:
        todo.remind_days_before = updates["remind_days_before"]
    todo.recurrence_type = recurrence_type
    todo.interval_days = interval_days
    if "repeat_count" in updates:
        todo.repeat_count = updates["repeat_count"]
    if "is_active" in updates:
        todo.is_active = updates["is_active"]

    todo.updated_at = datetime.now(timezone.utc)
    session.add(todo)
    session.flush()

    if SCHEDULE_FIELDS.intersection(updates):
        rebuild_editable_cycles(session, todo)

    session.commit()
    session.refresh(todo)
    return todo


@router.get(
    "/{todo_id}/cycles",
    response_model=list[ReminderCycleResponse],
    summary="获取待办事项提醒周期",
    description="获取当前登录用户某个待办事项已经生成的提醒周期列表。",
)
def list_todo_cycles(
    todo_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> list[ReminderCycle]:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )

    return list(
        session.exec(
            select(ReminderCycle)
            .where(ReminderCycle.todo_id == todo_id)
            .order_by(ReminderCycle.sequence)
        )
    )


@router.post(
    "/{todo_id}/cycles/{cycle_id}/complete",
    response_model=ReminderCycleResponse,
    summary="标记本轮提醒完成",
    description="当某个提醒周期已经成功发送邮件后，将该周期标记为完成，停止本轮后续提醒。",
)
def complete_todo_cycle(
    todo_id: int,
    cycle_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ReminderCycle:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )

    cycle = session.get(ReminderCycle, cycle_id)
    if (
        cycle is None
        or cycle.todo_id != todo_id
        or cycle.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="提醒周期不存在",
        )

    if cycle.status == ReminderCycleStatus.COMPLETED:
        return cycle

    if cycle.status != ReminderCycleStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前提醒周期不是待完成状态",
        )

    sent_log_id = session.exec(
        select(EmailLog.id).where(
            EmailLog.reminder_cycle_id == cycle_id,
            EmailLog.status == EmailLogStatus.SUCCESS,
        )
    ).first()
    if sent_log_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前提醒周期还没有成功发送邮件，不能标记为完成",
        )

    now = datetime.now(timezone.utc)
    cycle.status = ReminderCycleStatus.COMPLETED
    cycle.completed_at = now
    cycle.updated_at = now
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    return cycle


@router.get(
    "/{todo_id}/email-logs",
    response_model=list[EmailLogResponse],
    summary="获取待办事项邮件发送日志",
    description="获取当前登录用户某个待办事项的邮件发送记录，支持分页和按提醒周期筛选。",
)
def list_todo_email_logs(
    todo_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    cycle_id: int | None = Query(default=None, description="提醒周期 ID"),
    limit: int = Query(default=100, ge=1, le=500, description="返回数量"),
    offset: int = Query(default=0, ge=0, description="跳过数量"),
) -> list[EmailLog]:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )

    stmt = select(EmailLog).where(
        EmailLog.todo_id == todo_id,
        EmailLog.user_id == current_user.id,
    )

    if cycle_id is not None:
        cycle = session.get(ReminderCycle, cycle_id)
        if (
            cycle is None
            or cycle.todo_id != todo_id
            or cycle.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="提醒周期不存在",
            )
        stmt = stmt.where(EmailLog.reminder_cycle_id == cycle_id)

    return list(
        session.exec(
            stmt.order_by(EmailLog.sent_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )


@router.post(
    "/{todo_id}/test-email",
    response_model=TestEmailResponse,
    summary="发送待办测试邮件",
    description="向待办事项配置的收件邮箱发送一封测试邮件，不写入正式邮件发送日志。",
)
def send_todo_test_email(
    todo_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> TestEmailResponse:
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )

    today = get_today()
    cycle = session.exec(
        select(ReminderCycle)
        .where(
            ReminderCycle.todo_id == todo_id,
            ReminderCycle.user_id == current_user.id,
            ReminderCycle.status == ReminderCycleStatus.PENDING,
            ReminderCycle.reminder_end_date >= today,
        )
        .order_by(ReminderCycle.reminder_start_date, ReminderCycle.sequence)
    ).first()
    if cycle is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前待办事项没有可用于测试的未来提醒周期",
        )

    subject = f"RemindFlow 测试邮件：{todo.description}"
    body_text = "\n".join(
        [
            "这是一封测试邮件，用于确认邮箱发送配置是否正常。",
            "",
            f"任务：{todo.description}",
            f"收件人：{todo.recipient_email}",
            f"最近一次提醒窗口将在 {cycle.reminder_start_date.isoformat()} 开启。",
            f"本轮目标日期：{cycle.target_date.isoformat()}",
            "",
            "如果你收到了这封邮件，说明当前待办事项的邮箱发送功能可以正常使用。",
        ]
    )
    result = send_email(todo.recipient_email, subject, body_text)

    return TestEmailResponse(
        success=result.success,
        message="测试邮件发送成功" if result.success else "测试邮件发送失败",
        recipient_email=todo.recipient_email,
        subject=subject,
        reminder_cycle_id=cycle.id,
        reminder_start_date=cycle.reminder_start_date,
        reminder_end_date=cycle.reminder_end_date,
        target_date=cycle.target_date,
        error_message=result.error_message,
    )


@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除待办事项",
    description="删除用户的待办事项以及关联的提醒周期。",
)
def delete_todo(
    todo_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    todo = session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="待办事项不存在",
        )
    email_logs = session.exec(
        select(EmailLog).where(EmailLog.todo_id == todo_id)
    ).all()
    for email_log in email_logs:
        session.delete(email_log)

    cycles = session.exec(
        select(ReminderCycle).where(ReminderCycle.todo_id == todo_id)
    ).all()
    for cycle in cycles:
        session.delete(cycle)
    session.delete(todo)
    session.commit()
    return None
