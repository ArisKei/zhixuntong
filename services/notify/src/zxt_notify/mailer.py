from __future__ import annotations

import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from typing import Callable, Literal

from .errors import NotificationError


EmailKind = Literal["alert", "daily"]


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int = 25
    sender: str = "zhixuntong@example.com"
    default_to: str = "demo@example.com"
    username: str | None = None
    password: str | None = None
    use_tls: bool = False
    timeout: float = 10


def _body_to_html(kind: EmailKind, body: str) -> str:
    if kind == "daily":
        parts = re.split(r"(?m)^##\s+", body)
        intro = parts[0].strip()
        sections: list[str] = []
        for part in parts[1:]:
            heading, _, content = part.partition("\n")
            escaped_content = escape(content.strip()).replace("\n", "<br>")
            sections.append(
                '<section style="padding:18px 0;border-top:1px solid #d8d6cd">'
                f'<h2 style="margin:0 0 10px;color:#0d5c49;font-size:18px">{escape(heading.strip())}</h2>'
                f'<p style="margin:0;line-height:1.8;color:#4f5b56">{escaped_content}</p>'
                "</section>"
            )
        prefix = f'<p style="line-height:1.8;color:#4f5b56">{escape(intro)}</p>' if intro else ""
        return prefix + "".join(sections)
    escaped_body = escape(body).replace("\n", "<br>")
    return f'<p style="line-height:1.9;color:#33403b">{escaped_body}</p>'


def render_email_html(kind: EmailKind, subject: str, body: str) -> str:
    if kind not in ("alert", "daily"):
        raise ValueError(f"unsupported email kind: {kind}")
    accent = "#c53b32" if kind == "alert" else "#0d5c49"
    label = "RISK ALERT" if kind == "alert" else "INDUSTRY BRIEF"
    return f"""<!doctype html>
<html lang="zh-CN">
<body style="margin:0;background:#f2f0e9;font-family:Arial,'Microsoft YaHei',sans-serif;color:#16201d">
  <div style="max-width:680px;margin:0 auto;padding:28px 18px">
    <div style="background:#ffffff;border-top:4px solid {accent};padding:34px">
      <div style="color:#0d5c49;font-size:12px;font-weight:700;letter-spacing:2px">智讯通 · {label}</div>
      <h1 style="margin:18px 0 26px;font-size:28px;line-height:1.4">{escape(subject)}</h1>
      {_body_to_html(kind, body)}
      <div style="margin-top:30px;padding-top:16px;border-top:1px solid #d8d6cd;color:#8a918e;font-size:12px">
        本邮件由智讯通企业智能情报系统自动生成，请结合原始来源复核后决策。
      </div>
    </div>
  </div>
</body>
</html>"""


def _recipients(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]


def build_email_message(kind: EmailKind, subject: str, body: str, to: str | None, settings: EmailSettings) -> EmailMessage:
    recipients = _recipients(to or settings.default_to)
    if not recipients:
        raise NotificationError("email", "未配置邮件收件人")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    message.add_alternative(render_email_html(kind, subject, body), subtype="html")
    return message


def send_email(
    kind: EmailKind,
    subject: str,
    body: str,
    to: str | None,
    *,
    settings: EmailSettings,
    smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
) -> str:
    message = build_email_message(kind, subject, body, to, settings)
    try:
        with smtp_factory(settings.host, settings.port, timeout=settings.timeout) as smtp:
            if settings.use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.username:
                smtp.login(settings.username, settings.password or "")
            smtp.send_message(message)
    except Exception as exc:
        raise NotificationError("email", f"邮件发送失败：{exc}") from exc
    return f"[email:{kind}] {subject}"
