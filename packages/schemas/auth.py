from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, examples=["demo"])
    password: str = Field(min_length=1, examples=["demo123"])


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
