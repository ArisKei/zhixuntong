from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.common import Citation, PageMeta
from schemas.enums import RiskLevel


class AlertEvaluateIn(BaseModel):
    news_id: int = Field(examples=[1])


class AlertOut(BaseModel):
    alert_id: str
    level: RiskLevel
    company: str
    title: str
    summary: str
    impact: str
    suggestion: str
    news_id: int
    citations: list[Citation] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertListOut(BaseModel):
    items: list[AlertOut]
    meta: PageMeta
