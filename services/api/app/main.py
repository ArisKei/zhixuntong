from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import paths as _paths  # noqa: F401  先注入 packages 到 sys.path
from app.clients.factory import build_clients
from app.config import settings
from app.errors import AppError
from app.logging import setup_logging
from app.routers import api_routers
from app.services.bootstrap import init_db
from app.services.scheduler import attach_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    app.state.clients = build_clients()
    attach_scheduler(app)
    yield
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="智讯通中台：采集、知识库、研判、通知的统一入口。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in api_routers:
    app.include_router(router)


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.detail})


@app.exception_handler(RequestValidationError)
async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"code": "validation_error", "message": str(exc.errors())},
    )
