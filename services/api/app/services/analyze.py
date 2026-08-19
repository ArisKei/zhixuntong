from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.models import Report
from app.services.news import list_news
from schemas.enums import ReportKind
from schemas.report import AnalyzeIn, ReportListOut, ReportOut
from schemas.common import PageMeta


def analyze(db: Session, clients: Clients, body: AnalyzeIn) -> ReportOut:
    news = list_news(db, days=body.range_days, page=1, page_size=100)
    payload = clients.dify.run(
        "wf_industry_brief",
        {
            "range_days": body.range_days,
            "news": [item.model_dump(mode="json") for item in news.items],
        },
    )
    row = Report(
        title=payload.get("title") or f"新能源汽车行业智能情报周报（近{body.range_days}天）",
        kind=payload.get("kind") or ReportKind.weekly.value,
        range_days=body.range_days,
        content_md=payload.get("content_md") or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ReportOut.model_validate(row)


def list_reports(db: Session, page: int = 1, page_size: int = 20) -> ReportListOut:
    query = db.query(Report)
    total = query.count()
    rows = query.order_by(Report.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReportListOut(
        items=[ReportOut.model_validate(row) for row in rows],
        meta=PageMeta(total=total, page=page, page_size=page_size),
    )
