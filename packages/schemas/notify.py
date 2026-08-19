from typing import Literal, Optional

from pydantic import BaseModel, Field


class DingTalkNotifyIn(BaseModel):
    alert_id: str = Field(examples=["alrt_20260818_001"])


class EmailNotifyIn(BaseModel):
    kind: Literal["alert", "daily"] = "alert"
    alert_id: Optional[str] = None
    report_id: Optional[int] = None
    to: Optional[str] = Field(default=None, examples=["demo@example.com"])


class NotifyOut(BaseModel):
    ok: bool = True
    channel: str
    message: str
