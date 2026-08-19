from dataclasses import dataclass

from app.clients.crawler import HttpCrawlerClient, LocalCrawlerClient, MockCrawlerClient
from app.clients.dify import HttpDifyClient, MockDifyClient
from app.clients.notify import HttpNotifyClient, LogNotifyClient
from app.clients.protocols import CrawlerClient, DifyClient, NotifyClient, RagClient
from app.clients.rag import HttpRagClient, MockRagClient
from app.config import settings


@dataclass
class Clients:
    crawler: CrawlerClient
    rag: RagClient
    dify: DifyClient
    notify: NotifyClient


def build_clients() -> Clients:
    crawler: CrawlerClient
    if settings.crawler_mode == "http":
        crawler = HttpCrawlerClient(settings.crawler_base_url)
    elif settings.crawler_mode == "local":
        crawler = LocalCrawlerClient()
    else:
        crawler = MockCrawlerClient()

    rag: RagClient = HttpRagClient(settings.rag_base_url) if settings.rag_mode == "http" else MockRagClient()
    dify: DifyClient = (
        HttpDifyClient(settings.dify_base_url, settings.dify_api_key)
        if settings.dify_mode == "http"
        else MockDifyClient()
    )
    notify: NotifyClient = (
        HttpNotifyClient(
            settings.dingtalk_webhook,
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_from,
        )
        if settings.notify_mode == "http"
        else LogNotifyClient()
    )
    return Clients(crawler=crawler, rag=rag, dify=dify, notify=notify)
