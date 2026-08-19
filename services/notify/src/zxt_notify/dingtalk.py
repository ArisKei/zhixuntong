from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .errors import NotificationError


DINGTALK_TEMPLATE = """【智讯通·行业重要事件提醒】
企业：{company}
事件：{title}
风险等级：{level}
影响分析：{impact}
建议：{suggestion}"""


class AlertLike(Protocol):
    company: str
    title: str
    level: Any
    impact: str
    suggestion: str


def _level_text(level: Any) -> str:
    return str(getattr(level, "value", level))


def render_dingtalk(alert: AlertLike) -> str:
    """Render the locked copy from docs/events.md without accepting free-form text."""
    return DINGTALK_TEMPLATE.format(
        company=alert.company,
        title=alert.title,
        level=_level_text(alert.level),
        impact=alert.impact,
        suggestion=alert.suggestion,
    )


def build_signed_webhook(webhook: str, secret: str, timestamp_ms: int | None = None) -> str:
    """Append DingTalk's timestamp/sign query parameters while preserving access_token."""
    timestamp = timestamp_ms or int(time.time() * 1000)
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    parts = urlsplit(webhook)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"timestamp": str(timestamp), "sign": signature})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def send_dingtalk(
    alert: AlertLike,
    *,
    webhook: str,
    secret: str | None = None,
    timeout: float = 15,
    client: httpx.Client | None = None,
) -> str:
    if not webhook.strip():
        raise NotificationError("dingtalk", "未配置 DINGTALK_WEBHOOK")

    text = render_dingtalk(alert)
    target = build_signed_webhook(webhook, secret) if secret else webhook
    payload = {"msgtype": "text", "text": {"content": text}}
    try:
        if client is None:
            with httpx.Client(timeout=timeout) as owned_client:
                response = owned_client.post(target, json=payload)
        else:
            response = client.post(target, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        raise NotificationError("dingtalk", f"钉钉发送失败：{exc}") from exc

    if isinstance(result, dict) and result.get("errcode", 0) != 0:
        message = result.get("errmsg") or "未知错误"
        raise NotificationError("dingtalk", f"钉钉机器人拒绝消息：{message}")
    return text
