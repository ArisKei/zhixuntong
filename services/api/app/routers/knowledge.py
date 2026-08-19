from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.db import get_db
from app.deps import get_clients
from app.security import get_current_user
from app.services.knowledge import search_knowledge, upload_document
from schemas.knowledge import KnowledgeSearchOut, KnowledgeUploadOut

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])


@router.post("/upload", response_model=KnowledgeUploadOut)
async def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> KnowledgeUploadOut:
    content = await file.read()
    filename = file.filename or "untitled.bin"
    return upload_document(db, clients, filename, content)


@router.get("/search", response_model=KnowledgeSearchOut)
def search(
    query: str = "",
    top_k: int = 5,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> KnowledgeSearchOut:
    return search_knowledge(db, clients, query, top_k)
