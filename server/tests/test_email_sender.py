from email.message import EmailMessage

from app.services import email_sender


class FakeSMTP:
    instances = []

    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args = None
        self.sent_message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username: str, password: str):
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage):
        self.sent_message = message


class FakeSMTPSSL(FakeSMTP):
    instances = []


def configure_smtp_settings(monkeypatch, *, use_ssl: bool, use_tls: bool):
    monkeypatch.setattr(email_sender.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(email_sender.settings, "smtp_port", 465 if use_ssl else 587)
    monkeypatch.setattr(email_sender.settings, "smtp_username", "sender@example.com")
    monkeypatch.setattr(email_sender.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_sender.settings, "smtp_from", "sender@example.com")
    monkeypatch.setattr(email_sender.settings, "smtp_use_ssl", use_ssl)
    monkeypatch.setattr(email_sender.settings, "smtp_use_tls", use_tls)
    monkeypatch.setattr(email_sender.settings, "smtp_timeout_seconds", 12)


def test_send_email_uses_smtp_ssl(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTPSSL.instances = []
    configure_smtp_settings(monkeypatch, use_ssl=True, use_tls=False)
    monkeypatch.setattr(email_sender.smtplib, "SMTP_SSL", FakeSMTPSSL)

    result = email_sender.send_email(
        "recipient@example.com",
        "测试主题",
        "测试正文",
    )

    assert result.success is True
    assert FakeSMTPSSL.instances
    smtp = FakeSMTPSSL.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 465
    assert smtp.timeout == 12
    assert smtp.started_tls is False
    assert smtp.login_args == ("sender@example.com", "secret")
    assert smtp.sent_message["To"] == "recipient@example.com"


def test_send_email_uses_starttls(monkeypatch):
    FakeSMTP.instances = []
    FakeSMTPSSL.instances = []
    configure_smtp_settings(monkeypatch, use_ssl=False, use_tls=True)
    monkeypatch.setattr(email_sender.smtplib, "SMTP", FakeSMTP)

    result = email_sender.send_email(
        "recipient@example.com",
        "测试主题",
        "测试正文",
    )

    assert result.success is True
    assert FakeSMTP.instances
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.login_args == ("sender@example.com", "secret")
    assert smtp.sent_message["Subject"] == "测试主题"
