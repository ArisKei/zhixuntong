from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional
from uuid import uuid4
import json

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import CrawlerTask, News
from app.paths import REPO_ROOT
from schemas.crawler import CrawlerTaskOut
from schemas.enums import TaskStatus


def _now() -> datetime:
    return datetime.now()


def _task_out(task: CrawlerTask) -> CrawlerTaskOut:
    return CrawlerTaskOut(
        task_id=task.task_id,
        source_id=task.source_id,
        status=TaskStatus(task.status),
        fetched=task.fetched,
        parsed=task.parsed,
        dropped_short=task.dropped_short,
        inserted=task.inserted,
        duplicated=task.duplicated,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def load_seed_news() -> list[dict]:
    path = REPO_ROOT / "fixtures" / "seed" / "news.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    ordered = sorted(items, key=lambda row: row["published_at"])
    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    rebased: list[dict] = []
    last_index = len(ordered) - 1
    for index, row in enumerate(ordered):
        cloned = dict(row)
        cloned["published_at"] = (today - timedelta(days=last_index - index)).isoformat()
        rebased.append(cloned)
    return rebased


def insert_news_items(db: Session, items: list[dict]) -> tuple[int, int, int]:
    inserted = 0
    duplicated = 0
    dropped = 0
    for item in items:
        content = (item.get("content") or "").strip()
        if len(content) < 80:
            dropped += 1
            continue
        digest = sha256(f"{item['title']}{item['source_url']}".encode("utf-8")).hexdigest()
        exists = db.query(News).filter(News.content_hash == digest).first()
        if exists:
            duplicated += 1
            continue
        db.add(
            News(
                title=item["title"],
                published_at=_parse_dt(item["published_at"]),
                source=item["source"],
                source_url=item["source_url"],
                category=item["category"],
                company=item.get("company"),
                content=content,
                content_hash=digest,
                keywords=item.get("keywords") or [],
                is_duplicate=False,
            )
        )
        inserted += 1
    return inserted, duplicated, dropped


def get_task(db: Session, task_id: Optional[str]) -> CrawlerTask:
    if task_id:
        task = db.query(CrawlerTask).filter(CrawlerTask.task_id == task_id).first()
    else:
        task = db.query(CrawlerTask).order_by(CrawlerTask.id.desc()).first()
    if task is None:
        raise AppError("task_not_found", "没有采集任务", 404)
    return task


class MockCrawlerClient:
    def start(self, db: Session, source_id: str, demo_mode: bool) -> CrawlerTaskOut:
        task = CrawlerTask(
            task_id=uuid4().hex[:12],
            source_id=source_id,
            status=TaskStatus.running.value,
            started_at=_now(),
        )
        db.add(task)
        db.flush()

        items = load_seed_news()
        if source_id == "demo_recall" or (demo_mode and source_id == "demo_recall"):
            items = [row for row in items if "召回" in row["title"]]
        elif source_id not in ("all", ""):
            items = [row for row in items if row["source"] == source_id]
        if demo_mode and source_id == "all":
            items = load_seed_news()
        if demo_mode and not any("召回" in row["title"] for row in items):
            items.extend([row for row in load_seed_news() if "召回" in row["title"]])

        inserted, duplicated, dropped = insert_news_items(db, items)
        task.fetched = len(items)
        task.parsed = len(items) - dropped
        task.dropped_short = dropped
        task.inserted = inserted
        task.duplicated = duplicated
        task.status = TaskStatus.success.value
        task.finished_at = _now()
        db.commit()
        db.refresh(task)
        return _task_out(task)

    def status(self, db: Session, task_id: Optional[str]) -> CrawlerTaskOut:
        return _task_out(get_task(db, task_id))


class HttpCrawlerClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def start(self, db: Session, source_id: str, demo_mode: bool) -> CrawlerTaskOut:
        import httpx

        try:
            response = httpx.post(
                f"{self.base_url}/internal/crawl",
                json={"source_id": source_id, "demo_mode": demo_mode},
                timeout=60,
            )
            response.raise_for_status()
        except Exception as exc:
            raise AppError("crawler_unavailable", "采集服务不可用", 503) from exc
        payload = response.json()
        return CrawlerTaskOut.model_validate(payload)

    def status(self, db: Session, task_id: Optional[str]) -> CrawlerTaskOut:
        return MockCrawlerClient().status(db, task_id)


class LocalCrawlerClient:
    def start(self, db: Session, source_id: str, demo_mode: bool) -> CrawlerTaskOut:
        runner = REPO_ROOT / "services" / "crawler" / "runner.py"
        if not runner.exists():
            raise AppError("crawler_unavailable", "成员 B 的 run_crawl 尚未就绪", 503)
        import importlib.util

        spec = importlib.util.spec_from_file_location("zxt_crawler_runner", runner)
        if spec is None or spec.loader is None:
            raise AppError("crawler_unavailable", "无法加载成员 B 的 run_crawl", 503)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.run_crawl(source_id)
        return CrawlerTaskOut.model_validate(result)

    def status(self, db: Session, task_id: Optional[str]) -> CrawlerTaskOut:
        return MockCrawlerClient().status(db, task_id)
