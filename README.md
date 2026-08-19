# 智讯通

企业智能情报分析与知识助手（FastAPI 中台 + 爬虫 + RAGFlow + Dify + 钉钉/邮件）。

**仓库：** https://github.com/ArisKei/zhixuntong

---

## 组员先看这里

### 必读（全员）

| 文件 | 干什么用 |
|---|---|
| [docs/小白协作说明书.md](docs/小白协作说明书.md) | **最先看**。组长做了什么、你做什么、怎么对接整合 |
| [docs/openapi.yaml](docs/openapi.yaml) | 接口契约：路径、请求/响应字段，**禁止私自改名** |
| [packages/schemas/README.md](packages/schemas/README.md) | 数据字段与枚举约定；你实现时的函数签名也在这 |
| [docs/events.md](docs/events.md) | 预警 JSON、钉钉文案模板、周报六个标题（固定格式） |
| [.env.example](.env.example) | 环境变量说明；组员做完后组长改这里对接真服务 |

### 按角色再看

| 角色 | 负责目录 | 还要看 |
|---|---|---|
| 成员 B 爬虫 | `services/crawler` | [services/crawler/README.md](services/crawler/README.md)、[services/crawler/AGENTS.md](services/crawler/AGENTS.md)、[fixtures/seed/news.json](fixtures/seed/news.json) |
| 成员 C 知识库 | `services/rag` | [services/rag/README.md](services/rag/README.md) |
| 成员 D AI 工作流 | `services/ai` | [services/ai/README.md](services/ai/README.md)、[docs/events.md](docs/events.md) |
| 成员 E 前端/通知 | `apps/web`、`services/notify` | [apps/web/README.md](apps/web/README.md)、[services/notify/README.md](services/notify/README.md)、[docs/events.md](docs/events.md) |

### 进阶 / 答辩（选读）

| 文件 | 干什么用 |
|---|---|
| [智讯通项目-AI分工方案.md](智讯通项目-AI分工方案.md) | 完整任务卡、排期、每人验收标准（做细活时对照） |
| [docs/demo-script.md](docs/demo-script.md) | 答辩最后 4 分钟「召回闭环」讲稿 |
| http://127.0.0.1:8000/docs | 中台跑起来后的在线接口文档（Swagger） |

**克隆后怎么开工：** 先读小白协作说明书 → 只改自己的目录 → 字段名以 `openapi.yaml` / `packages/schemas` 为准 → 做完告诉组长对接。

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

## 组长：启动中台

需要 Python 3.9+。

```powershell
cd services/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\run.ps1
```

- 健康检查：http://127.0.0.1:8000/health  
- 接口文档：http://127.0.0.1:8000/docs  
- 账号：`demo` / `demo123`

**Token 怎么拿：** 先调 `POST /api/auth/login`，复制返回的 `access_token`，点右上角 Authorize 粘贴。

**演示顺序：** login → crawler/start(`demo_recall`) → news → alert/evaluate → notify/dingtalk
