from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.core.config import settings
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.services.email_sender import EmailSendResult


def test_register_user_success(client: TestClient, session: Session):
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert data["is_active"] is True

    # Verify user exists in db
    db_user = session.exec(select(User).where(User.email == "test@example.com")).first()
    assert db_user is not None
    assert db_user.email == "test@example.com"


def test_register_duplicate_user_fails(client: TestClient):
    # First registration
    client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "password123"},
    )
    # Second registration with same email
    response = client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "password1234"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "该邮箱已经注册" in response.json()["detail"]


def test_register_invalid_email_or_password_fails(client: TestClient):
    # Test invalid email format
    response = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test password too short
    response = client.post(
        "/auth/register",
        json={"email": "short@example.com", "password": "123"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_register_requires_verification_code_when_enabled(
    client: TestClient,
    monkeypatch,
):
    monkeypatch.setattr(settings, "registration_email_verification_required", True)

    response = client.post(
        "/auth/register",
        json={"email": "need-code@example.com", "password": "password123"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "邮箱验证码" in response.json()["detail"]


def test_send_verification_code_and_register_success(
    client: TestClient,
    session: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "registration_email_verification_required", True)
    monkeypatch.setattr(
        "app.api.routes.auth.generate_verification_code",
        lambda: "123456",
    )
    monkeypatch.setattr(
        "app.api.routes.auth.send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )

    send_response = client.post(
        "/auth/send-verification-code",
        json={"email": "verified@example.com"},
    )
    assert send_response.status_code == status.HTTP_200_OK
    assert send_response.json()["message"] == "验证码已发送"

    register_response = client.post(
        "/auth/register",
        json={
            "email": "verified@example.com",
            "password": "password123",
            "verification_code": "123456",
        },
    )
    assert register_response.status_code == status.HTTP_201_CREATED
    assert register_response.json()["email"] == "verified@example.com"

    code_record = session.exec(
        select(EmailVerificationCode).where(
            EmailVerificationCode.email == "verified@example.com"
        )
    ).first()
    assert code_record is not None
    assert code_record.consumed_at is not None


def test_register_wrong_verification_code_fails(
    client: TestClient,
    session: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "registration_email_verification_required", True)
    monkeypatch.setattr(
        "app.api.routes.auth.generate_verification_code",
        lambda: "123456",
    )
    monkeypatch.setattr(
        "app.api.routes.auth.send_email",
        lambda recipient_email, subject, body_text: EmailSendResult(True),
    )

    client.post(
        "/auth/send-verification-code",
        json={"email": "wrong-code@example.com"},
    )
    response = client.post(
        "/auth/register",
        json={
            "email": "wrong-code@example.com",
            "password": "password123",
            "verification_code": "654321",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "验证码错误" in response.json()["detail"]
    code_record = session.exec(
        select(EmailVerificationCode).where(
            EmailVerificationCode.email == "wrong-code@example.com"
        )
    ).first()
    assert code_record is not None
    assert code_record.attempts == 1


def test_login_success(client: TestClient):
    # Register first
    client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )

    # Login
    response = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_credentials_fails(client: TestClient):
    # Register
    client.post(
        "/auth/register",
        json={"email": "wrong@example.com", "password": "password123"},
    )

    # Login with wrong password
    response = client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "邮箱或密码错误" in response.json()["detail"]

    # Login with non-existing email
    response = client.post(
        "/auth/login",
        json={"email": "nonexist@example.com", "password": "password123"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "邮箱或密码错误" in response.json()["detail"]


def test_get_current_user_me_success(client: TestClient):
    # Register & Login
    client.post(
        "/auth/register",
        json={"email": "me@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "me@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Get /me with valid token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "me@example.com"


def test_get_current_user_me_unauthorized(client: TestClient):
    # Without token
    response = client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # With invalid token
    headers = {"Authorization": "Bearer invalidtoken"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_change_password_success(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "change@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "change@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        json={"old_password": "password123", "new_password": "newpassword123"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "密码已修改"

    old_login_response = client.post(
        "/auth/login",
        json={"email": "change@example.com", "password": "password123"},
    )
    assert old_login_response.status_code == status.HTTP_401_UNAUTHORIZED

    new_login_response = client.post(
        "/auth/login",
        json={"email": "change@example.com", "password": "newpassword123"},
    )
    assert new_login_response.status_code == status.HTTP_200_OK


def test_change_password_wrong_old_password_fails(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "wrong-old@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "wrong-old@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        json={"old_password": "wrongpassword", "new_password": "newpassword123"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "旧密码错误" in response.json()["detail"]


def test_change_password_unauthorized_fails(client: TestClient):
    response = client.post(
        "/auth/change-password",
        json={"old_password": "password123", "new_password": "newpassword123"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_change_password_same_password_fails(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "same-password@example.com", "password": "password123"},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": "same-password@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        json={"old_password": "password123", "new_password": "password123"},
        headers=headers,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "新密码不能和旧密码相同" in response.json()["detail"]
