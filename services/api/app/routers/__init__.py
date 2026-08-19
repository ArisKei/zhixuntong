from fastapi import APIRouter

from app.routers import alert, analyze, auth, chat, crawler, health, knowledge, news, notify

api_routers: list[APIRouter] = [
    health.router,
    auth.router,
    crawler.router,
    news.router,
    knowledge.router,
    chat.router,
    analyze.router,
    alert.router,
    notify.router,
]
