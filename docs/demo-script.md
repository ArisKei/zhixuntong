# 4 分钟召回闭环讲稿（组长收口）

演示前确认：`DEMO_MODE=true`，`SCHEDULER_ENABLED=false`，中台已启动。

1. 打开 Swagger `/docs`，`POST /api/auth/login`（demo / demo123），右上角 Authorize。
2. `POST /api/crawler/start`，body：`{"source_id":"demo_recall"}`。
3. `GET /api/crawler/status` 看到 `inserted` / `duplicated`。
4. `GET /api/news?category=risk` 出现「召回 12 万辆」。
5. `POST /api/alert/evaluate`，body 填该 `news_id`，得到 `level=high`。
6. `POST /api/notify/dingtalk` 用返回的 `alert_id`；再 `POST /api/notify/email`。
7. 把屏幕切到钉钉群 / Mailhog（`http://127.0.0.1:8025`），读锁定文案。

口播一句：采集、研判、知识引用、触达，都经过 FastAPI 中台，而不是五套互不相干的程序。
