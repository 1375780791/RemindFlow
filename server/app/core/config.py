from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RemindFlow"
    database_url: str = "sqlite:///data/remindflow.db"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 60 * 24 * 30
    default_generated_cycle_count: int = 12

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 10
    registration_email_verification_required: bool = True
    email_verification_code_expires_minutes: int = 10
    email_verification_code_cooldown_seconds: int = 60
    email_verification_max_attempts: int = 5

    scheduler_timezone: str = "Asia/Shanghai"
    reminder_scan_hour: int = 8
    reminder_scan_minute: int = 0

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_temperature: float = 0.2
    openai_max_tokens: int = 1024
    llm_debug_log_enabled: bool = False
    llm_debug_log_path: str = "logs/llm_debug.log"

    model_config = SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
