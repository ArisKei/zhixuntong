# 成员 E：钉钉 / 邮件

契约：`docs/events.md` 钉钉模板。中台默认 `NOTIFY_MODE=log` 把文案打到控制台。

你实现 `services/notify` 后，组长改 `NOTIFY_MODE=http` 并配置 `DINGTALK_WEBHOOK`。开发邮件可用根目录 `docker compose up -d mailhog`，打开 http://127.0.0.1:8025
