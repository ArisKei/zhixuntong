from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.db import get_db
from app.deps import get_clients
from app.security import get_current_user
from app.services.analyze import analyze, list_reports
from schemas.report import AnalyzeIn, ReportListOut, ReportOut

router = APIRouter(prefix="/api", tags=["ai"], dependencies=[Depends(get_current_user)])


@router.post("/analyze", response_model=ReportOut)
def analyze_api(
    body: AnalyzeIn,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> ReportOut:
    return analyze(db, clients, body)


@router.get("/reports", response_model=ReportListOut)
def reports_api(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)) -> ReportListOut:
    return list_reports(db, page=page, page_size=page_size)
