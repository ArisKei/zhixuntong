# 智讯通——企业智能情报分析与知识助手

> 优化目标：20 分钟答辩能跑通一条完整闭环；5 人可并行；每一项工作都能用 Cursor / AI Coding 一次性写完并验收。
>
> 一句话：系统采集新能源汽车公开情报，结合企业内部资料做 RAG 问答与风险研判，再通过钉钉/邮件把结论推给人。

---

## 0. 相对原稿改了什么

原稿把技术点串成了闭环，但分工偏「角色口号」，不适合 AI Coding。本次只改工作方式，不改老师要求的技术栈。

| 原稿问题 | 优化后 |
|---|---|
| 5 人职责重叠（组长也调 Dify/RAG，成员 5 又做前端又做通知） | 每人只拥有一组目录 + 一组接口契约 |
| 任务太大（「做爬虫」「做 Dify」） | 拆成 1 个 Prompt 能完成的任务卡 |
| 没有接口约定，后半程才能联调 | 第 0 周先冻结 Schema / OpenAPI / 事件 JSON |
| 爬虫范围太大（6 类信息 × 无数站点） | 只做 **新能源汽车** 垂直，**3 个数据源** |
| 演示依赖当天网上刚好有新闻 | 仓库内置 **fixtures 种子数据**，答辩可离线跑通 |
| Dify / RAGFlow 靠点界面 | 业务逻辑写进 FastAPI；Dify/RAGFlow 只做编排和检索，配置文件进 Git |

**明确不做（防膨胀）：** 用户体系做简易登录即可；不做权限中台、不做多租户、不做实时行情、不对抗反爬、不追求 5000 条真实采集。答辩数字用种子数据 + 少量真实采集即可。

---

## 1. 业务闭环（答辩主线）

垂直场景固定为 **新能源汽车行业情报**，用户角色是「本公司战略/产品同事」。

```
公开网页/RSS
    → 爬虫采集 + 清洗去重
    → MySQL（新闻/政策/任务日志）
    → FastAPI 中台调度
         ├→ RAGFlow（企业私有文档问答，带引用）
         ├→ Dify Workflow（分类 / 风险研判 / 报告）
         └→ 钉钉机器人 + SMTP 邮件
```

三条必须能现场演示的用户路径：

1. **知识问答：**「X1 产品最大日处理能力是多少？」→ RAG 引用说明书页码  
2. **情报分析：**「最近 7 天新能源政策与车企动态」→ 结构化周报  
3. **风险闭环：** 种子新闻「XX 汽车召回」→ 风险高等级 → 钉钉 + 邮件同时到达  

---

## 2. 仓库结构（先定这个，AI 才知道往哪写）

建议一个 Git 仓库，按目录划边界。**谁的目录谁改，公共契约只改 `packages/schemas`。**

```
zhixuntong/
├── README.md
├── docker-compose.yml          # MySQL + RAGFlow + 可选 Mailhog
├── .env.example
├── docs/
│   ├── openapi.yaml            # 全组唯一 API 契约
│   ├── events.md               # 预警/报告 JSON
│   └── demo-script.md          # 4 分钟闭环讲稿
├── packages/
│   └── schemas/                # Pydantic 模型，全员依赖
│       ├── news.py
│       ├── knowledge.py
│       ├── alert.py
│       └── report.py
├── apps/
│   └── web/                    # 成员 E：Vue3 前端
├── services/
│   ├── api/                    # 成员 A：FastAPI 中台
│   ├── crawler/                # 成员 B：采集与清洗
│   ├── rag/                    # 成员 C：RAGFlow 封装 + 语料
│   ├── ai/                     # 成员 D：Prompt、Dify DSL、报告模板
│   └── notify/                 # 成员 E：钉钉 + 邮件
├── fixtures/                   # 答辩种子：HTML、PDF、假新闻、假文档
└── scripts/
    ├── seed_db.py
    └── demo_recall.py
```

**AI Coding 原则：** 一次只生成一个目录里的一个模块；输入输出必须是上面契约里的 JSON；依赖对方未完成时，先对 `fixtures/` 和 mock 接口编程。

---

