import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User

COOKIE_NAME = "science_bank_session"


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def find_user(db: Session, username: str) -> User | None:
    """Usernames are unique case-insensitively; lookups ignore case and surrounding whitespace."""
    return db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME), db: Session = Depends(get_db)
) -> User:
    """Identity comes from the token; role and active state always come from the database."""
    settings = get_settings()
    if session_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(session_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from exc
    subject = str(payload.get("sub") or "")
    # Tokens issued before migration 0003 carry the username instead of the id.
    user = db.get(User, int(subject)) if subject.isdigit() else (find_user(db, subject) if subject else None)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    return user


@dataclass(frozen=True)
class Actor:
    """The signed-in user performing a request, plus where it came from (for the audit log)."""

    user: User
    ip: str | None


def get_actor(request: Request, user: User = Depends(get_current_user)) -> Actor:
    return Actor(user=user, ip=client_ip(request))


def require_role(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this area.")
        return user

    return dependency


class LoginThrottle:
    """In-process limiter for a single-teacher deployment: N failures per window per client."""

    def __init__(self, max_failures: int = 8, window_seconds: int = 300) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._failures.get(key, []) if now - t < self.window]

    def check(self, key: str) -> None:
        with self._lock:
            recent = self._recent(key, time.monotonic())
            self._failures[key] = recent
            if len(recent) >= self.max_failures:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts; try again later")

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._failures[key] = [*self._recent(key, now), now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_throttle = LoginThrottle()
