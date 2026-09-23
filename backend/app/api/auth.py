from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
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


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)


class SessionUser(BaseModel):
    username: str


class RegistrationStatus(BaseModel):
    registration_open: bool


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


@router.get("/registration-status", response_model=RegistrationStatus)
def registration_status(db: Session = Depends(get_db)) -> RegistrationStatus:
    """Only expose registration while the single-teacher database has no account."""
    return RegistrationStatus(registration_open=(db.scalar(select(func.count(User.id))) or 0) == 0)


@router.post("/register", response_model=SessionUser, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionUser:
    """One-time bootstrap registration; permanently closes once an account exists."""
    if (db.scalar(select(func.count(User.id))) or 0) != 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed. Ask the teacher account owner to reset access.")

    client = request.client.host if request.client else "unknown"
    login_throttle.check(client)
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable")
    login_throttle.reset(client)
    settings = get_settings()
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