## 3. 第 0 周：全组先冻结契约（1 天，AI 生成）

这是并行开发的前提。由组长用一次 Cursor 任务生成，其他人 **只消费、不改字段名**。

### 3.1 MySQL 表（8 张，够答辩）

| 表 | 用途 | 谁写入 | 谁读取 |
|---|---|---|---|
| `users` | 简易登录 | A | A/E |
| `crawler_source` | 数据源配置 | B | A/B |
| `crawler_task` | 采集任务与状态 | B | A/E |
| `news` | 清洗后的新闻/政策 | B | 全员 |
| `knowledge_doc` | 已入知识库文档元数据 | C | A/E |
| `alert` | 预警事件 | D 经 A 写入 | E |
| `report` | 日报/周报 | D 经 A 写入 | E |
| `job_log` | 调度与错误日志 | A | A |

`news` 核心字段（全员按这个写）：

```json
{
  "id": 1,
  "title": "某车企宣布召回12万辆新能源车",
  "published_at": "2026-08-18T09:00:00+08:00",
  "source": "fixture-recall",
  "source_url": "https://example.com/n/1",
  "category": "risk",
  "company": "XX汽车",
  "content": "...",
  "content_hash": "sha256...",
  "keywords": ["召回", "新能源"],
  "is_duplicate": false
}
```

`category` 枚举固定：`policy` | `company` | `market` | `tech` | `risk` | `other`  
风险等级枚举固定：`low` | `medium` | `high` | `critical`

### 3.2 FastAPI 接口（先这 14 个，禁止私自加路径）

| 方法 | 路径 | 说明 | 实现人 |
|---|---|---|---|
| POST | `/api/auth/login` | 演示账号登录 | A |
| POST | `/api/crawler/start` | 启动一次采集 | A 调 B |
| GET | `/api/crawler/status` | 任务状态 | A 读 B |
| GET | `/api/news` | 新闻列表（筛选时间/分类） | A |
| GET | `/api/news/{id}` | 新闻详情 | A |
| POST | `/api/knowledge/upload` | 上传企业文档 | A 调 C |
| GET | `/api/knowledge/search` | 检索+引用 | A 调 C |
| POST | `/api/chat` | 统一问答入口 | A 调 C/D |
| POST | `/api/analyze` | 情报分析/报告 | A 调 D |
| POST | `/api/alert/evaluate` | 对一条新闻做风险研判 | A 调 D |
| GET | `/api/alerts` | 预警列表 | A |
| GET | `/api/reports` | 报告列表 | A |
| POST | `/api/notify/dingtalk` | 发钉钉 | A 调 E |
| POST | `/api/notify/email` | 发邮件 | A 调 E |

### 3.3 预警事件 JSON（钉钉/邮件/前端共用）

```json
{
  "alert_id": "alrt_20260818_001",
  "level": "high",
  "company": "XX汽车",
  "title": "宣布召回12万辆汽车",
  "summary": "……",
  "impact": "可能影响品牌信誉及供应链订单",
  "suggestion": "核对本公司是否使用相关零部件",
  "news_id": 1,
  "citations": [
    {"doc": "X1产品说明书", "page": 13, "snippet": "……"}
  ]
}
```

组长第 0 天的 Cursor 任务：**根据本节生成 `packages/schemas` + `docs/openapi.yaml` + Alembic 初版迁移，不要实现业务。**

---

## 4. 五人分工总览

| 代号 | 角色 | 只拥有的目录 | 对外交付物 | 答辩 3 分钟讲什么 |
|---|---|---|---|---|
| A 组长 | 中台与调度 | `services/api` `docs/` `packages/schemas` | 可运行的 API + Swagger | 架构、数据流、现场调接口 |
| B | 数据工程 | `services/crawler` `fixtures/html` | 3 个采集器 + 清洗入库 | 点「开始采集」，看去重数字和库表 |
| C | RAG 工程 | `services/rag` `fixtures/docs` | 知识库 + 带引用检索 API | 无 RAG vs 有 RAG 对比 |
| D | AI 应用 | `services/ai` | 3 条 Dify 工作流 + Prompt | 打开 Workflow 节点图 |
| E | 触达与界面 | `apps/web` `services/notify` | 5 个页面 + 钉钉/邮件 | 闭环最后一跳：消息到达 |

