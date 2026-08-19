from sqlalchemy.orm import Session

from app.clients.factory import Clients
from schemas.chat import ChatIn, ChatOut
from schemas.common import Citation


def chat(db: Session, clients: Clients, body: ChatIn) -> ChatOut:
    citations = clients.rag.search(db, body.query, top_k=5)
    payload = clients.dify.run(
        "wf_knowledge_qa",
        {"query": body.query, "citations": [item.model_dump() for item in citations]},
    )
    raw_citations = payload.get("citations") or [item.model_dump() for item in citations]
    parsed = [Citation.model_validate(item) for item in raw_citations]
    return ChatOut(
        answer=payload.get("answer") or "",
        citations=parsed,
        workflow=payload.get("workflow") or "wf_knowledge_qa",
    )
