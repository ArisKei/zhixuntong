from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth import login
from schemas.auth import LoginIn, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login_api(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    return login(db, body)
