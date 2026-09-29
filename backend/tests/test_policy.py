import pytest
from fastapi import HTTPException

from app.core.policy import can_modify, is_moderator, require_modify
from app.models import User


def _u(role: str, uid: int = 7) -> User:
    return User(id=uid, username=f"{role}{uid}", password_hash="x", role=role, is_active=True)


@pytest.mark.parametrize(
    ("role", "owner_id", "expected"),
    [
        ("regular", 7, True),
        ("regular", 8, False),
        ("power", 7, True),
        ("power", 8, True),
        ("admin", 8, True),
    ],
)
def test_can_modify(role, owner_id, expected):
    assert can_modify(_u(role), owner_id) is expected


def test_require_modify_raises_403_with_owner_message():
    with pytest.raises(HTTPException) as exc:
        require_modify(_u("regular"), 8, "question")
    assert exc.value.status_code == 403
    assert "question" in exc.value.detail


def test_is_moderator():
    assert is_moderator(_u("admin")) and is_moderator(_u("power")) and not is_moderator(_u("regular"))