工作量对齐方式：每人大约 **8～10 张任务卡**。卡与卡之间有依赖，但前 6 张都可以对着 mock/fixtures 先做完。

---

## 5. 成员 A（组长）—— FastAPI 中台

**职责边界：** 只做 HTTP、鉴权、编排、定时任务、日志。不写爬虫解析，不调 LLM 提示词，不写前端。

**技术：** FastAPI + SQLAlchemy 2 + Alembic + APScheduler + httpx + structlog

### 任务卡（按顺序交给 AI）

| ID | 任务 | 让 AI 生成的文件 | 验收 |
|---|---|---|---|
| A1 | 脚手架 | `services/api` 项目、`docker-compose` 中的 MySQL、`.env.example`、CORS、健康检查 `/health` | `uvicorn` 启动，`/health` 返回 200 |
| A2 | 契约落地 | 引用 `packages/schemas`，挂载 Swagger | `/docs` 能看到 14 个接口骨架 |
| A3 | 用户登录 | `users` 表 + JWT，演示账号 `demo/demo123` | 登录返回 token，无 token 访问业务接口 401 |
| A4 | 新闻只读 API | `GET /api/news` 分页、分类、时间筛选 | 对着 `fixtures` 种子数据能查出召回新闻 |
| A5 | 爬虫代理 | `POST /api/crawler/start` 用 httpx 调 B 的内部函数或子服务；写 `crawler_task` | 返回 `task_id`；`GET status` 能看到 running/success |
| A6 | RAG 代理 | upload/search 转调 C 的 client，统一错误码 | RAGFlow 挂了时返回 503 + 明确信息，不能 500 堆栈 |
| A7 | Dify 代理 | `/api/chat` `/api/analyze` `/api/alert/evaluate` | 请求体/响应体严格符合 OpenAPI |
| A8 | 通知代理 | 调 E 的 dingtalk/email 模块 | 用 Mailhog 或日志模式也能跑 |
| A9 | 调度器 | 每天 08:00 采集；每天 18:00 生成日报并发送 | 可用环境变量关掉，答辩改成「点按钮触发」 |
| A10 | 日志与演示开关 | `job_log`；`DEMO_MODE=true` 时强制注入召回种子新闻 | 答辩不依赖外网 |

**给 AI 的约束（写进 Cursor 规则）：**

- 所有外部依赖（爬虫/RAG/Dify/钉钉）必须有 `Protocol` 接口 + `MockXxxClient`
- 禁止在路由函数里写业务 if-else；放到 `services/` 层
- 错误统一 `{"code": "...", "message": "..."}`

**A 的独立演示：** 打开 `/docs`，依次调用 login → crawler/start → news → alert/evaluate → notify/dingtalk。

---

## 6. 成员 B——采集、清洗、MySQL 写入

**职责边界：** 把网页变成 `news` 行。不调 Dify，不做前端。分类可用规则+关键词，不必上大模型（D 会再判一次风险）。

**技术：** httpx 或 requests、BeautifulSoup、selectolax（可选）、feedparser（RSS）、tenacity 重试。Selenium **最多用于 1 个站点**，且必须可开关；答辩默认走 fixtures。

### 数据源（只做这 3 个，名称写死方便演示）

| source_id | 类型 | 建议 | 解析策略 |
|---|---|---|---|
| `miit_policy` | 政策 | 工信部或国务院政策列表页 / RSS | 列表标题+链接+日期；正文另开详情页 |
| `ev_news` | 行业新闻 | 选一个结构稳定的新能源资讯列表（或 RSS） | 列表+详情 |
| `oem_news` | 车企动态 | 选 1 家车企新闻中心 **静态列表** | 列表+详情 |

每个源必须同时提供：

1. `fixtures/html/{source_id}/list.html` + `detail.html`（给单测和离线答辩）  
2. `live` 模式（实习环境能上网时用）

### 任务卡

