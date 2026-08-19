from typing import Optional

from schemas.alert import AlertOut


DINGTALK_TEMPLATE = """【智讯通·行业重要事件提醒】
企业：{company}
事件：{title}
风险等级：{level}
影响分析：{impact}
建议：{suggestion}"""


class LogNotifyClient:
    def send_dingtalk(self, alert: AlertOut) -> str:
        from app.logging import get_logger

        text = DINGTALK_TEMPLATE.format(
            company=alert.company,
            title=alert.title,
            level=alert.level.value if hasattr(alert.level, "value") else alert.level,
            impact=alert.impact,
            suggestion=alert.suggestion,
        )
        get_logger("notify").info("dingtalk_log_mode", message=text)
        return text

    def send_email(self, kind: str, subject: str, body: str, to: Optional[str] = None) -> str:
        from app.logging import get_logger

        get_logger("notify").info("email_log_mode", kind=kind, subject=subject, to=to)
        return f"[email:{kind}] {subject}"


class HttpNotifyClient:
    def __init__(self, webhook: str, smtp_host: str, smtp_port: int, smtp_from: str) -> None:
        self.webhook = webhook
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_from = smtp_from

    def send_dingtalk(self, alert: AlertOut) -> str:
        import httpx

        from app.errors import AppError

        text = LogNotifyClient().send_dingtalk(alert)
        if not self.webhook:
            return text
        try:
            httpx.post(self.webhook, json={"msgtype": "text", "text": {"content": text}}, timeout=15).raise_for_status()
        except Exception as exc:
            raise AppError("notify_unavailable", "钉钉发送失败", 503) from exc
        return text

    def send_email(self, kind: str, subject: str, body: str, to: Optional[str] = None) -> str:
        import smtplib
        from email.message import EmailMessage

        from app.errors import AppError

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.smtp_from
        message["To"] = to or "demo@example.com"
        message.set_content(body)
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as smtp:
                smtp.send_message(message)
        except Exception as exc:
            raise AppError("notify_unavailable", "邮件发送失败（可改 NOTIFY_MODE=log）", 503) from exc
        return f"[email:{kind}] {subject}"
