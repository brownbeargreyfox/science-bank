"""Append-only audit trail. Callers add the row in the same transaction as the change they describe."""

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_audit(
    db: Session,
    actor,
    action: str,
    *,
    target_type: str | None = None,
    target_id: int | str | None = None,
    detail: dict | None = None,
    username: str | None = None,
    ip: str | None = None,
) -> AuditEvent:
    """`actor` is an `app.core.security.Actor` or None (anonymous, failed login, CLI)."""
    user = getattr(actor, "user", None)
    event = AuditEvent(
        actor_id=user.id if user else None,
        actor_username=user.username if user else username,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip=getattr(actor, "ip", None) or ip,
        detail=detail or {},
    )
    db.add(event)
    return event
