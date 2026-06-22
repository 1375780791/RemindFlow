import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db.session import get_session
from app.core.config import settings
from app.models import EmailLog, EmailVerificationCode, ReminderCycle, Todo, User  # Import models to register SQLModel metadata


@pytest.fixture(autouse=True)
def disable_email_verification_by_default(monkeypatch):
    monkeypatch.setattr(settings, "registration_email_verification_required", False)

@pytest.fixture(name="session")
def session_fixture():
    # Use StaticPool to share in-memory database across connections in a single thread
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "todo_user@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "todo_user@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
