from typing import Optional

from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.config import settings
from app.services.logutil import write_job_log
from schemas.crawler import CrawlerStartIn, CrawlerTaskOut


def start_crawler(db: Session, clients: Clients, body: CrawlerStartIn) -> CrawlerTaskOut:
    result = clients.crawler.start(db, body.source_id, settings.demo_mode)
    write_job_log(
        db,
        "crawler",
        f"source={result.source_id} inserted={result.inserted} duplicated={result.duplicated}",
        extra=result.model_dump(mode="json"),
    )
    return result


def crawler_status(db: Session, clients: Clients, task_id: Optional[str]) -> CrawlerTaskOut:
    return clients.crawler.status(db, task_id)
