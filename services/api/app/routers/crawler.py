from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.db import get_db
from app.deps import get_clients
from app.security import get_current_user
from app.services.crawler import crawler_status, start_crawler
from schemas.crawler import CrawlerStartIn, CrawlerTaskOut

router = APIRouter(prefix="/api/crawler", tags=["crawler"], dependencies=[Depends(get_current_user)])


@router.post("/start", response_model=CrawlerTaskOut)
def start(
    body: CrawlerStartIn,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> CrawlerTaskOut:
    return start_crawler(db, clients, body)


@router.get("/status", response_model=CrawlerTaskOut)
def status(
    task_id: Optional[str] = None,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> CrawlerTaskOut:
    return crawler_status(db, clients, task_id)
