from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.clients.factory import Clients
from app.db import get_db
from app.deps import get_clients
from app.security import get_current_user
from app.services.alert import evaluate_alert, list_alerts
from schemas.alert import AlertEvaluateIn, AlertListOut, AlertOut

router = APIRouter(prefix="/api", tags=["alert"], dependencies=[Depends(get_current_user)])


@router.post("/alert/evaluate", response_model=AlertOut)
def evaluate_api(
    body: AlertEvaluateIn,
    db: Session = Depends(get_db),
    clients: Clients = Depends(get_clients),
) -> AlertOut:
    return evaluate_alert(db, clients, body)


@router.get("/alerts", response_model=AlertListOut)
def alerts_api(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)) -> AlertListOut:
    return list_alerts(db, page=page, page_size=page_size)
