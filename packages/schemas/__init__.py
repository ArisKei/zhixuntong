"""全组唯一数据契约。字段名变更必须由组长合并。"""

from schemas.alert import AlertEvaluateIn, AlertListOut, AlertOut
from schemas.auth import LoginIn, TokenOut, UserOut
from schemas.chat import ChatIn, ChatOut
from schemas.common import Citation, ErrorBody, PageMeta
from schemas.crawler import CrawlerStartIn, CrawlerTaskOut, CrawlResult
from schemas.enums import NewsCategory, ReportKind, RiskLevel, TaskStatus
from schemas.knowledge import KnowledgeDocOut, KnowledgeSearchOut, KnowledgeUploadOut
from schemas.news import NewsListOut, NewsOut
from schemas.notify import DingTalkNotifyIn, EmailNotifyIn, NotifyOut
from schemas.report import AnalyzeIn, ReportListOut, ReportOut

__all__ = [
    "AlertEvaluateIn",
    "AlertListOut",
    "AlertOut",
    "AnalyzeIn",
    "ChatIn",
    "ChatOut",
    "Citation",
    "CrawlerStartIn",
    "CrawlerTaskOut",
    "CrawlResult",
    "DingTalkNotifyIn",
    "EmailNotifyIn",
    "ErrorBody",
    "KnowledgeDocOut",
    "KnowledgeSearchOut",
    "KnowledgeUploadOut",
    "LoginIn",
    "NewsCategory",
    "NewsListOut",
    "NewsOut",
    "NotifyOut",
    "PageMeta",
    "ReportKind",
    "ReportListOut",
    "ReportOut",
    "RiskLevel",
    "TaskStatus",
    "TokenOut",
    "UserOut",
]