| ID | 任务 | 让 AI 生成 | 验收 |
|---|---|---|---|
| B1 | 采集框架 | `BaseSpider`：fetch → parse_list → parse_detail → normalize → hash | 对 fixture HTML 跑通，不访问网络 |
| B2 | 去重 | `content_hash = sha256(title+url)`，库中存在则 `is_duplicate=true` 不插入正文重复行 | 同一 fixture 跑两次，第二次新增 0 条 |
| B3 | 清洗 | 去 script/style、压缩空白、去掉导航残渣；正文长度 < 80 字丢弃 | 单测：脏 HTML → 干净 text |
| B4 | 分类与关键词 | 关键词表 `召回/政策/补贴/电池/芯片` → category + keywords[] | 召回新闻必为 `risk` |
| B5 | 源 1 实现 | `miit_policy.py` | fixture 至少解析出 5 条 |
| B6 | 源 2 实现 | `ev_news.py` | fixture 至少 8 条 |
| B7 | 源 3 实现 | `oem_news.py` | fixture 至少 5 条 |
| B8 | 写入 MySQL | 只通过 schemas 定义的字段；写 `crawler_task` 统计：抓取数/清洗数/新增/重复 | 日志格式固定见下 |
| B9 | 给 A 的调用入口 | `run_crawl(source_id: str | "all") -> CrawlResult` | A 不需要知道解析细节 |
| B10 | 限速与失败 | 1 秒/请求；单源失败不影响其他源；写入 `job_log` | 故意把一个源 URL 配错，另外两个仍成功 |

**B 必须打出的控制台日志（答辩用，格式锁死，让 AI 按这个 print）：**

```
[crawl] source=ev_news mode=fixture
[crawl] fetched=20 parsed=18 dropped_short=2
[clean] done
[db] inserted=4 duplicated=14
[crawl] finished task_id=...
```

**给 AI 的约束：**

- 禁止把全站爬虫框架（Scrapy 分布式、代理池）写进来  
- 选择器写在每个源的 `selectors.py`，不要散落  
- 所有网络请求必须能被 `mode=fixture` 短路  

**B 的独立演示：** 点采集 → 看上述日志 → 打开 MySQL 看 `news` 和 `crawler_task`。

---

## 7. 成员 C——RAGFlow 企业知识库

**职责边界：** 文档进知识库、检索带引用。不负责行业新闻分析口径（那是 D），不负责页面（那是 E）。

**技术：** RAGFlow HTTP API、本目录下的 `ragflow_client.py`。解析/切分/Embedding **用 RAGFlow 自带能力**，不要自己再造一套向量库。

### 语料（答辩专用，放 `fixtures/docs/`）

至少 8 份，其中 2 份必须含「只有内部才知道」的数字：

| 文档 | 埋点（现场必问） |
|---|---|
| `X1产品说明书.pdf` | 「最大日处理能力为 6800 件」，第 13 页 |
| `产品对比-内部口径.docx` | 「A 产品较竞品续航高 12%」 |
| 行业报告 × 3、竞品简介 × 2、本公司简介 × 1 | 支撑分析类问题 |

### 任务卡

| ID | 任务 | 让 AI 生成 | 验收 |
|---|---|---|---|
| C1 | RAGFlow 部署说明 | `services/rag/README.md` + compose 片段 | 组员按文档能打开 RAGFlow 控制台 |
| C2 | Client 封装 | `create_dataset` `upload` `parse` `retrieve` | 全部用 httpx，超时和重试写死 |
| C3 | 引用结构 | retrieve 映射为 `citations[{doc,page,snippet,score}]` | 与 OpenAPI 一致 |
| C4 | 入库脚本 | `scripts/ingest_fixtures.py` 上传 fixtures/docs | 一键 ingest，输出文档数 |
| C5 | 元数据落库 | 上传成功后写 `knowledge_doc` | 前端知识库页能列出文件名 |
| C6 | 给 A 的 search | `search(query, top_k=5)` | 问「X1 最大日处理能力」命中说明书，snippet 含 6800 |
| C7 | 对比演示开关 | `naive_llm_answer()` 不检索 vs `rag_answer()` | 同一问题两种结果可并排返回，供前端展示 |
| C8 | 失败降级 | RAGFlow 不可用时返回 `rag_unavailable`，不编造引用 | 单测 mock 500 |
| C9 | 切分说明（答辩讲稿） | 文档里写清 chunk 约 256～512 token、重叠、为什么用 RAGFlow 解析 PDF | 口播 30 秒即可，不必自研切分器 |

