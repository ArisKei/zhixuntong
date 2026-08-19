from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.db import get_db
from app.deps import get_clients
from app.security import get_current_user
from app.services.notify import send_dingtalk, send_email
from schemas.notify import DingTalkNotifyIn, EmailNotifyIn, NotifyOut

router = APIRouter(prefix="/api/notify", tags=["notify"], dependencies=[Depends(get_current_user)])


@router.post("/dingtalk", response_model=NotifyOut)
def dingtalk_api(
    body: DingTalkNotifyIn,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> NotifyOut:
    return send_dingtalk(db, clients, body)


@router.post("/email", response_model=NotifyOut)
def email_api(
    body: EmailNotifyIn,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> NotifyOut:
    return send_email(db, clients, body)
