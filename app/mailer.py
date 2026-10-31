import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("mailer")


def send_email(to: str, subject: str, body: str) -> None:
    """Sends via SMTP (Mailpit locally). If no SMTP server is reachable the message is logged,
    so billing and auth flows never fail because mail is down."""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(msg)
    except OSError as exc:
        log.warning("SMTP unavailable (%s). Email to %s logged instead:\n%s\n%s", exc, to, subject, body)
