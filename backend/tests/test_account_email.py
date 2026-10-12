import smtplib

import pytest
from app.core.config import Settings, settings
from app.services.account_email import send_account_email


@pytest.mark.parametrize("port", [465, 587])
def test_smtp_uses_tls_and_sends_plain_text_link(monkeypatch, port):
    operations = []

    class SMTP:
        def __init__(self, host, port, **kwargs):
            operations.append(("connect", port, kwargs))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, **kwargs): operations.append(("tls", kwargs))
        def login(self, *args): operations.append(("login",))
        def send_message(self, message): operations.append(("message", message))

    monkeypatch.setattr(settings, "smtp_port", port)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "email_from", "sender@example.com")
    monkeypatch.setattr(smtplib, "SMTP_SSL" if port == 465 else "SMTP", SMTP)
    send_account_email("student@example.com", "reset", "https://study.example/#reset=secret")
    assert operations[0][2]["timeout"] <= 10
    assert operations[0][2].get("context") or any(op[0] == "tls" for op in operations)
    assert operations[-1][1]["To"] == "student@example.com"
    assert "#reset=secret" in operations[-1][1].get_content()


def test_smtp_failure_does_not_log_sensitive_details(monkeypatch, caplog):
    def failure(*args, **kwargs):
        raise smtplib.SMTPException("secret token and recipient")
    monkeypatch.setattr(settings, "email_from", "sender@example.com")
    monkeypatch.setattr(smtplib, "SMTP_SSL", failure)
    send_account_email("private@example.com", "verify", "https://study.example/#verify=secret")
    assert "delivery failed" in caplog.text
    assert "private@example.com" not in caplog.text and "secret token" not in caplog.text


def test_email_configuration_rejects_insecure_or_incomplete_settings():
    with pytest.raises(ValueError):
        Settings(_env_file=None, email_provider="smtp")
    with pytest.raises(ValueError):
        Settings(_env_file=None, auth_require_email_verification=True)
    with pytest.raises(ValueError):
        Settings(_env_file=None, public_app_url="https://evil.example/?redirect=another")
