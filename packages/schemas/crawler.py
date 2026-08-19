from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.enums import TaskStatus
from schemas.news import NewsOut


class CrawlerStartIn(BaseModel):
    source_id: str = Field(
        default="all",
        description="miit_policy | ev_news | oem_news | all | demo_recall",
        examples=["all"],
    )


class CrawlerTaskOut(BaseModel):
    task_id: str
    source_id: str
    status: TaskStatus
    fetched: int = 0
    parsed: int = 0
    dropped_short: int = 0
    inserted: int = 0
    duplicated: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CrawlResult(CrawlerTaskOut):
    """成员 B 的 run_crawl() 返回值。A 在 local 模式下消费。"""

    items: list[NewsOut] = Field(default_factory=list)
