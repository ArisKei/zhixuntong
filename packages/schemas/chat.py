from pydantic import BaseModel, Field

from schemas.common import Citation


class ChatIn(BaseModel):
    query: str = Field(min_length=1, examples=["X1产品最大日处理能力是多少？"])


class ChatOut(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    workflow: str = "wf_knowledge_qa"
