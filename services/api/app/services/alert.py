from datetime import datetime

from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.errors import AppError
from app.models import Alert
from app.services.news import get_news
from schemas.alert import AlertEvaluateIn, AlertListOut, AlertOut
from schemas.common import Citation, PageMeta
from schemas.enums import RiskLevel


def _to_out(row: Alert) -> AlertOut:
    return AlertOut(
        alert_id=row.alert_id,
        level=RiskLevel(row.level),
        company=row.company,
        title=row.title,
        summary=row.summary,
        impact=row.impact,
        suggestion=row.suggestion,
        news_id=row.news_id,
        citations=[Citation.model_validate(item) for item in (row.citations or [])],
        created_at=row.created_at,
    )


def evaluate_alert(db: Session, clients: Clients, body: AlertEvaluateIn) -> AlertOut:
    news = get_news(db, body.news_id)
    payload = clients.dify.run("wf_risk_alert", {"news": news.model_dump(mode="json")})
    citations = payload.get("citations") or []
    if payload.get("level") in {"high", "critical"} and not citations:
        citations = [item.model_dump() for item in clients.rag.search(db, news.title, top_k=3)]
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    row = Alert(
        alert_id=f"alrt_{stamp}_{body.news_id:03d}",
        level=payload.get("level") or RiskLevel.low.value,
        company=payload.get("company") or news.company or "未知企业",
        title=payload.get("title") or news.title,
        summary=payload.get("summary") or "",
        impact=payload.get("impact") or "",
        suggestion=payload.get("suggestion") or "",
        news_id=body.news_id,
        citations=citations,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def list_alerts(db: Session, page: int = 1, page_size: int = 20) -> AlertListOut:
    query = db.query(Alert)
    total = query.count()
    rows = query.order_by(Alert.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AlertListOut(items=[_to_out(row) for row in rows], meta=PageMeta(total=total, page=page, page_size=page_size))


def get_alert(db: Session, alert_id: str) -> AlertOut:
    row = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if row is None:
        raise AppError("alert_not_found", "预警不存在", 404)
    return _to_out(row)
