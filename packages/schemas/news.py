from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.common import PageMeta
from schemas.enums import NewsCategory


class NewsOut(BaseModel):
    id: int
    title: str
    published_at: datetime
    source: str
    source_url: str
    category: NewsCategory
    company: Optional[str] = None
    content: str
    content_hash: str
    keywords: list[str] = Field(default_factory=list)
    is_duplicate: bool = False

    model_config = {"from_attributes": True}


class NewsListOut(BaseModel):
    items: list[NewsOut]
    meta: PageMeta
