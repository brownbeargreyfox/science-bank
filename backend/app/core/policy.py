"""Who may change what. Decisions over the loaded User; routes call these after loading a target."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User

MODERATOR_ROLES = ("admin", "power")


def is_moderator(user: User) -> bool:
    return user.role in MODERATOR_ROLES


def can_modify(user: User, owner_id: int) -> bool:
    return is_moderator(user) or user.id == owner_id


def require_modify(user: User, owner_id: int, what: str) -> None:
    if not can_modify(user, owner_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You can only change a {what} you own.")


def would_remove_last_admin(db: Session, user: User, *, new_role: str, new_active: bool) -> bool:
    """True when changing `user` to (new_role, new_active) would leave no active admin."""
    if user.role != "admin" or not user.is_active or (new_role == "admin" and new_active):
        return False
    others = db.scalar(
        select(func.count()).select_from(User).where(User.role == "admin", User.is_active, User.id != user.id)
    )
    return not others
