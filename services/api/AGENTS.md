# 智讯通中台（成员 A / 组长）

- 只做 HTTP、鉴权、编排、定时任务、日志。不写爬虫解析，不改 Prompt，不写前端。
- 字段名只来自 `packages/schemas`。错误体一律 `{"code","message"}`。
- 外部系统必须走 `app/clients` 的 Protocol；默认 Mock/log，组员就绪后改环境变量。
- 路由函数禁止堆业务 if-else，写到 `app/services`。
- 分类枚举：policy/company/market/tech/risk/other；风险：low/medium/high/critical。
- `DEMO_MODE=true` 时采集必须能注入召回种子新闻，答辩不依赖外网。
- `SCHEDULER_ENABLED` 默认 false，答辩用接口按钮触发。
