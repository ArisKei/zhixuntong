from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import News
from schemas.common import PageMeta
from schemas.enums import NewsCategory
from schemas.news import NewsListOut, NewsOut


def _to_out(row: News) -> NewsOut:
    return NewsOut.model_validate(row)


def list_news(
    db: Session,
    category: Optional[NewsCategory] = None,
    days: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> NewsListOut:
    query = db.query(News)
    if category is not None:
        query = query.filter(News.category == category.value)
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        query = query.filter(News.published_at >= cutoff)
    total = query.count()
    rows = (
        query.order_by(News.published_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return NewsListOut(items=[_to_out(row) for row in rows], meta=PageMeta(total=total, page=page, page_size=page_size))


def get_news(db: Session, news_id: int) -> NewsOut:
    row = db.get(News, news_id)
    if row is None:
        raise AppError("news_not_found", "新闻不存在", 404)
    return _to_out(row)
