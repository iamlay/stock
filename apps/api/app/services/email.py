from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.settings import settings

logger = logging.getLogger(__name__)

USER_AGENT = "StockLab/0.1 (+https://stock.iamlay.com)"


class EmailNotConfigured(RuntimeError):
    pass


class EmailSendError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> None:
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **headers,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status >= 300:
                raise EmailSendError(f"email provider returned {response.status}")
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise EmailSendError(f"email provider HTTP {exc.code}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise EmailSendError("email provider is unreachable") from exc


def _send_smtp(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.from_address
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
        logger.exception("failed to send email to %s via SMTP", to)
        raise EmailSendError("SMTP delivery failed") from exc


def _send_resend(to: str, subject: str, body: str) -> None:
    _post_json(
        "https://api.resend.com/emails",
        {
            "from": settings.from_address,
            "to": [to],
            "subject": subject,
            "text": body,
        },
        {"Authorization": f"Bearer {settings.resend_api_key}"},
    )


def _send_brevo(to: str, subject: str, body: str) -> None:
    name, address = parseaddr(settings.from_address)
    _post_json(
        "https://api.brevo.com/v3/smtp/email",
        {
            "sender": {"email": address or settings.from_address, "name": name or "StockLab"},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": body,
        },
        {"api-key": settings.brevo_api_key},
    )


def send_email(to: str, subject: str, body: str) -> None:
    if settings.auth_dev_mode:
        logger.info("email dev mode to=%s subject=%s body=%s", to, subject, body)
        return
    if not settings.email_configured:
        raise EmailNotConfigured("email provider is not configured")

    provider = settings.email_provider.strip().lower()
    if provider == "smtp":
        _send_smtp(to, subject, body)
    elif provider == "resend":
        _send_resend(to, subject, body)
    elif provider == "brevo":
        _send_brevo(to, subject, body)
    else:
        raise EmailNotConfigured(f"unknown email provider: {provider}")


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
