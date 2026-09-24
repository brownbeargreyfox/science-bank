"""Admin-only account and site-settings management."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.policy import would_remove_last_admin
from app.core.security import Actor, client_ip, find_user, hash_password, require_role
from app.models import User
from app.schemas import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    PasswordSet,
    SiteSettingsOut,
    SiteSettingsUpdate,
)
from app.services.audit import record_audit
from app.services.site_settings import get_site_settings

router = APIRouter(prefix="/admin", tags=["admin"])
require_admin = require_role("admin")


def _actor(request: Request, user: User) -> Actor:
    return Actor(user=user, ip=client_ip(request))


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: AdminUserCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> User:
    if find_user(db, body.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable")
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    record_audit(
        db,
        _actor(request, admin),
        "admin.user_create",
        target_type="user",
        target_id=user.id,
        detail={"username": user.username, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    user = _get_user(db, user_id)
    new_role = body.role if body.role is not None else user.role
    new_active = body.is_active if body.is_active is not None else user.is_active
    if would_remove_last_admin(db, user, new_role=new_role, new_active=new_active):
        raise HTTPException(status.HTTP_409_CONFLICT, "At least one active admin must remain.")
    changes = {}
    if new_role != user.role:
        changes["role"] = [user.role, new_role]
    if new_active != user.is_active:
        changes["is_active"] = [user.is_active, new_active]
    user.role, user.is_active = new_role, new_active
    if changes:
        record_audit(
            db, _actor(request, admin), "admin.user_update", target_type="user", target_id=user.id, detail=changes
        )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(
    user_id: int,
    body: PasswordSet,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Response:
    user = _get_user(db, user_id)
    user.password_hash = hash_password(body.password)
    record_audit(
        db,
        _actor(request, admin),
        "admin.password_reset",
        target_type="user",
        target_id=user.id,
        detail={"username": user.username},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings", response_model=SiteSettingsOut)
def read_settings(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> SiteSettingsOut:
    return SiteSettingsOut(registration_open=get_site_settings(db).registration_open)


@router.patch("/settings", response_model=SiteSettingsOut)
def update_settings(
    body: SiteSettingsUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> SiteSettingsOut:
    row = get_site_settings(db)
    if row.registration_open != body.registration_open:
        record_audit(
            db,
            _actor(request, admin),
            "admin.settings_update",
            target_type="site_settings",
            target_id=1,
            detail={"registration_open": [row.registration_open, body.registration_open]},
        )
        row.registration_open = body.registration_open
    db.commit()
    return SiteSettingsOut(registration_open=row.registration_open)