**给 AI 的约束：**

- 不要手写 FAISS/Chroma「再实现一个 RAG」来替代 RAGFlow（老师要求的是 RAGFlow）  
- 引用里禁止假页码；拿不到 page 就 `page: null`  
- Prompt 里必须要求「没有检索结果就说不知道」  

**C 的独立演示：** 先问无知识库的模型 → 再走 RAG → 指出「6800 件」和来源页码。

---

## 8. 成员 D——Dify Workflow 与情报智能

**职责边界：** Prompt、工作流编排、报告结构、风险等级。能进代码的尽量进 `services/ai`（模板、规则、JSON schema），Dify 只做可视化编排，方便答辩打开节点图。

**技术：** Dify Workflow 3 条；工具全部指向成员 A 已发布的 HTTP 接口；Prompt 文件进 Git。

### 三条工作流（节点写死，按这个在 Dify 里搭，也让 AI 先写节点说明）

**WF1 企业知识问答 `wf_knowledge_qa`**

```
Start(query)
  → HTTP GET /api/knowledge/search
  → LLM（只根据 citations 回答，输出 answer + citations）
  → Answer
```

**WF2 行业情报周报 `wf_industry_brief`**

```
Start(range=7d)
  → HTTP GET /api/news?days=7
  → Code（按 category 分组）
  → LLM（填报告模板）
  → HTTP POST 写 /api 落库 report
  → Answer(markdown 报告)
```

报告模板锁死六个标题，便于答辩和前端渲染：

1. 本周行业概况  
2. 重要政策  
3. 重点企业动态  
4. 技术进展  
5. 市场动态  
6. 趋势与建议  

**WF3 风险研判 `wf_risk_alert`**

```
Start(news_id)
  → HTTP GET /api/news/{id}
  → LLM（分类 + level + summary）
  → If/Else (level in high, critical)
       → HTTP GET /api/knowledge/search（查本公司是否相关）
       → LLM（impact + suggestion + citations）
  → HTTP POST /api/notify/dingtalk  （由 A/E 真正发送，D 只决定是否发）
  → Answer(alert JSON)
```

### 任务卡

| ID | 任务 | 让 AI 生成 | 验收 |
|---|---|---|---|
| D1 | JSON Schema | `alert` 与 `report` 的输出 schema，给 LLM 强制 JSON | 非法 JSON 能被校验拦住 |
| D2 | Prompt 仓库 | `services/ai/prompts/*.md` 每个 WF 一份 | 人能直接贴进 Dify |
| D3 | 规则兜底 | 标题/正文含「召回」「停产」「断供」时，level 不低于 high | 即使 LLM 说 low，规则可上调（答辩很加分） |
| D4 | 周报模板 | Jinja 或 markdown 模板 | 缺某类新闻时写「本周未监测到」而不是编造 |
| D5 | Dify 工具清单 | 每个 HTTP 工具的 URL、方法、参数表 | 组员按表在 Dify 配工具，不必猜 |
| D6 | WF1 配置说明 + 导出 DSL | `services/ai/dify/wf_knowledge_qa.json` | 导入 Dify 能跑 X1 问题 |
| D7 | WF2 | 同上 | 用种子 7 天新闻能出六段报告 |
| D8 | WF3 | 同上 | 召回新闻 → high → 含 impact/suggestion |
| D9 | 给 A 的调用约定 | `dify_client.run(workflow_key, inputs)` | A 只传 key 和 inputs |
| D10 | 评测集 | 20 条问题和期望（含 3 条必须拒答） | 现场可抽问 |

**给 AI 的约束：**

- Prompt 必须要求：不引用检索结果以外的内部数字  
- LLM 输出只允许 JSON，markdown 报告由模板渲染，避免自由发挥导致前端难解析  
- Dify 节点顺序按上面画的来，不要额外加 10 个节点  

