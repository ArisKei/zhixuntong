# 智讯通

企业智能情报分析与知识助手（FastAPI 中台 + 爬虫 + RAGFlow + Dify + 钉钉/邮件）。

**仓库：** https://github.com/ArisKei/zhixuntong

---

## 开发进度

| 模块 | 状态 | 说明 |
|---|---|---|
| FastAPI 中台 | ✅ 已提供 | 登录、采集、新闻、知识库、AI 分析、预警与通知统一接口 |
| Web 前端 | ✅ **开发完成** | Vue 3 五页面、Mock/真实接口切换、召回闭环与响应式布局 |
| 钉钉 / 邮件通知 | ✅ **开发完成** | 固定钉钉模板、Webhook 加签、HTML 邮件、SMTP/TLS 与日志降级 |
| 爬虫 / RAGFlow / Dify | 🚧 按分工联调 | 可继续通过中台 Mock Client 并行开发 |

成员 E 的前端与通知职责已于 **2026-08-19** 全部完成，并通过通知单元测试、前端类型检查、生产构建和 FastAPI live 端到端流程验证。详细说明见 [apps/web/README.md](apps/web/README.md) 与 [services/notify/README.md](services/notify/README.md)。

---

## 组员先看这里

### 必读（全员）

| 文件 | 干什么用 |
|---|---|
| [docs/小白协作说明书.md](docs/小白协作说明书.md) | **最先看**。组长做了什么、你做什么、怎么对接整合 |
| [docs/组员接口对照表.md](docs/组员接口对照表.md) | **谁实现哪些接口、传参/返回长什么样**（按 B/C/D/E 分列） |
| [docs/openapi.yaml](docs/openapi.yaml) | 完整 OpenAPI 契约原文，**禁止私自改字段名** |
| [packages/schemas/README.md](packages/schemas/README.md) | 数据字段与枚举；你实现时的函数签名 |
| [docs/events.md](docs/events.md) | 预警 JSON、钉钉文案模板、周报六个标题（固定格式） |
| [.env.example](.env.example) | 环境变量说明；组员做完后组长改这里对接真服务 |

### 按角色再看

| 角色 | 负责目录 | 还要看 |
|---|---|---|
| 成员 B 爬虫 | `services/crawler` | [接口对照表 · B](docs/组员接口对照表.md#1-成员-b--爬虫--入库)、[crawler README](services/crawler/README.md)、[fixtures/seed/news.json](fixtures/seed/news.json) |
| 成员 C 知识库 | `services/rag` | [接口对照表 · C](docs/组员接口对照表.md#2-成员-c--ragflow-知识库)、[rag README](services/rag/README.md) |
| 成员 D AI 工作流 | `services/ai` | [接口对照表 · D](docs/组员接口对照表.md#3-成员-d--dify-工作流)、[ai README](services/ai/README.md)、[events.md](docs/events.md) |
| 成员 E 前端/通知 | `apps/web`、`services/notify` | [接口对照表 · E](docs/组员接口对照表.md#4-成员-e--钉钉--邮件--前端)、[web](apps/web/README.md)、[notify](services/notify/README.md) |

### 进阶 / 答辩（选读）

| 文件 | 干什么用 |
|---|---|
| [智讯通项目-AI分工方案.md](智讯通项目-AI分工方案.md) | 完整任务卡、排期、每人验收标准（做细活时对照） |
| [docs/demo-script.md](docs/demo-script.md) | 答辩最后 4 分钟「召回闭环」讲稿 |
| http://127.0.0.1:8000/docs | 中台跑起来后的在线接口文档（Swagger） |

**克隆后怎么开工：** 小白协作说明书 → **组员接口对照表（看自己那一节）** → 只改自己的目录 → 字段名以契约为准 → 做完告诉组长对接。

---

## 目录谁负责

| 人 | 目录 |
|---|---|
| 组长 A | `services/api`、`packages/schemas`、`docs/` |
| 成员 B | `services/crawler`、`fixtures/html` |
| 成员 C | `services/rag`、`fixtures/docs` |
| 成员 D | `services/ai` |
| 成员 E | `apps/web`、`services/notify` |

---

## 启动项目

需要 Python 3.9+、Node.js 20+。以下命令均从仓库根目录开始执行。

### 首次安装（只需执行一次）

```powershell
cd services/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ../../apps/web
npm install
```

### 日常启动

打开两个 PowerShell 终端。

终端一：启动 FastAPI 中台：

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
.\run.ps1
```

终端二：以前端 Live 模式连接 FastAPI：

```powershell
cd apps/web
$env:VITE_API_MODE="live"
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
npm run dev -- --host 127.0.0.1 --port 5173
```

- 前端地址：http://127.0.0.1:5173
- 健康检查：http://127.0.0.1:8000/health
- 接口文档：http://127.0.0.1:8000/docs
- 演示账号：`demo` / `demo123`

上述前端环境变量只对当前终端生效。需要持久化 Live 模式时，可复制 `apps/web/.env.example` 为 `apps/web/.env`，并设置相同的两个变量。只运行 `npm run dev` 且未配置环境变量时，前端使用 Mock 数据。

修改仓库根目录 `.env` 中的钉钉或 SMTP 配置后，必须重启 FastAPI 才会生效。

**Token 怎么拿：** 先调 `POST /api/auth/login`，复制返回的 `access_token`，点右上角 Authorize 粘贴。

**演示顺序：** login → crawler/start(`demo_recall`) → news → alert/evaluate → notify/dingtalk

前端包含：

- 首页情报总览与“一键召回闭环”
- AI 助手及可核验引用
- 企业知识库上传、文档列表和试检索
- 情报时间线、分类筛选与六段行业周报
- 分级预警详情、钉钉与邮件推送
- 行业日报 / 周报邮件发送

接口接入需求已作为 `API 需求` 注释统一整理在 `apps/web/src/services/api.ts`。

## 启用真实通知（成员 E 已完成）

默认 `NOTIFY_MODE=log`，会输出完整消息但不触达外部系统。接入钉钉与 SMTP 时，在 `.env` 中改为：

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

开发阶段可运行 `docker compose up -d mailhog`，然后在 http://127.0.0.1:8025 查看邮件。
