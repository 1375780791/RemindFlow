from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_bcrypt_password_length(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("密码不能超过 72 字节，请缩短密码长度")
    return password


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    verification_code: str | None = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )

    @field_validator("password")
    @classmethod
    def password_must_fit_bcrypt_limit(cls, password: str) -> str:
        return validate_bcrypt_password_length(password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def password_must_fit_bcrypt_limit(cls, password: str) -> str:
        return validate_bcrypt_password_length(password)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("old_password", "new_password")
    @classmethod
    def password_must_fit_bcrypt_limit(cls, password: str) -> str:
        return validate_bcrypt_password_length(password)


class SendVerificationCodeRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime
