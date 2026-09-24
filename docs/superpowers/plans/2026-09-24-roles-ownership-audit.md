# Roles, Ownership, Audit Log, Account Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Science Bank three roles (admin / power / regular), per-item ownership enforced by one policy on every mutating route, an append-only audit log, and admin account management (API, CLI, minimal Users page).

**Architecture:** A new Alembic migration adds role/active columns, owner/actor columns, `audit_events`, and `site_settings`. Auth switches from "username string from JWT" to "load the `User` row every request" (`get_current_user` / `Actor`). A pure `app/core/policy.py` decides modify rights; routes call it after loading their target and write an audit row in the same transaction. A new `/api/admin` router serves account/settings management; the frontend gains an Admin → Users page and hides edit controls when the API says `can_modify: false`.

**Tech Stack:** FastAPI, SQLAlchemy 2 (typed `Mapped`), Alembic, PostgreSQL 16, PyJWT, bcrypt, pytest + TestClient; React 19, TanStack Query, react-router 7, openapi-fetch/openapi-typescript, Tailwind 4, oxlint.

**Spec:** `docs/superpowers/specs/2026-09-24-roles-ownership-audit-design.md`

## Global Constraints

- Roles are exactly `admin`, `power`, `regular`; new accounts default to `regular`.
- Role and active state are **never** read from the JWT; every request loads the `User` row.
- Username uniqueness and lookup are case-insensitive (`lower(username)`); display keeps original case.
- Passwords: minimum 12 characters everywhere (API and CLI).
- Admins and power users may modify any content; regular users only content they own. Adding someone else's question to your own assessment is allowed.
- Questions are never hard-deleted ("delete" = `archived` status). Assessments are soft-deleted via `deleted_at`.
- No change may leave zero active admins (409).
- Audit rows are written in the same transaction as the change; failed logins commit on their own; audit `detail` never contains passwords or hashes.
- User FKs use `ON DELETE RESTRICT`; users are disabled, never deleted.
- Deterministic generation rules are untouched: no family output changes, no family version bumps.
- Acceptance bar: backend suite runs against a throwaway Postgres with **zero skipped DB tests**; `ruff check`, `npm run lint`, `npm run build` clean.

### Test database (used by every backend task)

```sh
docker run -d --rm --name sb-testdb -p 127.0.0.1:54330:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
export TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54330/sb_test
cd backend && .venv/bin/python -m pytest -q
```

The fixtures drop/recreate `sb_test` per session. Stop it afterwards with `docker stop sb-testdb`. Never point `TEST_DATABASE_URL` at the production database.

## Review Focus

- **Pre-existing sessions at deploy time:** cookies issued before this change carry `sub=<username>` (e.g. `Nina`). They must keep working (case-insensitive lookup) — pinned in Task 3 (`test_legacy_username_token_still_works`).
- **Username case collisions:** registering `nina` when `Nina` exists, and logging in as `NINA`, must resolve to the one account — pinned in Task 3 (`test_usernames_are_case_insensitive`).
- **Mixed-ownership bulk status change by a regular user:** must change nothing and name the forbidden ids, not partially apply — pinned in Task 4 (`test_bulk_status_is_all_or_nothing_on_ownership`).
- **Soft-deleted assessment still referenced by an open browser tab / print URL:** detail and print must 404, and it must not appear in the "Add to assessment" picker — pinned in Task 5 (`test_soft_deleted_assessment_is_hidden_and_restorable`).
- **Admin locks themselves out** via the UI (demote/disable self as the only admin): must 409 and leave state unchanged; CLI `set-role` remains the break-glass path — pinned in Task 7 (`test_last_admin_guard`) and Task 8 (`test_cli_set_role_and_list_users`).

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/alembic/versions/0003_roles_ownership_audit.py` (new) | Schema + backfill migration |
| `backend/app/models/bank.py` (modify) | `User` role/active/last_login, owner/actor columns, `AuditEvent`, `SiteSettings` |
| `backend/app/models/__init__.py` (modify) | Export new models |
| `backend/app/core/policy.py` (new) | Pure role/ownership decisions |
| `backend/app/services/audit.py` (new) | `record_audit()` |
| `backend/app/services/site_settings.py` (new) | Read/update the single settings row |
| `backend/app/core/security.py` (modify) | `get_current_user`, `Actor`, `get_actor`, `require_role`, token by id |
| `backend/app/api/auth.py` (modify) | Case-insensitive login/register, `/me` role, audit, last_login |
| `backend/app/api/questions.py`, `generate.py`, `assessments.py` (modify) | Ownership checks, actor columns, audit, `owner`/`can_modify` fields |
| `backend/app/services/bank.py` (modify) | Accept actor ids when creating versions/events/runs |
| `backend/app/schemas/__init__.py` (modify) | `OwnerOut`, `can_modify`, admin schemas |
| `backend/app/api/admin.py` (new) | `/api/admin/users`, `/api/admin/settings` |
| `backend/app/main.py` (modify) | Wire `get_current_user`, admin router |
| `backend/app/cli.py` (modify) | `set-role`, `set-active`, `list-users`, safer `set-password` |
| `backend/tests/conftest.py` (modify) | Seed users per role; `login_as` helper |
| `backend/tests/test_migration_0003.py` (new) | Backfill/role/index migration test |
| `backend/tests/test_policy.py` (new) | Pure policy unit tests |
| `backend/tests/test_permissions.py` (new) | Role × route matrix + route inventory |
| `backend/tests/test_admin.py` (new) | Admin API, guards, CLI |
| `frontend/src/api/schema.d.ts` (regenerate) | OpenAPI types |
| `frontend/src/api/queries.ts` (modify) | Admin queries |
| `frontend/src/pages/AdminUsers.tsx` (new) | Users + registration admin page |
| `frontend/src/components/Layout.tsx`, `main.tsx` (modify) | Admin nav + route guard |
| `frontend/src/pages/QuestionDetail.tsx`, `Questions.tsx`, `AssessmentBuilder.tsx`, `Assessments.tsx`, `components/AddToAssessment.tsx` (modify) | Respect `can_modify` |
| `README.md`, `HANDOFF.md` (modify) | Roles, CLI, ops docs |

---

### Task 1: Migration 0003 and models

**Files:**
- Create: `backend/alembic/versions/0003_roles_ownership_audit.py`
- Modify: `backend/app/models/bank.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/test_migration_0003.py`

**Interfaces:**
- Produces: `User.role: str`, `User.is_active: bool`, `User.last_login_at: datetime | None`; `ROLES = ("admin", "power", "regular")` in `app.models.bank`; `Question.owner_id/owner`, `Assessment.owner_id/owner/deleted_at`, `QuestionVersion.created_by`, `QuestionStatusEvent.actor_id`, `GenerationRun.created_by`; `AuditEvent`, `SiteSettings` models.

- [ ] **Step 1: Write the failing migration test**

`backend/tests/test_migration_0003.py`:

```python
"""Upgrades a pre-0003 database and checks roles, backfill, and case-insensitive usernames."""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from tests.conftest import BACKEND, TEST_DB_URL


def _alembic(url: str, target: str, monkeypatch) -> None:
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        command.upgrade(cfg, target)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


@pytest.fixture
def scratch_url(database):
    url = make_url(TEST_DB_URL).set(database=make_url(TEST_DB_URL).database + "_mig")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    yield url.render_as_string(hide_password=False)
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    admin.dispose()


def test_upgrade_backfills_roles_and_owners(scratch_url, monkeypatch):
    _alembic(scratch_url, "0002_eocep_constraints", monkeypatch)
    eng = create_engine(scratch_url)
    with eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('brandon','x'), ('Nina','y')"))
        c.execute(text("insert into assessments (title, instructions) values ('Old quiz', '')"))
    _alembic(scratch_url, "head", monkeypatch)
    with eng.begin() as c:
        roles = dict(c.execute(text("select username, role from users")).all())
        assert roles == {"brandon": "admin", "Nina": "power"}
        brandon_id = c.scalar(text("select id from users where username='brandon'"))
        assert c.scalar(text("select owner_id from assessments")) == brandon_id
        assert c.scalar(text("select registration_open from site_settings where id=1")) is True
    with pytest.raises(IntegrityError), eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('NINA','z')"))
    eng.dispose()


def test_upgrade_promotes_first_user_when_no_brandon(scratch_url, monkeypatch):
    _alembic(scratch_url, "0002_eocep_constraints", monkeypatch)
    eng = create_engine(scratch_url)
    with eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('solo','x')"))
    _alembic(scratch_url, "head", monkeypatch)
    with eng.begin() as c:
        assert c.scalar(text("select role from users where username='solo'")) == "admin"
    eng.dispose()


