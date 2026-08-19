from sqlalchemy.orm import Session

from app.clients.factory import Clients
from schemas.knowledge import KnowledgeSearchOut, KnowledgeUploadOut


def upload_document(db: Session, clients: Clients, filename: str, content: bytes) -> KnowledgeUploadOut:
    document = clients.rag.upload(db, filename, content)
    return KnowledgeUploadOut(document=document)


def search_knowledge(db: Session, clients: Clients, query: str, top_k: int) -> KnowledgeSearchOut:
    documents = clients.rag.list_documents(db)
    citations = clients.rag.search(db, query, top_k) if query.strip() else []
    return KnowledgeSearchOut(query=query, citations=citations, documents=documents)
