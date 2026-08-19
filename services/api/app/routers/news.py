from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import get_current_user
from app.services.news import get_news, list_news
from schemas.enums import NewsCategory
from schemas.news import NewsListOut, NewsOut

router = APIRouter(prefix="/api", tags=["news"], dependencies=[Depends(get_current_user)])


@router.get("/news", response_model=NewsListOut)
def news_list(
    category: Optional[NewsCategory] = None,
    days: Optional[int] = 7,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> NewsListOut:
    return list_news(db, category=category, days=days, page=page, page_size=page_size)


@router.get("/news/{news_id}", response_model=NewsOut)
def news_detail(news_id: int, db: Session = Depends(get_db)) -> NewsOut:
    return get_news(db, news_id)
