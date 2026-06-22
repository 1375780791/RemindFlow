from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, Integer, Text
from sqlmodel import Field, SQLModel


class EmailVerificationPurpose(str, Enum):
    REGISTER = "register"


class EmailVerificationCode(SQLModel, table=True):
    __tablename__ = "email_verification_codes"

    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
    )
    email: str = Field(max_length=255, index=True)
    purpose: EmailVerificationPurpose = Field(index=True)
    code_hash: str = Field(sa_column=Column(Text))
    expires_at: datetime = Field(index=True)
    consumed_at: datetime | None = Field(default=None, index=True)
    attempts: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