**D 的独立演示：** 打开 Dify 画布，走一遍 WF3，让老师看到 `Start → HTTP → LLM → If/Else → Answer`。

---

## 9. 成员 E——前端 + 钉钉 + 邮件

**职责边界：** 把中台结果展示出来、把预警推出去。不做爬虫、不改 Prompt。前端先对接 **Mock**（MSW 或静态 json），A 的接口通了再换 baseURL。

**技术：** Vue 3 + Vite + Vue Router + 少量 CSS（不要上大后台模板）；钉钉自定义机器人 webhook；SMTP（开发用 Mailhog）。

### 页面（只做 5 个，每个一屏一件事）

| 路由 | 一屏只做一件事 | 调的接口 |
|---|---|---|
| `/` | 今日采集数、预警数、最近 5 条新闻 | news + alerts 摘要 |
| `/assistant` | 一个问题框 + 回答 + 引用列表 | `/api/chat` |
| `/knowledge` | 上传 + 文档列表 + 试检索 | upload/search |
| `/intel` | 新闻时间线 + 生成周报按钮 + 报告原文 | news + analyze + reports |
| `/alerts` | 预警列表 + 「推送到钉钉/邮件」 | alerts + notify |

视觉要求（避免做成通用后台）：

- 产品名「智讯通」在首页是主视觉，不是导航小字  
- 首页用一张真实的资讯/车间/车展类图片或资讯流作主视觉，不要纯色底 + 卡片墙  
- 新闻列表就是列表，不要每条都做成卡片仪表盘  

### 任务卡

| ID | 任务 | 让 AI 生成 | 验收 |
|---|---|---|---|
| E1 | 前端脚手架 | Vite Vue3、路由、统一 `api.ts` | 五路由能切 |
| E2 | Mock | `apps/web/mock/*.json` 与 OpenAPI 同结构 | 后端没开也能演示 UI |
| E3 | 首页 | 数字 + 最近新闻 | 能看到召回那条 |
| E4 | 助手页 | 流式可后做；先整包返回。展示 citations | 引用可点击显示 doc/page |
| E5 | 知识库页 | 上传进度、列表、检索框 | 上传调用 A 的 upload |
| E6 | 情报页 | 筛选 category；一键生成周报 | 报告六个标题可见 |
| E7 | 预警页 | 按 level 着色；详情用 alert JSON | high/critical 更醒目 |
| E8 | 钉钉 | `services/notify/dingtalk.py` 拼 markdown | 自定义机器人收到预警卡片 |
| E9 | 邮件 | SMTP + HTML 模板（日报/预警两套） | Mailhog 能看到信；正文含报告六段 |
| E10 | 演示按钮 | 「跑一次召回闭环」调用 A 的 demo 接口 | 1 次点击走完采集→研判→双通道通知 |

钉钉文案锁死（让 AI 按模板拼，不要自由发挥）：

```
【智讯通·行业重要事件提醒】
企业：{company}
事件：{title}
风险等级：{level}
影响分析：{impact}
建议：{suggestion}
```

**E 的独立演示：** 钉钉群机器人弹出上述格式；邮箱收到《新能源汽车行业风险事件分析报告》。

---

## 10. 协作关系（答辩就用这张图）

不要说「五个人各做一块」。说「一条流水线，五段工序」。

```
B 采集/清洗/入库
        ↓
A FastAPI 中台（鉴权、调度、日志、Swagger）
        ↓
    ┌───┴────┐
    C RAG检索  D 研判/报告
    └───┬────┘
        ↓
E 页面展示 + 钉钉 + 邮件
```

接口所有权：

- **字段名冲突只改 schemas，开 10 分钟站会**  
- A 提供 Mock Client，C/D/E 前半段不阻塞  
- 联调只在最后 3 天：A 关掉 mock，指向真实 B/C/D/E  

建议 Git：`main` 保护；每人 `feat/a-api`、`feat/b-crawler`…；契约变更走 `feat/schemas` 由 A 合并。

---

## 11. 建议排期（约 10 个工作日）

