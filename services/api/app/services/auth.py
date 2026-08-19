from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import User
from app.security import create_access_token, verify_password
from schemas.auth import LoginIn, TokenOut


def login(db: Session, body: LoginIn) -> TokenOut:
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError("invalid_credentials", "用户名或密码错误", 401)
    token = create_access_token(user.id, user.username)
    return TokenOut(access_token=token)
