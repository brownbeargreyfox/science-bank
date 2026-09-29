"""Database helpers shared by the administration, results, and usage routes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policy import can_modify, is_moderator
from app.models import Administration, User
from app.services.bank import not_found

MAX_SECTIONS = 12


def visible_clauses(user: User) -> list:
    """Where-clauses for the administrations a user may see: not deleted, and their own unless a moderator."""
    clauses = [Administration.deleted_at.is_(None)]
    if not is_moderator(user):
        clauses.append(Administration.owner_id == user.id)
    return clauses


def get_administration(
    db: Session, user: User, administration_id: int, *, lock: bool = False, include_deleted: bool = False
) -> Administration:
    """Load an administration the user may access, or raise 404 so colleagues' records cannot be enumerated."""
    stmt = select(Administration).where(Administration.id == administration_id)
    if not include_deleted:
        stmt = stmt.where(Administration.deleted_at.is_(None))
    if lock:
        stmt = stmt.with_for_update()
    admin = db.scalar(stmt)
    if admin is None or not can_modify(user, admin.owner_id):
        raise not_found("Administration")
    return admin
