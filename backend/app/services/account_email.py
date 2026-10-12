import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def email_enabled() -> bool:
    return settings.email_provider == "smtp"


def send_account_email(recipient: str, purpose: str, link: str) -> None:
    """Run as a response background task; never log recipients, links, or credentials."""
    action = "Reset your password" if purpose == "reset" else "Verify your email"
    duration = f"{settings.auth_reset_minutes} minutes" if purpose == "reset" else (
        f"{settings.auth_verify_hours} hours"
    )
    try:
        message = EmailMessage()
        message["From"] = settings.email_from
        message["To"] = recipient
        message["Subject"] = f"StudyBot: {action}"
        message.set_content(
            f"{action} for your StudyBot account:\n\n{link}\n\n"
            f"This single-use link expires in {duration}. "
            "If you did not request it, you can ignore this email.\n"
        )
        context = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=settings.smtp_timeout_seconds,
                                  context=context) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, 587,
                              timeout=settings.smtp_timeout_seconds) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException, UnicodeError, ValueError):
        logger.warning("Account email delivery failed; check sender configuration and service logs")
