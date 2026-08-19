from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.common import PageMeta
from schemas.enums import ReportKind


class AnalyzeIn(BaseModel):
    range_days: int = Field(default=7, ge=1, le=30)


class ReportOut(BaseModel):
    id: Optional[int] = None
    title: str
    kind: ReportKind = ReportKind.weekly
    range_days: int = 7
    content_md: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReportListOut(BaseModel):
    items: list[ReportOut]
    meta: PageMeta
