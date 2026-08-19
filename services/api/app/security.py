from datetime import datetime, timedelta, timezone
from typing import Optional
import binascii
import hashlib
import hmac
import secrets

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import AppError
from app.models import User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2${salt}${binascii.hexlify(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, hexhash = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(binascii.hexlify(digest).decode(), hexhash)


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("unauthorized", "未登录或 token 无效", 401)
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception as exc:
        raise AppError("unauthorized", "未登录或 token 无效", 401) from exc
    user = db.get(User, user_id)
    if user is None:
        raise AppError("unauthorized", "未登录或 token 无效", 401)
    return user
