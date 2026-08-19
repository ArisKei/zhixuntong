from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.db import get_db
from app.deps import get_clients
from app.security import get_current_user
from app.services.chat import chat
from schemas.chat import ChatIn, ChatOut

router = APIRouter(prefix="/api", tags=["ai"], dependencies=[Depends(get_current_user)])


@router.post("/chat", response_model=ChatOut)
def chat_api(
    body: ChatIn,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> ChatOut:
    return chat(db, clients, body)
