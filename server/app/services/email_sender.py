from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from app.core.config import settings
from app.models.reminder_cycle import ReminderCycle
from app.models.todo import Todo


@dataclass(slots=True)
class EmailSendResult:
    success: bool
    error_message: str | None = None


def build_reminder_email(todo: Todo, cycle: ReminderCycle) -> tuple[str, str]:
    subject = f"RemindFlow 提醒：{todo.description}"
    body_lines = [
        "你有一条待办提醒：",
        "",
        f"任务：{todo.description}",
        f"收件人：{todo.recipient_email}",
        f"目标日期：{cycle.target_date.isoformat()}",
        f"提醒窗口：{cycle.reminder_start_date.isoformat()} 至 {cycle.reminder_end_date.isoformat()}",
        f"循环序号：第 {cycle.sequence} 轮",
        "",
        "请尽快处理。",
    ]
    return subject, "\n".join(body_lines)


def send_email(recipient_email: str, subject: str, body_text: str) -> EmailSendResult:
    if not settings.smtp_host:
        return EmailSendResult(False, "SMTP 主机未配置")

    from_email = settings.smtp_from or settings.smtp_username
    if not from_email:
        return EmailSendResult(False, "SMTP 发件人未配置")

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body_text, charset="utf-8")

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - depends on external SMTP
        return EmailSendResult(False, str(exc))

    return EmailSendResult(True)
