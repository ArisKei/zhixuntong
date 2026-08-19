from typing import Optional, Protocol

from sqlalchemy.orm import Session

from schemas.alert import AlertOut
from schemas.common import Citation
from schemas.crawler import CrawlerTaskOut
from schemas.knowledge import KnowledgeDocOut


class CrawlerClient(Protocol):
    def start(self, db: Session, source_id: str, demo_mode: bool) -> CrawlerTaskOut: ...

    def status(self, db: Session, task_id: Optional[str]) -> CrawlerTaskOut: ...


class RagClient(Protocol):
    def upload(self, db: Session, filename: str, content: bytes) -> KnowledgeDocOut: ...

    def search(self, db: Session, query: str, top_k: int = 5) -> list[Citation]: ...

    def list_documents(self, db: Session) -> list[KnowledgeDocOut]: ...


class DifyClient(Protocol):
    def run(self, workflow_key: str, inputs: dict) -> dict: ...


class NotifyClient(Protocol):
    def send_dingtalk(self, alert: AlertOut) -> str: ...

    def send_email(self, kind: str, subject: str, body: str, to: Optional[str] = None) -> str: ...
