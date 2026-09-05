from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    pass


def send_email(subject: str, recipient: str, body: str, html: Optional[str] = None) -> None:
    settings = get_settings()

    # If SMTP is not configured, log an error and raise so the server logs a clear failure.
    if not settings.smtp_host or not settings.email_from:
        logger.error(
            "SMTP is not configured; verification/reset emails will not be sent. Required envs: SMTP_HOST, EMAIL_FROM. Subject=%s Recipient=%s",
            subject,
            recipient,
        )
        raise EmailServiceError("SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = recipient
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port or 587)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port or 25)

        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)

        server.send_message(msg)
        server.quit()
    except Exception as exc:
        logger.exception("Failed to send email to %s: %s", recipient, exc)
        raise EmailServiceError("Failed to send email") from exc
