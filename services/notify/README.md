# 成员 E：钉钉 / 邮件通知

> ✅ **开发状态：通知能力已完成**

本目录提供可由 FastAPI 中台调用的 `zxt_notify` 库。对外 `/api/notify/*` 路由仍由 `services/api` 提供；本目录只负责固定模板、钉钉机器人调用和 SMTP 邮件发送。

## 已完成功能

- 锁定的钉钉行业事件模板
- 钉钉自定义机器人 Webhook 调用与业务错误码校验
- 可选钉钉加签密钥 `DINGTALK_SECRET`
- 预警邮件和日报/周报邮件 HTML 模板
- 纯文本邮件降级
- SMTP TLS、账号密码、默认收件人配置
- 日志模式与真实发送模式共用同一套模板
- 单元测试覆盖模板、Webhook 成功/失败、SMTP 发送

## 中台配置

在仓库根目录或 `services/api/.env` 中配置：

```env
NOTIFY_MODE=http

DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=

SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_FROM=zhixuntong@example.com
SMTP_DEFAULT_TO=demo@example.com
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=false
```

开发邮件可使用仓库自带 MailHog：

```powershell
docker compose up -d mailhog
```

然后打开 http://127.0.0.1:8025 查看邮件。

## 函数契约

```python
from zxt_notify import EmailSettings, send_dingtalk, send_email

send_dingtalk(alert, webhook="https://...", secret=None)
send_email(
    kind="alert",
    subject="【智讯通预警】召回事件",
    body="事件摘要……",
    to="demo@example.com",
    settings=EmailSettings(...),
)
```

钉钉正文固定为：

```text
【智讯通·行业重要事件提醒】
企业：{company}
事件：{title}
风险等级：{level}
影响分析：{impact}
建议：{suggestion}
```

## 测试

```powershell
python -m pip install -r services/notify/requirements.txt
$env:PYTHONPATH="services/notify/src"
python -m unittest discover -s services/notify/tests -v
```