def test_upgrade_refuses_case_duplicate_usernames(scratch_url, monkeypatch):
    _alembic(scratch_url, "0002_eocep_constraints", monkeypatch)
    eng = create_engine(scratch_url)
    with eng.begin() as c:
        c.execute(text("insert into users (username, password_hash) values ('nina','x'), ('Nina','y')"))
    with pytest.raises(Exception, match="duplicate usernames"):
        _alembic(scratch_url, "head", monkeypatch)
    eng.dispose()
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_migration_0003.py -v`
Expected: FAIL — alembic cannot find target `head` beyond 0002 behaviour (roles column missing / `KeyError: 'role'`-style assertion failure).

Note: `app.core.db.engine` is created at import time from settings; the migration test only uses Alembic (which reads `get_settings()` in `env.py`), so clearing the settings cache is sufficient.

- [ ] **Step 3: Write the migration**

`backend/alembic/versions/0003_roles_ownership_audit.py`:

```python
"""Roles, content ownership, actor columns, audit log, and DB-backed site settings."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0003_roles_ownership_audit"
down_revision = "0002_eocep_constraints"
branch_labels = None
depends_on = None


def _user_fk(table: str, column: str, nullable: bool = True) -> None:
    op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
    op.create_foreign_key(f"fk_{table}_{column}", table, "users", [column], ["id"], ondelete="RESTRICT")
    if not nullable:
        op.alter_column(table, column, nullable=False)


def upgrade() -> None:
    from app.core.config import get_settings

    conn = op.get_bind()
    dupes = conn.execute(
        sa.text("select lower(username) from users group by 1 having count(*) > 1")
    ).scalars().all()
    if dupes:
        raise RuntimeError(f"Resolve case-insensitive duplicate usernames before upgrading: {dupes}")

    op.add_column("users", sa.Column("role", sa.String(16), nullable=False, server_default="regular"))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_users_role", "users", "role in ('admin', 'power', 'regular')")
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)

    conn.execute(sa.text("update users set role = 'admin' where lower(username) = 'brandon'"))
    conn.execute(sa.text("update users set role = 'power' where lower(username) = 'nina' and role <> 'admin'"))
    conn.execute(
        sa.text(
            "update users set role = 'admin' where id = (select min(id) from users) "
            "and not exists (select 1 from users where role = 'admin')"
        )
    )

    admin_id = conn.scalar(sa.text("select min(id) from users where role = 'admin'"))
    for table in ("questions", "assessments"):
        _user_fk(table, "owner_id")
        has_rows = conn.scalar(sa.text(f"select exists (select 1 from {table})"))
        if has_rows and admin_id is None:
            raise RuntimeError(f"{table} has rows but no user exists to own them")
        if has_rows:
            conn.execute(sa.text(f"update {table} set owner_id = :uid"), {"uid": admin_id})
        op.alter_column(table, "owner_id", nullable=False)
        op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])
    op.add_column("assessments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    _user_fk("question_versions", "created_by")
    _user_fk("question_status_events", "actor_id")
    _user_fk("question_family_runs", "created_by")

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("actor_username", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("detail", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_audit_events_at", "audit_events", ["at"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])

    op.create_table(
        "site_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_open", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_site_settings_singleton"),
    )
    conn.execute(
        sa.text("insert into site_settings (id, registration_open) values (1, :open)"),
        {"open": get_settings().registration_open},
    )


def downgrade() -> None:
    op.drop_table("site_settings")
    op.drop_index("ix_audit_events_actor_id", "audit_events")
    op.drop_index("ix_audit_events_at", "audit_events")
    op.drop_table("audit_events")
    for table, column in (
        ("question_family_runs", "created_by"),
        ("question_status_events", "actor_id"),
        ("question_versions", "created_by"),
    ):
        op.drop_constraint(f"fk_{table}_{column}", table, type_="foreignkey")
        op.drop_column(table, column)
    op.drop_column("assessments", "deleted_at")
    for table in ("assessments", "questions"):
        op.drop_index(f"ix_{table}_owner_id", table)
        op.drop_constraint(f"fk_{table}_owner_id", table, type_="foreignkey")
        op.drop_column(table, "owner_id")
    op.drop_index("uq_users_username_lower", "users")
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
```

- [ ] **Step 4: Update the models**

In `backend/app/models/bank.py` — add imports `Boolean, CheckConstraint, Index, BigInteger, text` from `sqlalchemy` alongside the existing ones, then replace `User` and add the new columns/models:

```python
ROLES = ("admin", "power", "regular")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('admin', 'power', 'regular')", name="ck_users_role"),
        Index("uq_users_username_lower", text("lower(username)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="regular", server_default="regular")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Add to `GenerationRun`:
```python
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
```
Add to `Question` (after `current_version_no`) and a relationship:
```python
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    ...
    owner: Mapped[User] = relationship()
```
Add to `QuestionVersion`:
```python
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
```
Add to `QuestionStatusEvent`:
```python
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
```
Add to `Assessment`:
```python
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ...
    owner: Mapped[User] = relationship()
```
New models at the end of the file:
```python
class AuditEvent(Base):
    """Append-only record of security-relevant and content-changing actions."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    actor_username: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class SiteSettings(Base):
    """Single row (id=1) of runtime-editable settings; seeded from env by migration 0003."""

    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    registration_open: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```
Export `AuditEvent`, `SiteSettings`, `ROLES` from `backend/app/models/__init__.py` (add to the import and `__all__`).

- [ ] **Step 5: Keep existing tests compiling — owner the seeded fixtures**

`questions.owner_id` and `assessments.owner_id` are now NOT NULL, but the routes don't set them until Tasks 4–5. Do not add temporary defaults. Update `backend/tests/conftest.py` so the seeded teacher is an **admin** (existing tests assume full access):

```python
        s.add(User(username=TEACHER["username"], password_hash=hash_password(TEACHER["password"]), role="admin"))
```

Existing API tests that save questions or create assessments will fail with NOT NULL `owner_id` until Tasks 4–5; that is expected and is the only allowed red. Tasks 1–3 run their targeted tests; Task 5 Step 4 restores a fully green suite.

- [ ] **Step 6: Run the migration tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_migration_0003.py tests/test_engine.py -v`
Expected: PASS (3 migration tests + engine tests), 0 skipped.

- [ ] **Step 7: Lint and commit**

```bash
cd backend && .venv/bin/ruff check app tests alembic
git add backend/alembic/versions/0003_roles_ownership_audit.py backend/app/models backend/tests/test_migration_0003.py backend/tests/conftest.py
git commit -m "feat: add roles, ownership, audit and site-settings schema (migration 0003)"
```

---

### Task 2: Policy and audit services

**Files:**
- Create: `backend/app/core/policy.py`, `backend/app/services/audit.py`, `backend/app/services/site_settings.py`
- Test: `backend/tests/test_policy.py`

**Interfaces:**
- Consumes: `User`, `AuditEvent`, `SiteSettings` from Task 1.
- Produces:
  - `policy.can_modify(user: User, owner_id: int) -> bool`
  - `policy.require_modify(user: User, owner_id: int, what: str) -> None` (raises `HTTPException(403)`)
  - `policy.is_moderator(user: User) -> bool` (admin or power)
  - `audit.record_audit(db: Session, actor: Actor | None, action: str, *, target_type: str | None = None, target_id: int | str | None = None, detail: dict | None = None, username: str | None = None, ip: str | None = None) -> AuditEvent` — adds to the session, does not commit.
  - `site_settings.get_site_settings(db) -> SiteSettings`

`Actor` is defined in Task 3; to avoid a circular import, `audit.py` types it as a `Protocol`-free duck type: it reads `actor.user` and `actor.ip`.

- [ ] **Step 1: Write failing policy tests**

`backend/tests/test_policy.py`:

```python
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
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.policy'`.

- [ ] **Step 3: Implement**

`backend/app/core/policy.py`:

```python
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
```

`backend/app/services/audit.py`:

```python
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
    """`actor` is an `app.core.security.Actor` or None (anonymous / failed login / CLI)."""
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
```

`backend/app/services/site_settings.py`:

