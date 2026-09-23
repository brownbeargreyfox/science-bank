from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    COOKIE_NAME,
    create_access_token,
    get_current_teacher,
    hash_password,
    login_throttle,
    verify_password,
)
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Equalizes timing between unknown-user and wrong-password paths.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-account")


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionUser(BaseModel):
    username: str


@router.post("/login", response_model=SessionUser)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionUser:
    settings = get_settings()
    client = request.client.host if request.client else "unknown"
    login_throttle.check(client)

    user = db.scalar(select(User).where(User.username == payload.username))
    ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        login_throttle.record_failure(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    login_throttle.reset(client)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(subject=user.username),
        httponly=True,
        samesite="strict",
        secure=settings.is_production,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return SessionUser(username=user.username)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=SessionUser)
def me(username: str = Depends(get_current_teacher)) -> SessionUser:
    return SessionUser(username=username)
