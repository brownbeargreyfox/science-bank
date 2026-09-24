"""Who may change what. Pure functions over the loaded User; routes call these after loading a target."""

from fastapi import HTTPException, status

from app.models import User

MODERATOR_ROLES = ("admin", "power")


def is_moderator(user: User) -> bool:
    return user.role in MODERATOR_ROLES


def can_modify(user: User, owner_id: int) -> bool:
    return is_moderator(user) or user.id == owner_id


def require_modify(user: User, owner_id: int, what: str) -> None:
    if not can_modify(user, owner_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You can only change a {what} you own.")
