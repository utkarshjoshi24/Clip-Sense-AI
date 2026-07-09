"""
backend/app/services/email.py — Email service.

In dev (EMAIL_MOCK=True): prints emails to the console.
In prod: sends via SMTP using configured credentials.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _send_smtp(to_email: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())


def send_email(to_email: str, subject: str, html_body: str) -> None:
    """Send an email — mocked in dev, real SMTP in prod."""
    if settings.EMAIL_MOCK:
        logger.info(
            "[EMAIL MOCK] To: %s | Subject: %s\n%s",
            to_email, subject, html_body
        )
        print(f"\n{'='*60}\n[DEV EMAIL] To: {to_email}\nSubject: {subject}\n{html_body}\n{'='*60}\n")
        return
    try:
        _send_smtp(to_email, subject, html_body)
        logger.info("Email sent to %s: %s", to_email, subject)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        raise


def send_verification_email(to_email: str, token: str) -> None:
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#7c3aed">Verify your ClipSense account</h2>
      <p>Click the button below to verify your email address. This link expires in 24 hours.</p>
      <a href="{verify_url}"
         style="background:#7c3aed;color:#fff;padding:12px 24px;border-radius:6px;
                text-decoration:none;display:inline-block;margin:16px 0">
        Verify Email
      </a>
      <p style="color:#888;font-size:12px">Or copy this URL: {verify_url}</p>
    </div>
    """
    send_email(to_email, "Verify your ClipSense email", html)


def send_password_reset_email(to_email: str, token: str) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2 style="color:#7c3aed">Reset your ClipSense password</h2>
      <p>Click the button below to reset your password. This link expires in 1 hour and can only be used once.</p>
      <a href="{reset_url}"
         style="background:#7c3aed;color:#fff;padding:12px 24px;border-radius:6px;
                text-decoration:none;display:inline-block;margin:16px 0">
        Reset Password
      </a>
      <p style="color:#888;font-size:12px">If you didn't request this, ignore this email.</p>
    </div>
    """
    send_email(to_email, "Reset your ClipSense password", html)
