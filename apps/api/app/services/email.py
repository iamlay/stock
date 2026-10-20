from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.settings import settings

logger = logging.getLogger(__name__)


class EmailNotConfigured(RuntimeError):
    pass


class EmailSendError(RuntimeError):
    pass


def send_email(to: str, subject: str, body: str) -> None:
    if settings.auth_dev_mode:
        logger.info("email dev mode to=%s subject=%s body=%s", to, subject, body)
        return
    if not settings.email_configured:
        raise EmailNotConfigured("SMTP is not configured")

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        if settings.smtp_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15
            ) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.exception("failed to send email to %s", to)
        raise EmailSendError("email delivery failed") from exc


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url.rstrip('/')}/verify-email?token={quote(token)}"
    send_email(
        to,
        "验证你的 StockLab 邮箱",
        (
            "欢迎使用 StockLab。\n\n"
            "点击下面的链接验证邮箱（24 小时内有效）：\n\n"
            f"{link}\n\n"
            "如果这不是你的操作，请忽略这封邮件。\n"
        ),
    )


def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={quote(token)}"
    send_email(
        to,
        "重置你的 StockLab 密码",
        (
            "我们收到了重置密码的请求。\n\n"
            "点击下面的链接设置新密码（30 分钟内有效）：\n\n"
            f"{link}\n\n"
            "如果这不是你的操作，请忽略这封邮件，密码不会改变。\n"
        ),
    )