```python
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SiteSettings


def get_site_settings(db: Session) -> SiteSettings:
    """The migration seeds row 1; recreate it from env defaults if someone removed it."""
    row = db.get(SiteSettings, 1)
    if row is None:
        row = SiteSettings(id=1, registration_open=get_settings().registration_open)
        db.add(row)
        db.flush()
    return row
```

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_policy.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/policy.py backend/app/services/audit.py backend/app/services/site_settings.py backend/tests/test_policy.py
git commit -m "feat: add ownership policy, audit recorder, and site settings service"
```

---

### Task 3: Per-request user loading, case-insensitive auth, auth auditing

**Files:**
- Modify: `backend/app/core/security.py`, `backend/app/api/auth.py`, `backend/app/main.py`, `backend/app/schemas/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `record_audit`, `get_site_settings` (Task 2).
- Produces:
  - `security.get_current_user(session_token=Cookie, db=Depends(get_db)) -> User` (401 if missing/disabled)
  - `@dataclass(frozen=True) class Actor: user: User; ip: str | None`
  - `security.get_actor(request: Request, user: User = Depends(get_current_user)) -> Actor`
  - `security.require_role(*roles: str)` → FastAPI dependency returning `User`, 403 otherwise
  - `security.create_access_token(user_id: int) -> str` (sub = `str(user_id)`)
  - `security.find_user(db, username: str) -> User | None` (case-insensitive)
  - `security.client_ip(request) -> str | None`
  - Schema `SessionUser { id: int, username: str, role: Literal["admin","power","regular"] }`
  - conftest fixtures: `login_as(anon, role) -> dict` returning `{"id", "username"}` of a per-role seeded user; seeded users `nina` (admin, existing TEACHER), `pat` (power), `reg` / `reg2` (regular). Password for all: `TEACHER["password"]`.

- [ ] **Step 1: Seed per-role users in conftest and add `login_as`**

In `backend/tests/conftest.py`, replace the single-user seed with:

```python
USERS = {"admin": "nina", "power": "pat", "regular": "reg", "regular2": "reg2"}
```

and in `database()`:

```python
        pw = hash_password(TEACHER["password"])
        for key, name in USERS.items():
            s.add(User(username=name, password_hash=pw, role=key.rstrip("2")))
        s.commit()
```

Add after the `client` fixture:

```python
def login_as(anon, who: str) -> dict:
    """Log the TestClient in as one of USERS' keys ('admin', 'power', 'regular', 'regular2')."""
    anon.post("/api/auth/logout")
    r = anon.post("/api/auth/login", json={"username": USERS[who], "password": TEACHER["password"]})
    assert r.status_code == 200, r.text
    return r.json()
```

- [ ] **Step 2: Write failing auth tests**

Append to `backend/tests/test_api.py` (auth section), and update the existing assertion in `test_login_logout_and_throttle` from `== {"username": "nina"}` to check `username == "nina"` and `role == "admin"`; in `test_registration_allows_multiple_teacher_accounts` change `created.json() == {"username": "alex"}` to check `username == "alex"` and `role == "regular"`:

```python
def test_usernames_are_case_insensitive(anon):
    assert anon.post("/api/auth/login", json={"username": "NINA", "password": TEACHER["password"]}).status_code == 200
    assert anon.get("/api/auth/me").json()["username"] == "nina"
    anon.post("/api/auth/logout")
    r = anon.post("/api/auth/register", json={"username": "Nina", "password": "long enough password"})
    assert r.status_code == 409


def test_disabled_user_session_stops_working_immediately(anon, db):
    from app.core.security import hash_password
    from app.models import User

    db.add(User(username="temp-disable", password_hash=hash_password("temporary password"), role="regular"))
    db.commit()
    assert anon.post("/api/auth/login", json={"username": "temp-disable", "password": "temporary password"}).status_code == 200
    assert anon.get("/api/auth/me").status_code == 200
    user = db.scalar(select(User).where(User.username == "temp-disable"))
    user.is_active = False
    db.commit()
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.post("/api/auth/login", json={"username": "temp-disable", "password": "temporary password"}).status_code == 401


def test_legacy_username_token_still_works(anon):
    import jwt as pyjwt
    from datetime import UTC, datetime, timedelta

    from app.core.config import get_settings
    from app.core.security import COOKIE_NAME

    s = get_settings()
    legacy = pyjwt.encode({"sub": "Pat", "exp": datetime.now(UTC) + timedelta(hours=1)}, s.jwt_secret, algorithm=s.jwt_algorithm)
    anon.cookies.set(COOKIE_NAME, legacy)
    me = anon.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "pat" and me.json()["role"] == "power"
    anon.cookies.clear()


def test_auth_events_are_audited(anon, db):
    from app.models import AuditEvent

    before = db.scalar(select(func.max(AuditEvent.id))) or 0
    anon.post("/api/auth/login", json={"username": "reg", "password": "wrong password!"})
    login_as(anon, "regular")
    anon.post("/api/auth/logout")
    db.expire_all()
    rows = db.execute(
        select(AuditEvent.action, AuditEvent.actor_username, AuditEvent.actor_id).where(AuditEvent.id > before).order_by(AuditEvent.id)
    ).all()
    actions = [r.action for r in rows]
    assert actions[0] == "auth.login_failed" and rows[0].actor_id is None and rows[0].actor_username == "reg"
    assert "auth.login" in actions and "auth.logout" in actions
    assert all("password" not in str(d) for d in db.scalars(select(AuditEvent.detail).where(AuditEvent.id > before)))
```

Add `from tests.conftest import TEACHER, login_as` at the top of `test_api.py` (replacing the existing `TEACHER` import).

- [ ] **Step 3: Run and confirm failures**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api.py -k "case_insensitive or disabled or legacy or audited or login_logout or registration" -v`
Expected: FAIL — `/me` lacks `role`; `NINA` login returns 401; disabled user still 200.

- [ ] **Step 4: Implement security changes**

In `backend/app/core/security.py` replace `create_access_token` and `get_current_teacher`, keeping hashing and `LoginThrottle` unchanged:

```python
from dataclasses import dataclass

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import User


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def find_user(db: Session, username: str) -> User | None:
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
```

Keep `COOKIE_NAME`, `hash_password`, `verify_password`, `LoginThrottle`, `login_throttle` as they are. Note: `app.models` must not import `app.core.security` (it doesn't today) to avoid a cycle.

- [ ] **Step 5: Implement auth route changes**

In `backend/app/schemas/__init__.py` add:

```python
Role = Literal["admin", "power", "regular"]
```

In `backend/app/api/auth.py`:

```python
class SessionUser(BaseModel):
    id: int
    username: str
    role: Role


def _session(user: User) -> SessionUser:
    return SessionUser(id=user.id, username=user.username, role=user.role)


