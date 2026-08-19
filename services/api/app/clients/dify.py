from collections import defaultdict

from app.clients.rag import COMPARE_CITATION, X1_CITATION
from app.errors import AppError


def _brief_markdown(news_items: list[dict], range_days: int) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in news_items:
        grouped[item.get("category") or "other"].append(f"- {item.get('title')}")

    def section(key: str, empty: str) -> str:
        lines = grouped.get(key) or []
        return "\n".join(lines) if lines else empty

    return "\n".join(
        [
            f"# 新能源汽车行业智能情报周报（近{range_days}天）",
            "",
            "## 一、本周行业概况",
            f"监测新闻 {len(news_items)} 条。",
            "",
            "## 二、重要政策",
            section("policy", "本周未监测到"),
            "",
            "## 三、重点企业动态",
            section("company", "本周未监测到"),
            "",
            "## 四、技术进展",
            section("tech", "本周未监测到"),
            "",
            "## 五、市场动态",
            section("market", "本周未监测到"),
            "",
            "## 六、趋势与建议",
            "关注召回与政策窗口，核对本公司产品口径是否需要更新。",
        ]
    )


class MockDifyClient:
    def run(self, workflow_key: str, inputs: dict) -> dict:
        if workflow_key == "wf_knowledge_qa":
            citations = inputs.get("citations") or []
            if citations:
                first = citations[0]
                page = first.get("page")
                page_text = f"第{page}页" if page is not None else "未知页"
                answer = f"{first.get('snippet')}\n来源：《{first.get('doc')}》{page_text}"
            else:
                answer = "知识库中未检索到相关内容，无法回答。"
            return {"answer": answer, "citations": citations, "workflow": workflow_key}

        if workflow_key == "wf_industry_brief":
            news_items = inputs.get("news") or []
            range_days = int(inputs.get("range_days") or 7)
            return {
                "title": f"新能源汽车行业智能情报周报（近{range_days}天）",
                "kind": "weekly",
                "range_days": range_days,
                "content_md": _brief_markdown(news_items, range_days),
            }

        if workflow_key == "wf_risk_alert":
            news = inputs.get("news") or {}
            text = f"{news.get('title', '')}{news.get('content', '')}"
            level = "low"
            if any(token in text for token in ("事故", "关税", "停产")):
                level = "medium"
            if any(token in text for token in ("召回", "断供", "停产")):
                level = "high"
            if "紧急" in text:
                level = "critical"
            high = level in {"high", "critical"}
            return {
                "level": level,
                "company": news.get("company") or "未知企业",
                "title": news.get("title") or "",
                "summary": (news.get("content") or "")[:120],
                "impact": "可能影响品牌信誉及供应链订单" if high else "短期舆论影响有限，持续观察即可。",
                "suggestion": "核对本公司是否使用相关零部件" if high else "纳入日常情报观察列表。",
                "citations": [X1_CITATION.model_dump(), COMPARE_CITATION.model_dump()] if high else [],
            }

        raise AppError("unknown_workflow", f"未知工作流: {workflow_key}", 400)


class HttpDifyClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def run(self, workflow_key: str, inputs: dict) -> dict:
        import httpx

        try:
            response = httpx.post(
                f"{self.base_url}/v1/workflows/run",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"workflow_key": workflow_key, "inputs": inputs},
                timeout=60,
            )
            response.raise_for_status()
        except Exception as exc:
            raise AppError("dify_unavailable", "Dify 不可用", 503) from exc
        payload = response.json()
        return payload.get("data") or payload
