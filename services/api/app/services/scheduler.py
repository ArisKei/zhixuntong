from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from zoneinfo import ZoneInfo

from app.config import settings
from app.db import SessionLocal
from app.logging import get_logger
from app.services.analyze import analyze
from app.services.crawler import start_crawler
from app.services.notify import send_email
from schemas.crawler import CrawlerStartIn
from schemas.notify import EmailNotifyIn
from schemas.report import AnalyzeIn


def attach_scheduler(app: FastAPI) -> None:
    if not settings.scheduler_enabled:
        get_logger("scheduler").info("scheduler_disabled")
        return

    scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Shanghai"))

    def morning_crawl() -> None:
        db = SessionLocal()
        try:
            start_crawler(db, app.state.clients, CrawlerStartIn(source_id="all"))
        except Exception:
            get_logger("scheduler").exception("morning_crawl_failed")
        finally:
            db.close()

    def evening_report() -> None:
        db = SessionLocal()
        try:
            report = analyze(db, app.state.clients, AnalyzeIn(range_days=1))
            send_email(db, app.state.clients, EmailNotifyIn(kind="daily", report_id=report.id))
        except Exception:
            get_logger("scheduler").exception("evening_report_failed")
        finally:
            db.close()

    scheduler.add_job(morning_crawl, "cron", hour=8, minute=0, id="morning_crawl")
    scheduler.add_job(evening_report, "cron", hour=18, minute=0, id="evening_report")
    scheduler.start()
    app.state.scheduler = scheduler
    get_logger("scheduler").info("scheduler_started")