| 天 | 全组 | A | B | C | D | E |
|---|---|---|---|---|---|---|
| 1 | 冻结契约、建仓、compose | schemas + OpenAPI + 空路由 | 表结构对齐 | 部署 RAGFlow | 建 Dify 应用 | 前端脚手架 + mock |
| 2–3 | | 登录、新闻 API、mock 客户端 | 框架+清洗+去重+3 个 fixture 源 | client + 上传 fixtures | Prompt + schema + 规则兜底 | 五页面用 mock 跑通 |
| 4–5 | | 接 B 入库；调度 | 接真源（能连则连） | ingest + search 验收 6800 | 搭 WF1/WF2 | 接真实 news API |
| 6–7 | | 接 C/D | 任务状态给 A | 对比演示接口 | 搭 WF3 + 导出 DSL | 钉钉/邮件 + Mailhog |
| 8 | 联调召回闭环 | demo 开关 | 保证种子新闻可插入 | 保证说明书可检索 | 保证 high 级告警 | 一键演示按钮 |
| 9 | 修演示脚本、补日志 | Swagger 演示路径 | 控制台日志美化 | 准备对比问句 | 打开画布演练 | 真机钉钉/邮箱 |
| 10 | 预答辩 | 架构 2 分钟 | 采集 3 分钟 | RAG 3 分钟 | Dify 3 分钟 | 触达 3 分钟 + 全组 4 分钟闭环 |

---

## 12. 每人给 Cursor 的「项目规则」摘要

把下面几句放进各自目录的 `AGENTS.md`，能明显提高 AI 一次写对的概率。

**全员：** 只使用 `packages/schemas` 中的字段名；时间一律 ISO8601；分类/风险枚举不准自造。

**A：** 外部系统全是可替换 Client；路由不写业务。

**B：** 默认 `CRAWL_MODE=fixture`；选择器与蜘蛛分离；去重用 hash。

**C：** 只封装 RAGFlow；引用结构固定；禁止假页码。

**D：** 模型只出 JSON；报告用模板；召回类关键词规则可升级风险。

**E：** 先 mock 后真实；钉钉/邮件用固定模板；页面不得超过约定的 5 个路由。

---

## 13. 答辩 18 分钟节奏

| 时间 | 谁 | 内容 |
|---|---|---|
| 0–2 | A | 背景：企业情报分散；架构图；为何中台是 FastAPI |
| 2–5 | B | 3 源、清洗去重、现场采集日志 + 数据库 |
| 5–8 | C | RAGFlow 链路；6800 件对比演示 |
| 8–11 | D | 三张 Workflow 图；风险 JSON；规则兜底 |
| 11–14 | E | 页面走查；钉钉/邮件模板 |
| 14–18 | 全组 | **一条召回闭环**（见下） |
| 18–20 | A | 成果数字 + 分工是流水线不是拼盘 |

### 最后 4 分钟闭环（唯一主演示）

1. E 点「跑一次召回闭环」（或 B 点开始采集，fixture 含召回稿）  
2. B 日志出现 `inserted` / `duplicated`  
3. A 的 `GET /api/news` 能看到该条  
4. D 的 WF3：`risk` + `high`  
5. C 检索本公司文档，给出是否相关与引用  
6. 钉钉弹出锁定文案，邮箱同时到达  

不要五人各演示五套互不相干的功能。

---

## 14. 成果口径（可按最终数字改）

- 技术栈：Python、FastAPI、MySQL、RAGFlow、Dify、httpx/BS4、Vue3、钉钉机器人、SMTP  
- 数据源：3 个（fixture + 可选 live）  
- 知识库：8～20 份文档（含 2 个埋点）  
- Dify：3 条 Workflow  
- FastAPI：14 个业务接口 + `/health`  
- MySQL：8 张表  
- 能力：问答、检索引用、周报、预警、钉钉、邮件  

---

## 15. 给组长的一句话

先让 AI 把 **契约和空壳** 写出来，再让五个人对着同一份 JSON 填实现。谁先做完谁先用 mock 演示；最后三天只干一件事：把「召回新闻 → 高风险 → 钉钉/邮件」跑稳定。
