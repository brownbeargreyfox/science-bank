"""Operational commands: `python -m app.cli <command>`."""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.policy import would_remove_last_admin
from app.core.security import PASSWORD_MIN, find_user, hash_password
from app.models import ROLES, User
from app.services.audit import record_audit
from app.standards.importer import import_standards


def cmd_import_standards(_: argparse.Namespace) -> int:
    settings = get_settings()
    with SessionLocal() as db:
        report = import_standards(db, settings.standards_dir)
        db.commit()
    print(report.summary())
    return 0


def cmd_sync_families(_: argparse.Namespace) -> int:
    from app.services.families.registry import sync_families

    with SessionLocal() as db:
        count = sync_families(db)
        db.commit()
    print(f"question families synced: {count}")
    return 0


def _audit_cli(db, action: str, user: User, detail: dict) -> None:
    record_audit(db, None, action, username="cli", target_type="user", target_id=user.id, detail=detail)


def cmd_set_password(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        any_user = db.scalar(select(User.id).limit(1)) is not None
    if args.username is None and any_user:
        print("--username is required (use list-users to see accounts)", file=sys.stderr)
        return 1
    username = args.username or get_settings().teacher_username
    password = args.password_stdin and sys.stdin.readline().rstrip("\n") or None
    if password is None:
        password = getpass.getpass(f"New password for {username}: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match", file=sys.stderr)
            return 1
    if len(password) < PASSWORD_MIN:
        print(f"Password must be at least {PASSWORD_MIN} characters", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        user = find_user(db, username)
        if user is None:
            # The first account on an empty install administers it; later ones are regular teachers.
            role = "regular" if any_user else "admin"
            user = User(username=username, password_hash=hash_password(password), role=role)
            db.add(user)
            db.flush()
        else:
            user.password_hash = hash_password(password)
        _audit_cli(db, "cli.set_password", user, {"username": user.username})
        db.commit()
        print(f"Password set for {user.username} ({user.role})")
    return 0


def cmd_set_role(args: argparse.Namespace) -> int:
    with SessionLocal() as db:
        user = find_user(db, args.username)
        if user is None:
            print(f"No such user: {args.username}", file=sys.stderr)
            return 1
        if would_remove_last_admin(db, user, new_role=args.role, new_active=user.is_active):
            print("Refusing: at least one active admin must remain", file=sys.stderr)
            return 1
        _audit_cli(db, "cli.set_role", user, {"role": [user.role, args.role]})
        user.role = args.role
        db.commit()
        print(f"{user.username} is now {user.role}")
    return 0


def cmd_set_active(args: argparse.Namespace) -> int:
    active = args.active == "true"
    with SessionLocal() as db:
        user = find_user(db, args.username)
        if user is None:
            print(f"No such user: {args.username}", file=sys.stderr)
            return 1
        if would_remove_last_admin(db, user, new_role=user.role, new_active=active):
            print("Refusing: at least one active admin must remain", file=sys.stderr)
            return 1
        _audit_cli(db, "cli.set_active", user, {"is_active": [user.is_active, active]})
        user.is_active = active
        db.commit()
        print(f"{user.username} is now {'active' if active else 'disabled'}")
    return 0


def cmd_list_users(_: argparse.Namespace) -> int:
    with SessionLocal() as db:
        for u in db.scalars(select(User).order_by(User.id)):
            last = u.last_login_at.isoformat(timespec="minutes") if u.last_login_at else "never"
            state = "active" if u.is_active else "DISABLED"
            print(f"{u.id:>4}  {u.username:<24} {u.role:<8} {state:<8} last login {last}")
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Container start-up: import standards, sync families, create the first admin from env if absent."""
    cmd_import_standards(args)
    cmd_sync_families(args)
    settings = get_settings()
    with SessionLocal() as db:
        has_user = db.scalar(select(User.id).limit(1)) is not None
        if not has_user and settings.teacher_password_hash:
            db.add(User(username=settings.teacher_username, password_hash=settings.teacher_password_hash, role="admin"))
            db.commit()
            print(f"Created admin account {settings.teacher_username!r} from TEACHER_PASSWORD_HASH")
    if not has_user and not settings.teacher_password_hash:
        print(
            "WARNING: no account exists. Run: docker compose exec app python -m app.cli set-password --username <name>",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("import-standards", help="Load data/standards JSON into the database (idempotent)")
    sub.add_parser("sync-families", help="Register code-defined question families in the database")
    sub.add_parser("bootstrap", help="import-standards + sync-families + create the first admin from env if missing")
    pw = sub.add_parser("set-password", help="Create an account or change its password")
    pw.add_argument("--username")
    pw.add_argument("--password-stdin", action="store_true", help="Read the password from stdin (for scripts)")
    role = sub.add_parser("set-role", help="Change a user's role (break-glass admin recovery)")
    role.add_argument("--username", required=True)
    role.add_argument("--role", required=True, choices=ROLES)
    act = sub.add_parser("set-active", help="Enable or disable an account")
    act.add_argument("--username", required=True)
    act.add_argument("--active", required=True, choices=("true", "false"))
    sub.add_parser("list-users", help="List accounts with role, status, and last login")
    args = parser.parse_args(argv)
    handlers = {
        "import-standards": cmd_import_standards,
        "sync-families": cmd_sync_families,
        "bootstrap": cmd_bootstrap,
        "set-password": cmd_set_password,
        "set-role": cmd_set_role,
        "set-active": cmd_set_active,
        "list-users": cmd_list_users,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
