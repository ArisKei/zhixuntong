from typing import Optional

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str


class Citation(BaseModel):
    doc: str
    page: Optional[int] = None
    snippet: str
    score: Optional[float] = None


class PageMeta(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
