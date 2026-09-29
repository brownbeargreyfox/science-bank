from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    COOKIE_NAME,
    PASSWORD_MIN,
    Actor,
    client_ip,
    create_access_token,
    find_user,
    get_current_user,
    hash_password,
    login_throttle,
    verify_password,
)
from app.models import User
from app.schemas import Role
from app.services.audit import record_audit
from app.services.site_settings import get_site_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Equalizes timing between unknown-user and wrong-password paths.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-account")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=PASSWORD_MIN, max_length=128)


class SessionUser(BaseModel):
    id: int
    username: str
    role: Role


class RegistrationStatus(BaseModel):
    registration_open: bool


def _session(user: User) -> SessionUser:
    return SessionUser(id=user.id, username=user.username, role=user.role)


def _set_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(user.id),
        httponly=True,
        samesite="strict",
        secure=settings.is_production,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=SessionUser)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionUser:
    ip = client_ip(request) or "unknown"
    login_throttle.check(ip)
    user = find_user(db, payload.username)
    ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok or not user.is_active:
        login_throttle.record_failure(ip)
        reason = "unknown_user" if user is None else ("bad_password" if not ok else "disabled")
        record_audit(db, None, "auth.login_failed", username=payload.username[:64], ip=ip, detail={"reason": reason})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    login_throttle.reset(ip)
    user.last_login_at = func.now()
    record_audit(db, Actor(user, ip), "auth.login", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    _set_cookie(response, user)
    return _session(user)


@router.get("/registration-status", response_model=RegistrationStatus)
def registration_status(db: Session = Depends(get_db)) -> RegistrationStatus:
    """Report whether this installation currently accepts new self-service accounts."""
    return RegistrationStatus(registration_open=get_site_settings(db).registration_open)


@router.post("/register", response_model=SessionUser, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessionUser:
    """Create a regular teacher account while registration is open."""
    if not get_site_settings(db).registration_open:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is currently closed.")
    ip = client_ip(request) or "unknown"
    login_throttle.check(ip)
    if find_user(db, payload.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable")
    user = User(username=payload.username, password_hash=hash_password(payload.password), role="regular")
    db.add(user)
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable") from err
    user.last_login_at = func.now()
    record_audit(db, Actor(user, ip), "auth.register", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    login_throttle.reset(ip)
    _set_cookie(response, user)
    return _session(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            user = get_current_user(token, db)
            record_audit(db, Actor(user, client_ip(request)), "auth.logout", target_type="user", target_id=user.id)
            db.commit()
        except HTTPException:
            pass
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=SessionUser)
def me(user: User = Depends(get_current_user)) -> SessionUser:
    return _session(user)
