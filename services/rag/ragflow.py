"""成员 C：RAGFlow 封装核心库。

只依赖 httpx + 标准库，供 `main.py`（本目录的 FastAPI 服务）调用。
环境变量见 `.env.example`。

返回类型复用 `packages/schemas` 的契约模型，保证与中台字段一致。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# 独立运行/测试时也能 import 到 packages/schemas（与中台 paths.py 一致）
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGES_DIR = _REPO_ROOT / "packages"
if str(_PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGES_DIR))

from schemas.common import Citation  # noqa: E402
from schemas.knowledge import KnowledgeDocOut  # noqa: E402

DEFAULT_DATASET_NAME = "enterprise"
_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_dotenv() -> None:
    """按需加载 services/rag/.env（只补缺，不覆盖已存在的环境变量）。"""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class RagflowError(Exception):
    """RAGFlow 调用失败。main.py 捕获后转 503。"""


@dataclass
class RagflowConfig:
    base_url: str
    api_key: str
    dataset_id: str


def build_config() -> RagflowConfig:
    _load_dotenv()
    base_url = os.environ.get("RAGFLOW_BASE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("RAGFLOW_API_KEY", "").strip()
    dataset_id = os.environ.get("RAGFLOW_DATASET_ID", "").strip()
    if not base_url:
        raise RagflowError("缺少 RAGFLOW_BASE_URL（见 services/rag/.env.example）")
    if not api_key:
        raise RagflowError("缺少 RAGFLOW_API_KEY（见 services/rag/.env.example）")
    return RagflowConfig(base_url=base_url, api_key=api_key, dataset_id=dataset_id)


def _request(cfg: RagflowConfig, method: str, path: str, **kwargs) -> dict:
    url = f"{cfg.base_url}{path}"
    kwargs.setdefault("headers", {"Authorization": f"Bearer {cfg.api_key}"})
    kwargs.setdefault("timeout", 60)
    try:
        response = httpx.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise RagflowError(f"RAGFlow 不可达 {url}: {exc}") from exc
    if response.status_code >= 400:
        raise RagflowError(f"RAGFlow 返回 {response.status_code}: {response.text[:300]}")
    return response.json()


def _ensure_dataset_id(cfg: RagflowConfig) -> str:
    """优先用配置的 dataset_id；为空时按名字自动查找。"""
    if cfg.dataset_id:
        return cfg.dataset_id
    payload = _request(
        cfg,
        "GET",
        "/api/v1/datasets",
        params={"page": 1, "page_size": 100, "name": DEFAULT_DATASET_NAME},
    )
    data = payload.get("data") or []
    datasets = data.get("datasets") if isinstance(data, dict) else data
    for ds in datasets or []:
        if ds.get("name") == DEFAULT_DATASET_NAME:
            return ds["id"]
    raise RagflowError(
        f"未找到名为 '{DEFAULT_DATASET_NAME}' 的数据集，"
        "请在 RAGFlow 创建后在 .env 配置 RAGFLOW_DATASET_ID"
    )


def _parse_ts(value) -> Optional[datetime]:
    """RAGFlow 时间戳（Unix 秒或毫秒）转 datetime。"""
    if value in (None, ""):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num > 1e12:  # 毫秒
        num /= 1000
    return datetime.fromtimestamp(num)


def _extract_page(positions) -> Optional[int]:
    """从 chunk.positions 提取页码。

    RAGFlow 的 positions 因文档类型而异：纯文本常为 [""]，PDF 常为
    [[page, x1, y1, x2, y2], ...]。取第一个位置的第一个整数作为页码。
    """
    if not positions:
        return None
    first = positions[0]
    if isinstance(first, (list, tuple)) and first:
        num = first[0]
        if isinstance(num, int):
            return num
    return None


def _doc_id(raw) -> int:
    """RAGFlow 文档 id 是 UUID 字符串，契约 KnowledgeDocOut.id 是 int。

    中台 HttpRagClient 忽略本服务的 upload 响应体、list_documents 走 Mock，
    故该字段不承载真实语义；此处取 UUID 前 8 位 hex 转 int 作稳定标识。
    """
    s = str(raw or "").replace("-", "")
    if not s:
        return 0
    try:
        return int(s[:8], 16)
    except ValueError:
        return 0


def _doc_to_out(doc: dict) -> KnowledgeDocOut:
    run = (doc.get("run") or "").upper()
    if run == "DONE":
        status = "ready"
    elif run in ("RUNNING", "UNSTART", "PARSING"):
        status = "parsing"
    else:
        status = "failed"
    return KnowledgeDocOut(
        id=_doc_id(doc.get("id")),
        filename=doc.get("name") or "",
        dataset=DEFAULT_DATASET_NAME,
        status=status,
        chunk_count=doc.get("chunk_count") or 0,
        created_at=_parse_ts(doc.get("create_time")) or datetime.now(),
    )


def upload(filename: str, content: bytes) -> KnowledgeDocOut:
    """上传文档并触发解析，返回 KnowledgeDocOut。"""
    cfg = build_config()
    dataset_id = _ensure_dataset_id(cfg)

    # 查重：同名文档已存在则直接返回，避免重复上传
    existing = _request(
        cfg,
        "GET",
        f"/api/v1/datasets/{dataset_id}/documents",
        params={"page": 1, "page_size": 100, "name": filename},
    )
    ex_data = existing.get("data") or {}
    docs = ex_data.get("docs") if isinstance(ex_data, dict) else ex_data
    if isinstance(docs, dict):
        docs = docs.get("docs") or []
    for doc in docs or []:
        if doc.get("name") == filename:
            return _doc_to_out(doc)

    payload = _request(
        cfg,
        "POST",
        f"/api/v1/datasets/{dataset_id}/documents",
        files={"file": (filename, content)},
    )
    uploaded = (payload.get("data") or [{}])[0]
    doc_id = uploaded.get("id")

    if doc_id:
        # 触发解析（异步），让文档进入可检索状态
        _request(
            cfg,
            "POST",
            f"/api/v1/datasets/{dataset_id}/chunks",
            json={"document_ids": [doc_id]},
        )

    return KnowledgeDocOut(
        id=_doc_id(doc_id),
        filename=uploaded.get("name") or filename,
        dataset=DEFAULT_DATASET_NAME,
        status="parsing",
        chunk_count=0,
        created_at=_parse_ts(uploaded.get("create_time")) or datetime.now(),
    )


def search(query: str, top_k: int = 5) -> list[Citation]:
    """检索并转换为 Citation 列表。无结果时返回空列表（不抛错）。"""
    if not query.strip():
        return []
    cfg = build_config()
    dataset_id = _ensure_dataset_id(cfg)

    payload = _request(
        cfg,
        "POST",
        "/api/v1/retrieval",
        json={
            "question": query,
            "dataset_ids": [dataset_id],
            "top_k": top_k,
            "page": 1,
            "page_size": top_k,
        },
        timeout=30,
    )
    data = payload.get("data") or {}
    chunks = data.get("chunks") or []
    doc_aggs = data.get("doc_aggs") or []

    doc_name_by_id = {
        agg.get("doc_id"): agg.get("doc_name") for agg in doc_aggs if agg.get("doc_id")
    }

    citations: list[Citation] = []
    for chunk in chunks[:top_k]:
        doc_name = (
            doc_name_by_id.get(chunk.get("document_id"))
            or chunk.get("document_keyword")
            or "未知文档"
        )
        citations.append(
            Citation(
                doc=doc_name,
                page=_extract_page(chunk.get("positions")),
                snippet=chunk.get("content") or "",
                score=chunk.get("similarity"),
            )
        )
    return citations


def list_documents() -> list[KnowledgeDocOut]:
    """列出数据集内文档，映射为 KnowledgeDocOut。"""
    cfg = build_config()
    dataset_id = _ensure_dataset_id(cfg)
    payload = _request(
        cfg,
        "GET",
        f"/api/v1/datasets/{dataset_id}/documents",
        params={"page": 1, "page_size": 100},
    )
    data = payload.get("data") or {}
    docs = data.get("docs") if isinstance(data, dict) else data
    if isinstance(docs, dict):
        docs = docs.get("docs") or []
    return [_doc_to_out(doc) for doc in docs or []]
