"""Email sending backend — SMTP/SendGrid/SES configurable via env vars."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from .templates import render_template

logger = logging.getLogger("grantlayer.notifications")

_SMTP_HOST = os.environ.get("GRANTLAYER_SMTP_HOST", "localhost")
_SMTP_PORT = int(os.environ.get("GRANTLAYER_SMTP_PORT", "25"))
_SMTP_USER = os.environ.get("GRANTLAYER_SMTP_USER", "")
_SMTP_PASS = os.environ.get("GRANTLAYER_SMTP_PASS", "")
_SMTP_FROM = os.environ.get("GRANTLAYER_SMTP_FROM", "noreply@grantlayer.example")
_SMTP_TLS = os.environ.get("GRANTLAYER_SMTP_TLS", "false").lower() in ("1", "true", "yes")
_UNSUBSCRIBE_SECRET = os.environ.get("GRANTLAYER_UNSUBSCRIBE_SECRET", "change-me-unsub")
_BACKEND = os.environ.get("GRANTLAYER_EMAIL_BACKEND", "smtp")  # smtp | sendgrid | ses | noop
_BASE_URL = os.environ.get("GRANTLAYER_BASE_URL", "http://localhost:8765")


def make_unsubscribe_token(email: str) -> str:
    """Generate a signed unsubscribe token for *email*."""
    ts = int(time.time())
    raw = f"{email}:{ts}"
    sig = hmac.new(
        _UNSUBSCRIBE_SECRET.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()[:16]
    import base64
    payload = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"{payload}.{sig}"


def verify_unsubscribe_token(token: str, max_age_seconds: int = 7 * 86400) -> Optional[str]:
    """Verify a signed unsubscribe token. Returns email if valid, None otherwise."""
    try:
        import base64
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, provided_sig = parts
        padding = "=" * (4 - len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + padding).decode()
        email, ts_str = raw.rsplit(":", 1)
        ts = int(ts_str)
        if time.time() - ts > max_age_seconds:
            return None
        expected_sig = hmac.new(
            _UNSUBSCRIBE_SECRET.encode(), raw.encode(), hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None
        return email
    except Exception:
        return None


async def send_email(to: str, template: str, context: dict[str, Any]) -> None:
    """Send an email using the configured backend.

    context must contain all variables referenced by the template.
    Automatically adds an unsubscribe_url if not present.
    """
    base_url = os.environ.get("GRANTLAYER_BASE_URL", _BASE_URL)
    unsub_token = make_unsubscribe_token(to)
    context.setdefault("unsubscribe_url", f"{base_url}/v1/notifications/unsubscribe?token={unsub_token}")
    html_body = render_template(template, context)

    backend = os.environ.get("GRANTLAYER_EMAIL_BACKEND", _BACKEND).lower()
    if backend == "noop":
        logger.info("send_email [noop]: to=%s template=%s", to, template)
        return

    if backend == "sendgrid":
        await _send_sendgrid(to=to, subject=_subject_for(template), html=html_body)
    elif backend == "ses":
        await _send_ses(to=to, subject=_subject_for(template), html=html_body)
    else:
        _send_smtp(to=to, subject=_subject_for(template), html=html_body)


def _subject_for(template: str) -> str:
    subjects = {
        "grant_approved": "Your grant has been approved — GrantLayer",
        "grant_rejected": "Your grant request was rejected — GrantLayer",
        "grant_request_submitted": "Grant request submitted — GrantLayer",
        "webhook_failure_alert": "Webhook delivery failure alert — GrantLayer",
    }
    return subjects.get(template, f"GrantLayer notification: {template}")


def _send_smtp(to: str, subject: str, html: str) -> None:
    host = os.environ.get("GRANTLAYER_SMTP_HOST", _SMTP_HOST)
    port = int(os.environ.get("GRANTLAYER_SMTP_PORT", str(_SMTP_PORT)))
    user = os.environ.get("GRANTLAYER_SMTP_USER", _SMTP_USER)
    password = os.environ.get("GRANTLAYER_SMTP_PASS", _SMTP_PASS)
    tls = os.environ.get("GRANTLAYER_SMTP_TLS", "false").lower() in ("1", "true", "yes")
    from_addr = os.environ.get("GRANTLAYER_SMTP_FROM", _SMTP_FROM)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    smtp: smtplib.SMTP
    if tls:
        smtp = smtplib.SMTP_SSL(host, port)
    else:
        smtp = smtplib.SMTP(host, port)
    try:
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [to], msg.as_string())
    finally:
        smtp.quit()


async def _send_sendgrid(to: str, subject: str, html: str) -> None:
    api_key = os.environ.get("GRANTLAYER_SENDGRID_API_KEY", "")
    from_addr = os.environ.get("GRANTLAYER_SMTP_FROM", _SMTP_FROM)
    import httpx
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()


async def _send_ses(to: str, subject: str, html: str) -> None:
    from_addr = os.environ.get("GRANTLAYER_SMTP_FROM", _SMTP_FROM)
    try:
        import boto3  # type: ignore[import-untyped]
        ses = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "eu-central-1"))
        ses.send_email(
            Source=from_addr,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": html}},
            },
        )
    except ImportError:
        raise RuntimeError("boto3 is required for SES email backend. Install with: pip install boto3")
