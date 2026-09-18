from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send_otp_email(self, to_email: str, otp_code: str) -> bool:
        """
        Sends a 6-digit OTP to the recipient email address.
        If SMTP credentials are not configured, logs the OTP prominently to the terminal.
        """
        settings = self.settings

        if not settings.smtp_user or not settings.smtp_password:
            print(
                f"\n{'='*60}\n"
                f" [DEV MODE] SMTP NOT CONFIGURED IN .env\n"
                f" Recipient: {to_email}\n"
                f" Verification OTP Code: {otp_code}\n"
                f" To receive real emails via Gmail, configure SMTP_USER & SMTP_PASSWORD in backend/.env\n"
                f"{'='*60}\n"
            )
            logger.warning("[DEV MODE] Verification OTP for %s: %s", to_email, otp_code)
            return True

        msg = EmailMessage()
        from_email = settings.smtp_from_email or settings.smtp_user
        from_header = f"{settings.smtp_from_name} <{from_email}>"
        msg["From"] = from_header
        msg["To"] = to_email
        msg["Subject"] = f"Your Admin Verification Code: {otp_code}"

        plain_text = (
            f"Hello,\n\n"
            f"Your verification code to complete Admin registration is: {otp_code}\n\n"
            f"This code will expire in 10 minutes.\n"
            f"If you did not request this, please ignore this email.\n"
        )
        msg.set_content(plain_text)

        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 20px; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="margin-bottom: 24px;">
      <span style="font-size: 13px; font-weight: 700; color: #3b82f6; text-transform: uppercase; letter-spacing: 0.1em;">RAG ASSISTANT</span>

      <h1 style="font-size: 22px; font-weight: 700; color: #0f172a; margin: 8px 0 0 0;">Admin Account Verification</h1>
    </div>
    <p style="color: #475569; font-size: 15px; line-height: 1.5; margin: 0 0 24px 0;">
      Use the verification code below to complete your administrator account registration. This code is valid for <strong>10 minutes</strong>.
    </p>
    <div style="background-color: #f1f5f9; border-radius: 8px; padding: 18px; text-align: center; margin-bottom: 24px;">
      <span style="font-family: monospace; font-size: 34px; font-weight: 700; letter-spacing: 8px; color: #1e293b;">{otp_code}</span>
    </div>
    <p style="color: #94a3b8; font-size: 13px; line-height: 1.4; margin: 0;">
      If you did not attempt to register an admin account with ACME, you can safely ignore this email.
    </p>
  </div>
</body>
</html>"""
        msg.add_alternative(html_content, subtype="html")

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            logger.info("Verification OTP email sent successfully to %s", to_email)
            return True
        except Exception as exc:
            logger.error("Failed to send OTP email to %s: %s", to_email, exc)
            raise RuntimeError(f"Failed to send email: {exc}") from exc
