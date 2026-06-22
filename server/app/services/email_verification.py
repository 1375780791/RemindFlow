from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from app.core.config import settings
from app.models.email_verification_code import EmailVerificationPurpose


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(
    *,
    email: str,
    purpose: EmailVerificationPurpose,
    code: str,
) -> str:
    payload = f"{email.lower()}:{purpose.value}:{code}:{settings.secret_key}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_verification_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.email_verification_code_expires_minutes
    )


def build_verification_email(code: str) -> tuple[str, str]:
    subject = "RemindFlow 注册验证码"
    body_text = "\n".join(
        [
            "你正在注册 RemindFlow。",
            "",
            f"验证码：{code}",
            f"有效期：{settings.email_verification_code_expires_minutes} 分钟",
            "",
            "如果这不是你本人操作，可以忽略这封邮件。",
        ]
    )
    return subject, body_text
