from typing import Optional

from schemas.alert import AlertOut
from zxt_notify import (
    EmailSettings,
    NotificationError,
    render_dingtalk,
    send_dingtalk as deliver_dingtalk,
    send_email as deliver_email,
)


class LogNotifyClient:
    def send_dingtalk(self, alert: AlertOut) -> str:
        from app.logging import get_logger

        text = render_dingtalk(alert)
        get_logger("notify").info("dingtalk_log_mode", message=text)
        return text

    def send_email(self, kind: str, subject: str, body: str, to: Optional[str] = None) -> str:
        from app.logging import get_logger

        get_logger("notify").info("email_log_mode", kind=kind, subject=subject, to=to)
        return f"[email:{kind}] {subject}"


class HttpNotifyClient:
    def __init__(
        self,
        webhook: str,
        dingtalk_secret: str,
        smtp_host: str,
        smtp_port: int,
        smtp_from: str,
        smtp_default_to: str,
        smtp_user: str,
        smtp_password: str,
        smtp_use_tls: bool,
    ) -> None:
        self.webhook = webhook
        self.dingtalk_secret = dingtalk_secret or None
        self.email_settings = EmailSettings(
            host=smtp_host,
            port=smtp_port,
            sender=smtp_from,
            default_to=smtp_default_to,
            username=smtp_user or None,
            password=smtp_password or None,
            use_tls=smtp_use_tls,
        )

    def send_dingtalk(self, alert: AlertOut) -> str:
        from app.errors import AppError

        try:
            return deliver_dingtalk(alert, webhook=self.webhook, secret=self.dingtalk_secret)
        except NotificationError as exc:
            raise AppError("notify_unavailable", str(exc), 503) from exc

    def send_email(self, kind: str, subject: str, body: str, to: Optional[str] = None) -> str:
        from app.errors import AppError

        try:
            return deliver_email(kind, subject, body, to, settings=self.email_settings)
        except (NotificationError, ValueError) as exc:
            raise AppError("notify_unavailable", str(exc), 503) from exc