def _set_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(user.id),
        httponly=True,
        samesite="strict",
        secure=settings.is_production,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=SessionUser)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionUser:
    ip = client_ip(request) or "unknown"
    login_throttle.check(ip)
    user = find_user(db, payload.username)
    ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok or not user.is_active:
        login_throttle.record_failure(ip)
        reason = "unknown_user" if user is None else ("disabled" if not user.is_active and ok else "bad_password")
        record_audit(db, None, "auth.login_failed", username=payload.username[:64], ip=ip, detail={"reason": reason})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    login_throttle.reset(ip)
    user.last_login_at = func.now()
    record_audit(db, Actor(user, ip), "auth.login", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    _set_cookie(response, user)
    return _session(user)


@router.get("/registration-status", response_model=RegistrationStatus)
def registration_status(db: Session = Depends(get_db)) -> RegistrationStatus:
    return RegistrationStatus(registration_open=get_site_settings(db).registration_open)


@router.post("/register", response_model=SessionUser, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionUser:
    if not get_site_settings(db).registration_open:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is currently closed.")
    ip = client_ip(request) or "unknown"
    login_throttle.check(ip)
    if find_user(db, payload.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable")
    user = User(username=payload.username, password_hash=hash_password(payload.password), role="regular")
    db.add(user)
    try:
        db.flush()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable") from err
    user.last_login_at = func.now()
    record_audit(db, Actor(user, ip), "auth.register", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    login_throttle.reset(ip)
    _set_cookie(response, user)
    return _session(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            user = get_current_user(token, db)
            record_audit(db, Actor(user, client_ip(request)), "auth.logout", target_type="user", target_id=user.id)
            db.commit()
        except HTTPException:
            pass
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=SessionUser)
def me(user: User = Depends(get_current_user)) -> SessionUser:
    return _session(user)
```

Imports for `auth.py`: `from sqlalchemy import func`, `from sqlalchemy.exc import IntegrityError`, `from app.core.security import COOKIE_NAME, Actor, client_ip, create_access_token, find_user, get_current_user, hash_password, login_throttle, verify_password`, `from app.schemas import Role`, `from app.services.audit import record_audit`, `from app.services.site_settings import get_site_settings`. Remove the unused `select` import.

In `backend/app/main.py`: replace `get_current_teacher` with `get_current_user` in the import and in `protected = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])`.

- [ ] **Step 6: Run the auth tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_api.py -k "auth or login or registration or case_insensitive or disabled or legacy or audited or every_non_public" -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/security.py backend/app/api/auth.py backend/app/main.py backend/app/schemas/__init__.py backend/tests/conftest.py backend/tests/test_api.py
git commit -m "feat: load user per request, case-insensitive usernames, audit auth events"
```

---

### Task 4: Question ownership, actor tracking, and auditing

**Files:**
- Modify: `backend/app/services/bank.py`, `backend/app/api/generate.py`, `backend/app/api/questions.py`, `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_permissions.py` (new)

**Interfaces:**
- Consumes: `Actor`, `get_actor` (Task 3); `require_modify`, `can_modify`, `record_audit` (Task 2).
- Produces:
  - `save_generated(db, std, family, generated, *, owner_id: int) -> tuple[GenerationRun, list[int]]`
  - `add_version(question, edit, *, actor_id: int) -> QuestionVersion`
  - `change_status(question, to_status, note, *, actor_id: int) -> None`
  - Schema `OwnerOut { id: int, username: str }`; `QuestionSummary` and `QuestionDetail` gain `owner: OwnerOut` and `can_modify: bool`.
  - Test helper in `test_permissions.py`: `make_question(anon, who) -> int` (logs in as `who`, generates+saves one population question, returns its id).

- [ ] **Step 1: Write failing permission tests**

`backend/tests/test_permissions.py`:

```python
"""Role × ownership matrix for every mutating route, plus a guard that new routes are covered."""

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from tests.conftest import login_as

from tests.test_api import _generate  # existing helper: resolves the standard id, builds a GenerateRequest body


def make_question(anon, who: str) -> int:
    """Log in as `who`, save one generated set, return the first question id (owned by `who`)."""
    login_as(anon, who)
    _, body = _generate(anon, "biology-1", "B-LS2-1", "population-carrying-capacity", seed="edit")
    r = anon.post("/api/generate/save", json=body)
    assert r.status_code == 201, r.text
    return r.json()["question_ids"][0]


def _edit_body(anon, qid: int) -> dict:
    """A valid QuestionEdit that differs from the current version (ChoiceIn has only text/correct/rationale)."""
    cur = anon.get(f"/api/questions/{qid}").json()["current"]
    body = {"stem": cur["stem"] + " (edited)", "dok": cur["dok"], "explanation": cur["explanation"]}
    if cur["question_type"] == "multiple_choice":
        body["choices"] = [{"text": c["text"], "correct": c["correct"], "rationale": c["rationale"]} for c in cur["choices"]]
    else:
        body["answer"] = cur["answer"]
    return body


def test_question_owner_and_can_modify_fields(anon):
    qid = make_question(anon, "regular")
    mine = anon.get(f"/api/questions/{qid}").json()
    assert mine["owner"]["username"] == "reg" and mine["can_modify"] is True
    login_as(anon, "regular2")
    theirs = anon.get(f"/api/questions/{qid}").json()
    assert theirs["can_modify"] is False
    listed = anon.get("/api/questions", params={"page_size": 200}).json()["items"]
    assert next(i for i in listed if i["id"] == qid)["can_modify"] is False


@pytest.mark.parametrize(("who", "expected"), [("regular", 201), ("regular2", 403), ("power", 201), ("admin", 201)])
def test_edit_question_matrix(anon, who, expected):
    qid = make_question(anon, "regular")
    login_as(anon, who)
    r = anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid))
    assert r.status_code == expected, r.text


@pytest.mark.parametrize(("who", "expected"), [("regular", 200), ("regular2", 403), ("power", 200), ("admin", 200)])
def test_status_matrix(anon, who, expected):
    qid = make_question(anon, "regular")
    login_as(anon, who)
    r = anon.post(f"/api/questions/{qid}/status", json={"to_status": "archived"})
    assert r.status_code == expected, r.text


@pytest.mark.parametrize(("who", "expected"), [("regular", 201), ("regular2", 403), ("power", 201)])
def test_restore_matrix(anon, who, expected):
    qid = make_question(anon, "regular")
    anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid))
    login_as(anon, who)
    r = anon.post(f"/api/questions/{qid}/restore/1")
    assert r.status_code == expected, r.text


def test_bulk_status_is_all_or_nothing_on_ownership(anon, db):
    from app.models import Question

    mine = make_question(anon, "regular")
    theirs = make_question(anon, "power")
    login_as(anon, "regular")
    r = anon.post("/api/questions/bulk-status", json={"question_ids": [mine, theirs], "to_status": "archived"})
    assert r.status_code == 403 and str(theirs) in r.json()["detail"]
    db.expire_all()
    assert db.get(Question, mine).status == "generated"


def test_question_actions_record_actor_and_audit(anon, db):
    from app.models import AuditEvent, Question, QuestionStatusEvent, QuestionVersion

    qid = make_question(anon, "regular")
    me = login_as(anon, "power")
    anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid))
    anon.post(f"/api/questions/{qid}/status", json={"to_status": "reviewed"})
    db.expire_all()
    q = db.get(Question, qid)
    assert db.scalar(select(QuestionVersion.created_by).where(QuestionVersion.question_id == qid, QuestionVersion.version_no == 2)) == me["id"]
    assert db.scalar(select(QuestionStatusEvent.actor_id).where(QuestionStatusEvent.question_id == qid).order_by(QuestionStatusEvent.id.desc()).limit(1)) == me["id"]
    actions = db.scalars(select(AuditEvent.action).where(AuditEvent.target_type == "question", AuditEvent.target_id == str(qid))).all()
    assert {"question.version", "question.status"} <= set(actions)
    assert q.owner_id != me["id"]


def test_failed_change_writes_no_audit_row(anon, db):
    from app.models import AuditEvent

    qid = make_question(anon, "regular")
    before = db.scalar(select(func.max(AuditEvent.id))) or 0
    r = anon.post(f"/api/questions/{qid}/status", json={"to_status": "generated"})  # not an allowed transition
    assert r.status_code == 409
    login_as(anon, "regular2")
    assert anon.post(f"/api/questions/{qid}/status", json={"to_status": "archived"}).status_code == 403
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.id > before, AuditEvent.target_type == "question")) == 0
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_permissions.py -v`
Expected: FAIL — `save` 500s on NOT NULL `owner_id`, `owner` key missing.

- [ ] **Step 3: Thread actors through `bank.py`**

- `save_generated(db, std, family, generated, *, owner_id: int)`: set `GenerationRun(created_by=owner_id, ...)`, `Question(owner_id=owner_id, ...)`, the v1 `QuestionVersion(created_by=owner_id, ...)`, and the initial `QuestionStatusEvent(actor_id=owner_id, ...)`.
- `add_version(question, edit, *, actor_id: int)`: pass `created_by=actor_id` to the new `QuestionVersion`.
- `change_status(question, to_status, note, *, actor_id: int)`: pass `actor_id=actor_id` to the `QuestionStatusEvent`.

- [ ] **Step 4: Schemas**

In `backend/app/schemas/__init__.py`:

```python
class OwnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
```

Add `owner: OwnerOut` and `can_modify: bool` to `QuestionSummary` and `QuestionDetail`. (Import `ConfigDict` from pydantic if not already imported.)

- [ ] **Step 5: Routes**

`backend/app/api/generate.py` `save`:

```python
@router.post("/save", response_model=GenerateSaveOut, status_code=status.HTTP_201_CREATED)
def save(req: GenerateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> GenerateSaveOut:
    """Regenerate server-side from the seed (never trusting client-edited content) and store in the bank."""
    if not req.seed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A seed is required to save; preview first")
    std, family, out = _generate(db, req, req.seed)
    run, ids = save_generated(db, std, family, out, owner_id=actor.user.id)
    record_audit(db, actor, "question.generate", target_type="generation_run", target_id=run.id,
                 detail={"question_ids": ids, "family": family.key, "seed": req.seed})
    db.commit()
    return GenerateSaveOut(run_id=run.id, seed=req.seed, question_ids=ids)
```

`backend/app/api/questions.py`:
- `_load` adds `selectinload(Question.owner)`.
- `_detail(db, q, user)` adds `owner=OwnerOut.model_validate(q.owner)` and `can_modify=can_modify(user, q.owner_id)`.
- `list_questions` gains `user: User = Depends(get_current_user)`; add `User` to the select (`.join(User, User.id == Question.owner_id)`), unpack `for question, version, std, course, stim, owner in rows`, and set `owner=OwnerOut.model_validate(owner)`, `can_modify=can_modify(user, question.owner_id)`. Update `_status_counts` untouched (it re-selects only `Question.status`).
- `get_question(..., user: User = Depends(get_current_user))` → `_detail(db, _load(...), user)`.
- Mutations take `actor: Actor = Depends(get_actor)` and follow this pattern (shown for `edit_question`):

```python
@router.post("/{question_id}/versions", response_model=QuestionDetail, status_code=status.HTTP_201_CREATED)
def edit_question(
    question_id: int, edit: QuestionEdit, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> QuestionDetail:
    q = _load(db, question_id)
    require_modify(actor.user, q.owner_id, "question")
    version = add_version(q, edit, actor_id=actor.user.id)
    record_audit(db, actor, "question.version", target_type="question", target_id=q.id,
                 detail={"version_no": version.version_no})
    db.commit()
    return _detail(db, _load(db, question_id), actor.user)
```

  - `restore_version`: `require_modify` after `_load`; new version gets `created_by=actor.user.id`; audit `question.restore` with `{"restored": version_no, "version_no": new.version_no}`.
  - `set_status`: `require_modify`; `change_status(q, change.to_status, change.note, actor_id=actor.user.id)`; audit `question.status` with `{"from": old_status, "to": change.to_status}` (capture `old_status = q.status` before changing).
  - `bulk_status`: after loading `found`, compute
    ```python
    forbidden = sorted(qid for qid, q in found.items() if not can_modify(actor.user, q.owner_id))
    if forbidden:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"You can only change questions you own; not yours: {', '.join(map(str, forbidden))}")
    ```
    before any `change_status`; pass `actor_id=actor.user.id`; after the loop, if `updated`, one audit row `question.bulk_status` with `target_type="question"`, `target_id=None`, `detail={"to": change.to_status, "updated": updated, "skipped": skipped}`.

Imports: `from app.core.policy import can_modify, require_modify`, `from app.core.security import Actor, get_actor, get_current_user`, `from app.models import User`, `from app.schemas import OwnerOut`, `from app.services.audit import record_audit`.

- [ ] **Step 6: Run question + existing API tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_permissions.py tests/test_api.py -k "not assessment" -v`
Expected: PASS for question tests; `test_assessment_builder_and_print` still fails on assessments `owner_id` (fixed in Task 5).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/bank.py backend/app/api/generate.py backend/app/api/questions.py backend/app/schemas/__init__.py backend/tests/test_permissions.py
git commit -m "feat: enforce question ownership, record actors, audit question changes"
```

---

### Task 5: Assessment ownership, soft delete/restore, auditing

**Files:**
- Modify: `backend/app/api/assessments.py`, `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_permissions.py`

**Interfaces:**
- Consumes: Task 2–4 helpers; `make_question` from `test_permissions.py`.
- Produces: `AssessmentSummary` gains `owner: OwnerOut`, `can_modify: bool`, `deleted_at: datetime | None`; `GET /assessments?include_deleted=true`; `POST /assessments/{id}/restore` → `AssessmentDetail`.

- [ ] **Step 1: Write failing tests** (append to `test_permissions.py`)

```python
def make_assessment(anon, who: str, title: str = "Perm quiz") -> int:
    login_as(anon, who)
    r = anon.post("/api/assessments", json={"title": title, "instructions": ""})
    assert r.status_code == 201, r.text
    return r.json()["id"]


ASSESSMENT_MUTATIONS = [
    ("patch", lambda a, aid, qid: a.patch(f"/api/assessments/{aid}", json={"title": "Renamed"})),
    ("add", lambda a, aid, qid: a.post(f"/api/assessments/{aid}/items", json={"question_ids": [qid]})),
    ("delete", lambda a, aid, qid: a.delete(f"/api/assessments/{aid}")),
]


@pytest.mark.parametrize("who,allowed", [("regular", True), ("regular2", False), ("power", True), ("admin", True)])
@pytest.mark.parametrize("name,call", ASSESSMENT_MUTATIONS)
def test_assessment_mutation_matrix(anon, who, allowed, name, call):
    qid = make_question(anon, "power")  # someone else's question: adding it is allowed
    aid = make_assessment(anon, "regular")
    login_as(anon, who)
    r = call(anon, aid, qid)
    assert (r.status_code < 400) is allowed, f"{name} as {who}: {r.status_code} {r.text}"


@pytest.mark.parametrize("who,allowed", [("regular", True), ("regular2", False), ("power", True)])
def test_item_mutation_matrix(anon, who, allowed):
    q1, q2 = make_question(anon, "regular"), make_question(anon, "admin")
    aid = make_assessment(anon, "regular")
    anon.post(f"/api/assessments/{aid}/items", json={"question_ids": [q1, q2]})
    items = anon.get(f"/api/assessments/{aid}").json()["items"]
    login_as(anon, who)
    calls = [
        anon.put(f"/api/assessments/{aid}/items/order", json={"item_ids": [items[1]["id"], items[0]["id"]]}),
        anon.post(f"/api/assessments/{aid}/items/{items[0]['id']}/refresh"),
        anon.delete(f"/api/assessments/{aid}/items/{items[1]['id']}"),
    ]
    assert all((r.status_code < 400) is allowed for r in calls), [r.status_code for r in calls]


def test_soft_deleted_assessment_is_hidden_and_restorable(anon, db):
    from app.models import Assessment, AuditEvent

    aid = make_assessment(anon, "regular", "Soft delete me")
    assert anon.delete(f"/api/assessments/{aid}").status_code == 204
    assert all(a["id"] != aid for a in anon.get("/api/assessments").json())
    assert anon.get(f"/api/assessments/{aid}").status_code == 404
    assert anon.get(f"/api/assessments/{aid}/print").status_code == 404
    login_as(anon, "regular2")
    assert all(a["id"] != aid for a in anon.get("/api/assessments", params={"include_deleted": True}).json())
    assert anon.post(f"/api/assessments/{aid}/restore").status_code == 403
    login_as(anon, "regular")
    deleted = anon.get("/api/assessments", params={"include_deleted": True}).json()
    assert any(a["id"] == aid and a["deleted_at"] for a in deleted)
    assert anon.post(f"/api/assessments/{aid}/restore").status_code == 200
    assert anon.get(f"/api/assessments/{aid}").status_code == 200
    db.expire_all()
    assert db.get(Assessment, aid).deleted_at is None
    actions = db.scalars(select(AuditEvent.action).where(AuditEvent.target_type == "assessment", AuditEvent.target_id == str(aid))).all()
    assert {"assessment.create", "assessment.delete", "assessment.restore"} <= set(actions)
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_permissions.py -k "assessment or item" -v`
Expected: FAIL — create 500 (NOT NULL owner_id).

- [ ] **Step 3: Implement**

In `backend/app/schemas/__init__.py`, add to `AssessmentSummary`: `owner: OwnerOut`, `can_modify: bool`, `deleted_at: datetime | None = None`.

In `backend/app/api/assessments.py`:

```python
def _load(db: Session, assessment_id: int, *, include_deleted: bool = False) -> Assessment:
    stmt = (
        select(Assessment)
        .options(
            selectinload(Assessment.owner),
            selectinload(Assessment.course),
            # ...existing item/question selectinloads unchanged...
        )
        .where(Assessment.id == assessment_id)
    )
    if not include_deleted:
        stmt = stmt.where(Assessment.deleted_at.is_(None))
    a = db.scalar(stmt)
    if a is None:
        raise not_found("Assessment")
    return a


def _load_for_change(db: Session, assessment_id: int, actor: Actor) -> Assessment:
    a = _load(db, assessment_id)
    require_modify(actor.user, a.owner_id, "assessment")
    return a
```

- `_summary(a, user)` and `_detail(a, user)` add `owner=OwnerOut.model_validate(a.owner)`, `can_modify=can_modify(user, a.owner_id)`, `deleted_at=a.deleted_at`. `_detail` builds from `_summary(a, user)`.
- `list_assessments(include_deleted: bool = False, db, user=Depends(get_current_user))`: select `Assessment, count` with `.options(selectinload(Assessment.course), selectinload(Assessment.owner))`; when `include_deleted` is false add `.where(Assessment.deleted_at.is_(None))`; when true, keep non-deleted rows plus deleted rows the user may modify: `.where(or_(Assessment.deleted_at.is_(None), true() if is_moderator(user) else Assessment.owner_id == user.id))`. Build summaries with the owner and `can_modify`.
- `create_assessment(..., actor=Depends(get_actor))`: `Assessment(owner_id=actor.user.id, ...)`, `db.flush()`, `record_audit(db, actor, "assessment.create", target_type="assessment", target_id=a.id, detail={"title": a.title})`, commit.
- `get_assessment` / `print_view`: add `user: User = Depends(get_current_user)`; pass `user` to `_detail`. (`_load` already 404s deleted.)
- `update_assessment`, `add_items`, `remove_item`, `reorder_items`, `refresh_item`: take `actor: Actor = Depends(get_actor)`, replace `_load(db, id)` with `_load_for_change(db, id, actor)`, and before `db.commit()` record: `assessment.update` (`detail={"fields": sorted(fields)}`), `assessment.items` (`detail={"op": "add", "added": added, "skipped": skipped}` / `{"op": "remove", "item_id": item_id}` / `{"op": "reorder"}` / `{"op": "refresh", "item_id": item_id}`). Return `_detail(_load(db, assessment_id), actor.user)`.
- `delete_assessment`:
  ```python
  a = _load_for_change(db, assessment_id, actor)
  a.deleted_at = func.now()
  record_audit(db, actor, "assessment.delete", target_type="assessment", target_id=a.id, detail={"title": a.title})
  db.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)
  ```
- New route:
  ```python
  @router.post("/{assessment_id}/restore", response_model=AssessmentDetail)
  def restore_assessment(assessment_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> AssessmentDetail:
      a = _load(db, assessment_id, include_deleted=True)
      require_modify(actor.user, a.owner_id, "assessment")
      if a.deleted_at is None:
          raise HTTPException(status.HTTP_409_CONFLICT, "That assessment is not deleted")
      a.deleted_at = None
      record_audit(db, actor, "assessment.restore", target_type="assessment", target_id=a.id)
      db.commit()
      return _detail(_load(db, assessment_id), actor.user)
  ```

Imports: `or_, true` from sqlalchemy; `can_modify, is_moderator, require_modify`; `Actor, get_actor, get_current_user`; `User`; `OwnerOut`; `record_audit`.

In `test_api.py::test_assessment_builder_and_print`, if it asserts the hard-delete (e.g. a 404 after delete), it still holds. If it asserts summary dict equality, add the new keys.

- [ ] **Step 4: Run full backend suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: all pass, 0 skipped.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/assessments.py backend/app/schemas/__init__.py backend/tests/test_permissions.py backend/tests/test_api.py
git commit -m "feat: assessment ownership, soft delete and restore, audit assessment changes"
```

---

### Task 6: Route-inventory guard

**Files:**
- Test: `backend/tests/test_permissions.py`

**Interfaces:**
- Consumes: the matrix tests from Tasks 4–5.

- [ ] **Step 1: Write the guard test** (append)

```python
# Every non-GET /api route must be listed here with how the policy covers it.
POLICY_COVERED = {
    ("POST", "/api/generate/preview"): "read-only preview",
    ("POST", "/api/generate/save"): "creates; owner = caller",
    ("POST", "/api/questions/{question_id}/versions"): "test_edit_question_matrix",
    ("POST", "/api/questions/{question_id}/restore/{version_no}"): "test_restore_matrix",
    ("POST", "/api/questions/{question_id}/status"): "test_status_matrix",
    ("POST", "/api/questions/bulk-status"): "test_bulk_status_is_all_or_nothing_on_ownership",
    ("POST", "/api/assessments"): "creates; owner = caller",
    ("PATCH", "/api/assessments/{assessment_id}"): "test_assessment_mutation_matrix",
    ("DELETE", "/api/assessments/{assessment_id}"): "test_assessment_mutation_matrix",
    ("POST", "/api/assessments/{assessment_id}/restore"): "test_soft_deleted_assessment_is_hidden_and_restorable",
    ("POST", "/api/assessments/{assessment_id}/items"): "test_assessment_mutation_matrix",
    ("DELETE", "/api/assessments/{assessment_id}/items/{item_id}"): "test_item_mutation_matrix",
    ("PUT", "/api/assessments/{assessment_id}/items/order"): "test_item_mutation_matrix",
    ("POST", "/api/assessments/{assessment_id}/items/{item_id}/refresh"): "test_item_mutation_matrix",
}


def test_every_mutating_route_is_policy_covered():
    from app.main import app

    found = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        if route.path.startswith(("/api/auth/", "/api/admin/")) or route.path == "/api/{path:path}":
            continue
        for method in route.methods - {"GET", "HEAD", "OPTIONS"}:
            found.add((method, route.path))
    assert found == set(POLICY_COVERED), f"uncovered: {found - set(POLICY_COVERED)}; stale: {set(POLICY_COVERED) - found}"
```

(`/api/admin/*` is excluded because the whole router requires `admin`, tested in Task 7.)

- [ ] **Step 2: Run it**

Run: `cd backend && .venv/bin/python -m pytest tests/test_permissions.py::test_every_mutating_route_is_policy_covered -v`
Expected: PASS. If it fails listing an uncovered route, add a matrix test for that route and list it — do not just add the key.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_permissions.py
git commit -m "test: fail when a mutating route is not covered by the ownership policy"
```

---

### Task 7: Admin API — users and settings

**Files:**
- Create: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`, `backend/app/schemas/__init__.py`, `backend/app/api/auth.py` (password min length constant)
- Test: `backend/tests/test_admin.py`

**Interfaces:**
- Consumes: `require_role`, `Actor`, `client_ip`, `find_user`, `record_audit`, `get_site_settings`.
- Produces:
  - `PASSWORD_MIN = 12` in `app.core.security` (used by auth `RegisterRequest`, admin, CLI).
  - `ensure_admin_remains(db, user: User, *, new_role: str, new_active: bool) -> None` in `app.api.admin` (409 if the change leaves zero active admins).
  - Schemas: `AdminUserOut {id, username, role, is_active, created_at, last_login_at}`, `AdminUserCreate {username, password, role}`, `AdminUserUpdate {role: Role | None, is_active: bool | None}`, `PasswordSet {password}`, `SiteSettingsOut/SiteSettingsUpdate {registration_open}`.

- [ ] **Step 1: Write failing tests**

`backend/tests/test_admin.py`:

```python
from sqlalchemy import select

from tests.conftest import TEACHER, login_as


def test_admin_routes_require_admin(anon):
    for who in ("regular", "power"):
        login_as(anon, who)
        assert anon.get("/api/admin/users").status_code == 403
        assert anon.patch("/api/admin/settings", json={"registration_open": False}).status_code == 403
    login_as(anon, "admin")
    users = anon.get("/api/admin/users").json()
    assert {"nina", "pat", "reg"} <= {u["username"] for u in users}
    assert "password_hash" not in users[0]


def test_create_update_and_reset_password(anon, db):
    from app.models import AuditEvent

    login_as(anon, "admin")
    r = anon.post("/api/admin/users", json={"username": "newteach", "password": "short", "role": "regular"})
    assert r.status_code == 422
    r = anon.post("/api/admin/users", json={"username": "newteach", "password": "a fine long password", "role": "regular"})
    assert r.status_code == 201
    uid = r.json()["id"]
    assert anon.post("/api/admin/users", json={"username": "NEWTEACH", "password": "a fine long password", "role": "regular"}).status_code == 409
    assert anon.patch(f"/api/admin/users/{uid}", json={"role": "power"}).json()["role"] == "power"
    assert anon.post(f"/api/admin/users/{uid}/password", json={"password": "another long password"}).status_code == 204
    anon.post("/api/auth/logout")
    assert anon.post("/api/auth/login", json={"username": "newteach", "password": "another long password"}).status_code == 200
    actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.target_id == str(uid))).all())
    assert {"admin.user_create", "admin.user_update", "admin.password_reset"} <= actions
    details = db.scalars(select(AuditEvent.detail).where(AuditEvent.target_id == str(uid))).all()
    assert all("password" not in str(d).lower() or "reset" in str(d).lower() for d in details)


def test_demotion_applies_to_existing_session(anon, db):
    from app.core.security import hash_password
    from app.models import User

    db.add(User(username="temp-admin", password_hash=hash_password("temporary password"), role="admin"))
    db.commit()
    anon.post("/api/auth/logout")
    anon.post("/api/auth/login", json={"username": "temp-admin", "password": "temporary password"})
    assert anon.get("/api/admin/users").status_code == 200
    u = db.scalar(select(User).where(User.username == "temp-admin"))
    u.role = "regular"
    db.commit()
    assert anon.get("/api/admin/users").status_code == 403


def test_last_admin_guard(anon, db):
    from app.models import User

    me = login_as(anon, "admin")
    others = db.scalars(select(User).where(User.role == "admin", User.id != me["id"], User.is_active)).all()
    for o in others:  # make nina the only active admin for this test
        o.is_active = False
    db.commit()
    assert anon.patch(f"/api/admin/users/{me['id']}", json={"role": "power"}).status_code == 409
    assert anon.patch(f"/api/admin/users/{me['id']}", json={"is_active": False}).status_code == 409
    assert anon.get("/api/auth/me").json()["role"] == "admin"
    for o in others:
        o.is_active = True
    db.commit()


def test_registration_toggle(anon):
    login_as(anon, "admin")
    assert anon.patch("/api/admin/settings", json={"registration_open": False}).json() == {"registration_open": False}
    anon.post("/api/auth/logout")
    assert anon.get("/api/auth/registration-status").json() == {"registration_open": False}
    assert anon.post("/api/auth/register", json={"username": "blocked", "password": "long enough password"}).status_code == 403
    login_as(anon, "admin")
    anon.patch("/api/admin/settings", json={"registration_open": True})
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin.py -v`
Expected: FAIL — 404 on `/api/admin/users`.

- [ ] **Step 3: Implement**

In `backend/app/core/security.py` add `PASSWORD_MIN = 12`; in `auth.py` use `Field(min_length=PASSWORD_MIN, max_length=128)`.

Schemas (`backend/app/schemas/__init__.py`):

```python
class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)
    role: Role = "regular"


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class SiteSettingsOut(BaseModel):
    registration_open: bool


class SiteSettingsUpdate(BaseModel):
    registration_open: bool
```

`backend/app/api/admin.py`:

```python
"""Admin-only account and site-settings management."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
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
AdminUser = Depends(require_role("admin"))


def _actor(request: Request, user: User) -> Actor:
    return Actor(user=user, ip=client_ip(request))


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


def ensure_admin_remains(db: Session, user: User, *, new_role: str, new_active: bool) -> None:
    if user.role != "admin" or not user.is_active or (new_role == "admin" and new_active):
        return
    others = db.scalar(
        select(func.count()).select_from(User).where(User.role == "admin", User.is_active, User.id != user.id)
    )
    if not others:
        raise HTTPException(status.HTTP_409_CONFLICT, "At least one active admin must remain.")


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _: User = AdminUser) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: AdminUserCreate, request: Request, db: Session = Depends(get_db), admin: User = AdminUser) -> User:
    if find_user(db, body.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is unavailable")
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    record_audit(db, _actor(request, admin), "admin.user_create", target_type="user", target_id=user.id,
                 detail={"username": user.username, "role": user.role})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, body: AdminUserUpdate, request: Request, db: Session = Depends(get_db), admin: User = AdminUser) -> User:
    user = _get_user(db, user_id)
    new_role = body.role if body.role is not None else user.role
    new_active = body.is_active if body.is_active is not None else user.is_active
    ensure_admin_remains(db, user, new_role=new_role, new_active=new_active)
    changes = {}
    if new_role != user.role:
        changes["role"] = [user.role, new_role]
    if new_active != user.is_active:
        changes["is_active"] = [user.is_active, new_active]
    user.role, user.is_active = new_role, new_active
    if changes:
        record_audit(db, _actor(request, admin), "admin.user_update", target_type="user", target_id=user.id, detail=changes)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(user_id: int, body: PasswordSet, request: Request, db: Session = Depends(get_db), admin: User = AdminUser) -> Response:
    user = _get_user(db, user_id)
    user.password_hash = hash_password(body.password)
    record_audit(db, _actor(request, admin), "admin.password_reset", target_type="user", target_id=user.id,
                 detail={"username": user.username})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings", response_model=SiteSettingsOut)
def get_settings_(db: Session = Depends(get_db), _: User = AdminUser) -> SiteSettingsOut:
    return SiteSettingsOut(registration_open=get_site_settings(db).registration_open)


@router.patch("/settings", response_model=SiteSettingsOut)
def update_settings(body: SiteSettingsUpdate, request: Request, db: Session = Depends(get_db), admin: User = AdminUser) -> SiteSettingsOut:
    row = get_site_settings(db)
    if row.registration_open != body.registration_open:
        record_audit(db, _actor(request, admin), "admin.settings_update", target_type="site_settings", target_id=1,
                     detail={"registration_open": [row.registration_open, body.registration_open]})
        row.registration_open = body.registration_open
    db.commit()
    return SiteSettingsOut(registration_open=row.registration_open)
```

`backend/app/main.py`: `from app.api import admin, ...` and add `admin` to the `protected.include_router` loop tuple.

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin.py tests/test_api.py::test_every_non_public_route_requires_auth -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/admin.py backend/app/main.py backend/app/schemas/__init__.py backend/app/core/security.py backend/app/api/auth.py backend/tests/test_admin.py
git commit -m "feat: admin API for accounts, roles, passwords and registration toggle"
```

---

### Task 8: CLI break-glass commands

**Files:**
- Modify: `backend/app/cli.py`
- Test: `backend/tests/test_admin.py`

**Interfaces:**
- Consumes: `find_user`, `PASSWORD_MIN`, `hash_password`, `record_audit`, `ROLES`.
- Produces: CLI commands `list-users`, `set-role --username U --role R`, `set-active --username U --active true|false`; `set-password` requires `--username` once any user exists.

- [ ] **Step 1: Write failing tests** (append to `test_admin.py`)

```python
def test_cli_set_role_and_list_users(database, capsys, db):
    from app import cli
    from app.models import AuditEvent, User

    assert cli.main(["set-role", "--username", "REG2", "--role", "power"]) == 0
    db.expire_all()
    assert db.scalar(select(User.role).where(User.username == "reg2")) == "power"
    assert cli.main(["set-role", "--username", "reg2", "--role", "regular"]) == 0
    assert cli.main(["set-role", "--username", "nobody", "--role", "admin"]) == 1
    assert cli.main(["list-users"]) == 0
    out = capsys.readouterr().out
    assert "nina" in out and "admin" in out
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "cli.set_role")) is not None


def test_cli_set_password_requires_username_once_users_exist(database, monkeypatch):
    import io

    from app import cli

    monkeypatch.setattr("sys.stdin", io.StringIO("long enough password\n"))
    assert cli.main(["set-password", "--password-stdin"]) == 1
    monkeypatch.setattr("sys.stdin", io.StringIO("tooshort\n"))
    assert cli.main(["set-password", "--username", "reg", "--password-stdin"]) == 1


def test_cli_set_active_respects_last_admin(database, db):
    from app import cli
    from app.models import User

    admins = db.scalars(select(User).where(User.role == "admin", User.is_active)).all()
    for a in admins[1:]:
        a.is_active = False
    db.commit()
    assert cli.main(["set-active", "--username", admins[0].username, "--active", "false"]) == 1
    for a in admins[1:]:
        a.is_active = True
    db.commit()
```

- [ ] **Step 2: Run and confirm failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin.py -k cli -v`
Expected: FAIL — `argparse` error `invalid choice: 'set-role'` (SystemExit 2).

- [ ] **Step 3: Implement**

Rewrite the user parts of `backend/app/cli.py`:

```python
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
        if _would_remove_last_admin(db, user, args.role, user.is_active):
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
        if _would_remove_last_admin(db, user, user.role, active):
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
            print(f"{u.id:>4}  {u.username:<24} {u.role:<8} {'active' if u.is_active else 'DISABLED':<8} last login {last}")
    return 0


def _would_remove_last_admin(db, user: User, new_role: str, new_active: bool) -> bool:
    from sqlalchemy import func

    if user.role != "admin" or not user.is_active or (new_role == "admin" and new_active):
        return False
    others = db.scalar(
        select(func.count()).select_from(User).where(User.role == "admin", User.is_active, User.id != user.id)
    )
    return not others
```

Remove `_upsert_user`. In `cmd_bootstrap`, replace the `_upsert_user(...)` call with creating `User(username=settings.teacher_username, password_hash=settings.teacher_password_hash, role="admin")` in a session and committing.

In `main()` register the parsers:

```python
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
```

and add them to `handlers`. Imports: `from app.core.security import PASSWORD_MIN, find_user, hash_password`, `from app.models import ROLES, User`, `from app.services.audit import record_audit`.

Note: `admin.ensure_admin_remains` and `cli._would_remove_last_admin` share the same rule. To keep it DRY, move the count query into `app/core/policy.py` as `def would_remove_last_admin(db, user, new_role, new_active) -> bool` and have both call it (admin raises 409 when true). Update Task 7's `ensure_admin_remains` accordingly in this step.

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli.py backend/app/core/policy.py backend/app/api/admin.py backend/tests/test_admin.py
git commit -m "feat: CLI list-users/set-role/set-active; set-password requires --username"
```

---

### Task 9: Frontend — role-aware session and Admin → Users page

**Files:**
- Regenerate: `frontend/openapi.json`, `frontend/src/api/schema.d.ts`
- Modify: `frontend/src/api/queries.ts`, `frontend/src/components/Layout.tsx`, `frontend/src/main.tsx`
- Create: `frontend/src/pages/AdminUsers.tsx`

**Interfaces:**
- Consumes: `/api/auth/me` `{id, username, role}`; `/api/admin/users`, `/api/admin/users/{user_id}`, `/api/admin/users/{user_id}/password`, `/api/admin/settings`.
- Produces: `useAdminUsers()`, `useSiteSettings()` hooks; `<RequireAdmin />` route guard exported from `Layout.tsx`.

- [ ] **Step 1: Regenerate API types**

```bash
cd backend && .venv/bin/python scripts/dump_openapi.py
cd ../frontend && npm run gen:api
```

Expected: `schema.d.ts` now contains `/api/admin/users` and `SessionUser.role`.

- [ ] **Step 2: Queries**

Append to `frontend/src/api/queries.ts`:

```ts
export function useAdminUsers() {
  return useQuery({ queryKey: ["admin", "users"], queryFn: () => unwrap(api.GET("/api/admin/users")) });
}

export function useSiteSettings() {
  return useQuery({ queryKey: ["admin", "settings"], queryFn: () => unwrap(api.GET("/api/admin/settings")) });
}
```

- [ ] **Step 3: Nav and guard**

In `Layout.tsx`, render an extra nav entry `{ to: "/admin/users", label: "Admin" }` only when `me.data?.role === "admin"` (build the list as `const items = me.data?.role === "admin" ? [...NAV, ADMIN_NAV] : NAV;` and map `items`). Show the role next to the username in the header, e.g. `nina · Admin` / `Nina · Power user` (labels: `admin → "Admin"`, `power → "Power user"`, `regular → "Teacher"`).

Add:

```tsx
/** Hides admin pages from non-admins; the API enforces the same rule. */
export function RequireAdmin() {
  const me = useMe();
  if (me.data?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}
```

In `main.tsx`, inside the `AppLayout` children: `{ element: <RequireAdmin />, children: [{ path: "/admin/users", element: <AdminUsersPage /> }] }`.

- [ ] **Step 4: Users page**

`frontend/src/pages/AdminUsers.tsx` — follow the existing page conventions (`PageHeader`, `ErrorNotice`, `Loading` from `components/ui.tsx`; `useMutation` + `unwrap(api.X(...))`; invalidate `["admin", ...]` on success). Contents:

1. **Registration** card: checkbox "Allow new teachers to create their own accounts", bound to `useSiteSettings()`, `PATCH /api/admin/settings` on change.
2. **Users** table: username, role `<select>` (Admin / Power user / Teacher), Active checkbox, Last login (formatted with the existing `lib/format.ts` date helper, "never" if null), and a "Reset password" button. Role/active changes call `PATCH /api/admin/users/{user_id}`; a 409 shows the server message via `ErrorNotice` and the query is refetched so the control snaps back. Disable the role select and Active checkbox for the row matching `me.data.id` with title "Use another admin account or the CLI to change your own access".
3. **Reset password** inline form under the row: two password inputs (min 12, must match; show the mismatch/length error client-side), submit → `POST /api/admin/users/{user_id}/password`, then "Password updated" confirmation.
4. **Create user** form: username, role select (default Teacher), password + confirm (min 12) → `POST /api/admin/users`; clear form on success.

- [ ] **Step 5: Lint, build, browser check**

```bash
cd frontend && npm run lint && npm run build
```

Expected: both clean. Then run the dev stack against the test DB or dev compose and verify in a browser: as `nina` (admin) the Admin link appears and the Users page lists users; as `pat` (power) there is no Admin link and `/admin/users` redirects home.

- [ ] **Step 6: Commit**

```bash
git add frontend/openapi.json frontend/src
git commit -m "feat: admin Users page with roles, activation, password reset and registration toggle"
```

---

### Task 10: Frontend — respect `can_modify` on content

**Files:**
- Modify: `frontend/src/pages/QuestionDetail.tsx`, `frontend/src/pages/Questions.tsx`, `frontend/src/pages/AssessmentBuilder.tsx`, `frontend/src/pages/Assessments.tsx`, `frontend/src/components/AddToAssessment.tsx`

**Interfaces:**
- Consumes: `owner`, `can_modify`, `deleted_at` on question/assessment responses; `POST /api/assessments/{assessment_id}/restore`; `GET /api/assessments?include_deleted=true`.

- [ ] **Step 1: QuestionDetail**

When `q.can_modify` is false: hide the status-transition buttons (`change` mutation), the Edit button / `EditQuestionForm`, and the per-version Restore buttons (`restore` mutation). Show under the header: `<p className="text-muted">Owned by {q.owner.username}. Only the owner or a power user can change this question.</p>`. When true, show `Owned by {q.owner.username}` as plain metadata.

- [ ] **Step 2: Questions (bank list)**

Bulk-status actions: only allow selecting rows where `item.can_modify` is true (disable the checkbox with `title="Owned by {owner}"` otherwise). Add an "Owner" column showing `item.owner.username`.

- [ ] **Step 3: AssessmentBuilder**

When `a.can_modify` is false: hide save/rename, add-items panel, reorder, remove, refresh, and delete controls; keep print links. Show `Owned by {a.owner.username}` in the header lead.

- [ ] **Step 4: Assessments list + trash**

Show owner on each row. Add a "Show deleted" toggle that refetches with `include_deleted: true`; deleted rows render muted with a "Restore" button (`POST /api/assessments/{assessment_id}/restore`, then invalidate the assessments queries). Update the AssessmentBuilder delete confirmation copy from permanent wording to "You can restore it from Assessments → Show deleted."

- [ ] **Step 5: AddToAssessment**

Filter the target-assessment picker to `can_modify === true` (deleted ones are already excluded by the API default).

- [ ] **Step 6: Lint, build, browser check**

```bash
cd frontend && npm run lint && npm run build
```

Browser check as `reg`: open a question owned by `pat` → no edit/status/restore controls and the "Owned by pat" note; open own question → controls present; assessment owned by someone else → print only; delete own assessment → appears under "Show deleted" and restores.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat: hide edit controls on content the user cannot modify; assessment trash and restore"
```

---

### Task 11: Docs and full verification

**Files:**
- Modify: `README.md`, `HANDOFF.md`, `.env.example`, `docker-compose.yml`

- [ ] **Step 1: Wire `REGISTRATION_OPEN` into compose**

It is currently not passed to the container, so `.env` has no effect. Add under `app.environment` in `docker-compose.yml`:

```yaml
      REGISTRATION_OPEN: ${REGISTRATION_OPEN:-true}
```

and in `.env.example` change the comment to: "Initial default only: migration 0003 copies this into the database; afterwards use Admin → Users → Registration."

- [ ] **Step 2: Docs**

- `README.md`: add a "Roles and administration" section with the capability table from the spec §1, the CLI commands (`list-users`, `set-role`, `set-active`, `set-password --username`), and the note that the first account created on an empty install is an admin.
- `HANDOFF.md`: replace the "Accounts and authentication" section to describe roles, ownership, audit log (`audit_events`, how to query it with `psql`), soft-deleted assessments, and the break-glass CLI; update "Immediate recommended work" to list Phase 2 (admin console) and Phase 3 (change requests) with the spec path. Commit `HANDOFF.md` (currently untracked).

- [ ] **Step 3: Full verification**

```bash
cd backend && .venv/bin/ruff check app tests alembic && .venv/bin/python -m pytest -q
cd ../frontend && npm run lint && npm run build
```

Expected: ruff clean; pytest all passed, **0 skipped**; lint/build clean. Paste the pytest summary line into the commit message body.

- [ ] **Step 4: Commit**

```bash
git add README.md HANDOFF.md .env.example docker-compose.yml
git commit -m "docs: roles, ownership, audit and admin operations"
```

---

### Task 12: Deploy to production (requires owner go-ahead)

This mutates the live database. **Stop and get explicit approval from Brandon before Step 2.**

- [ ] **Step 1: Pre-flight** — confirm branch is clean and pushed; `docker compose ps` healthy.

- [ ] **Step 2: Backup**

```bash
cd /home/brandon/apps/science-bank
mkdir -p backups && docker compose exec -T postgres pg_dump -U science_bank science_bank > backups/pre-0003-$(date +%F-%H%M).sql
ls -l backups/
```

Expected: non-empty dump. (`backups/` must be in `.gitignore`; add it if missing.)

- [ ] **Step 3: Deploy**

```bash
docker compose up -d --build
docker compose logs app --since 5m | grep -E "migrat|0003|ERROR|Traceback" || true
docker compose ps
```

Expected: migration `0003_roles_ownership_audit` applied, both services healthy.

- [ ] **Step 4: Live verification**

```bash
curl -fsS http://127.0.0.1:8420/readyz
docker compose exec app python -m app.cli list-users
docker compose exec -T postgres psql -U science_bank science_bank -c "select username, role, is_active from users order by id;" -c "select count(*) filter (where owner_id is null) as unowned from questions;"
```

Expected: `brandon admin`, `Nina power`; `unowned = 0`. Then in the browser at `https://science.maefranklin.com`: brandon sees Admin → Users; Nina (existing session should still work) sees no Admin link and can archive a brandon-owned question; `select action, actor_username from audit_events order by id desc limit 10;` shows the logins/actions.

- [ ] **Step 5: Rollback path (only if verification fails)**

```bash
docker compose stop app
docker compose exec -T postgres psql -U science_bank -d postgres -c "drop database science_bank with (force);" -c "create database science_bank owner science_bank;"
docker compose exec -T postgres psql -U science_bank science_bank < backups/pre-0003-<stamp>.sql
git checkout e5efd4b -- . && docker compose up -d --build   # previous app version
```
