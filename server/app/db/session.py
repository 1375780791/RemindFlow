from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from app.models import (  # noqa: F401
        email_log,
        email_verification_code,
        reminder_cycle,
        todo,
        user,
    )

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
