from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import Citation


class KnowledgeDocOut(BaseModel):
    id: int
    filename: str
    dataset: str = "enterprise"
    status: str = "ready"
    chunk_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeUploadOut(BaseModel):
    document: KnowledgeDocOut


class KnowledgeSearchOut(BaseModel):
    query: str = ""
    citations: list[Citation] = Field(default_factory=list)
    documents: list[KnowledgeDocOut] = Field(default_factory=list)
