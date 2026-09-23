"""Operational commands: `python -m app.cli <command>`."""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User
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


def _upsert_user(username: str, password_hash: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            db.add(User(username=username, password_hash=password_hash))
        else:
            user.password_hash = password_hash
        db.commit()


def cmd_set_password(args: argparse.Namespace) -> int:
    username = args.username or get_settings().teacher_username
    password = args.password_stdin and sys.stdin.readline().rstrip("\n") or None
    if password is None:
        password = getpass.getpass(f"New password for {username}: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match", file=sys.stderr)
            return 1
    if len(password) < 10:
        print("Password must be at least 10 characters", file=sys.stderr)
        return 1
    _upsert_user(username, hash_password(password))
    print(f"Password set for {username}")
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Container start-up: import standards, sync families, create the teacher from env if absent."""
    cmd_import_standards(args)
    cmd_sync_families(args)
    settings = get_settings()
    with SessionLocal() as db:
        has_user = db.scalar(select(User.id).limit(1)) is not None
    if not has_user:
        if settings.teacher_password_hash:
            _upsert_user(settings.teacher_username, settings.teacher_password_hash)
            print(f"Created teacher account {settings.teacher_username!r} from TEACHER_PASSWORD_HASH")
        else:
            print(
                "WARNING: no teacher account exists. Run: docker compose exec app python -m app.cli set-password",
                file=sys.stderr,
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("import-standards", help="Load data/standards JSON into the database (idempotent)")
    sub.add_parser("sync-families", help="Register code-defined question families in the database")
    sub.add_parser("bootstrap", help="import-standards + sync-families + create teacher from env if missing")
    pw = sub.add_parser("set-password", help="Create the teacher account or change its password")
    pw.add_argument("--username")
    pw.add_argument("--password-stdin", action="store_true", help="Read the password from stdin (for scripts)")
    args = parser.parse_args(argv)
    handlers = {
        "import-standards": cmd_import_standards,
        "sync-families": cmd_sync_families,
        "bootstrap": cmd_bootstrap,
        "set-password": cmd_set_password,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
