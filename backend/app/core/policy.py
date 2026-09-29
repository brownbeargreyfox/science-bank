"""Who may change what. Decisions over the loaded User; routes call these after loading a target."""

from fastapi import HTTPException, status
from sqlalchemy import select
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
    """True when changing `user` to (new_role, new_active) would leave no active admin.

    Locks the active-admin rows (in id order) until the caller's transaction ends, so two concurrent
    demotions serialize: the second re-reads after the first commits and sees who is still an admin.
    """
    if user.role != "admin" or not user.is_active or (new_role == "admin" and new_active):
        return False
    admin_ids = db.scalars(
        select(User.id).where(User.role == "admin", User.is_active).order_by(User.id).with_for_update()
    ).all()
    return not [uid for uid in admin_ids if uid != user.id]
