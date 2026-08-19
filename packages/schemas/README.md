# 数据契约（全组只读，变更走组长）

字段名、枚举、接口路径以本目录和 `docs/openapi.yaml` 为准。组员实现时 **只消费、不改名**。

## 枚举

- `category`: `policy` | `company` | `market` | `tech` | `risk` | `other`
- `level`: `low` | `medium` | `high` | `critical`
- `task.status`: `pending` | `running` | `success` | `failed`

## 给组员的入口签名（对接 A 的 mock/local）

**成员 B**

```python
def run_crawl(source_id: str) -> CrawlResult: ...
```

**成员 C**

```python
def search(query: str, top_k: int = 5) -> list[Citation]: ...
def upload(filename: str, content: bytes) -> KnowledgeDocOut: ...
```

**成员 D**

```python
def run(workflow_key: str, inputs: dict) -> dict: ...
# workflow_key: wf_knowledge_qa | wf_industry_brief | wf_risk_alert
```

**成员 E**

```python
def send_dingtalk(alert: AlertOut) -> None: ...
def send_email(kind: str, payload: dict) -> None: ...
```
