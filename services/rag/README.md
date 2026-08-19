# 成员 C：RAGFlow 封装服务

独立 HTTP 服务，暴露中台 `HttpRagClient` 已调用的两个端点，内部持 RAGFlow API Key 转发真 RAGFlow 并翻译字段。

契约：`packages/schemas/knowledge.py`、`packages/schemas/common.py`（`Citation`）、`docs/组员接口对照表.md` 第 2 节。

## 启动

需要 Python 3.9+。

```powershell
cd services/rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # 填 RAGFLOW_API_KEY / RAGFLOW_DATASET_ID
.\run.ps1
```

服务默认监听 `0.0.0.0:9380`（与中台默认 `RAG_BASE_URL` 一致）。

## 环境变量（services/rag/.env）

| 变量 | 说明 |
|---|---|
| `RAGFLOW_BASE_URL` | RAGFlow 地址，如 `http://192.168.10.210:8686` |
| `RAGFLOW_API_KEY` | RAGFlow 的 API Key（Bearer） |
| `RAGFLOW_DATASET_ID` | 数据集 UUID；留空时按名字 `enterprise` 自动查找 |

## 暴露的端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/datasets/enterprise/documents` | multipart `file`；上传 + 触发解析 |
| `POST` | `/api/v1/retrieval` | body `{"question","top_k"}`；返回 `{"chunks":[{document_name,page,content,score}]}` |

## 组长对接

1. 组长先启动本服务，再启动中台
2. 中台 `.env` 改为 `RAG_MODE=http`（`RAG_BASE_URL` 默认 `http://127.0.0.1:9380`，无需改动）

## 验收

问「X1 最大日处理能力」→ 检索返回 `content` 含 6800，且 `document_name` / `page` 有值（出处）。

```powershell
curl -X POST http://127.0.0.1:9380/api/v1/retrieval `
  -H "Content-Type: application/json" `
  -d '{"question":"X1最大日处理能力是多少","top_k":5}'
```
