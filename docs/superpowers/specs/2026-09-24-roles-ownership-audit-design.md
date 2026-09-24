# Phase 1 — Roles, Ownership, Audit Log, Account Management

Date: 2026-09-24
Status: Draft for review

## Context and intent

Science Bank has two accounts (`brandon`, `Nina`) and no notion of roles: every authenticated user is
an equal "teacher" and all content is shared and editable by anyone. The only administration is the
container CLI (`python -m app.cli set-password`). The site is expected to gain more teachers, so it
needs tiered administration before content and accounts accumulate.

This is **Phase 1 of 3**:

1. **Foundation (this spec):** roles, content ownership, a central permission policy enforced on
   every mutating route, an audit log, and account management (API + minimal admin Users page).
2. **Admin console:** diagnostics page, audit-log viewer, moderation UI. Separate spec.
3. **Change requests:** regular users propose edits/deletes to content they don't own; owners
   approve/reject. Separate spec. Depends on Phase 1 ownership + policy.

### What the owner said

- Admin (brandon): can do everything — accounts, troubleshooting, audit, content.
- Power user (Nina): can remove/clean up content herself without asking the admin.
- Regular user (future teachers): may build and print their own assessments; may not edit or delete
  anyone else's content without that person's explicit consent (consent = change requests, Phase 3).

### Confirmed assumptions

- Power users moderate **all content** but cannot manage accounts, change site settings, or see
  diagnostics/audit.
- Regular users may generate questions; they own what they generate. Adding someone else's question
  to one's own assessment is not "editing" it and is allowed.
- Existing content (5 questions, 0 assessments) is backfilled to `brandon` (id 1); it predates Nina's
  account.
- `brandon` → admin, `Nina` → power user, new registrations → regular.
- Deletion is soft: questions are archived (they may be pinned in other people's assessments);
  assessments get a restorable `deleted_at`.

## Non-goals (Phase 1)

- Change-request workflow (Phase 3). Until then, regular users simply get 403 on others' content.
- Diagnostics page, audit viewer UI, moderation UI (Phase 2). Phase 1 records audit events and exposes
  the admin API for users/settings only.
- Per-user private workspaces / data isolation. The bank stays shared-read for all authenticated
  users; ownership governs *changes*, not visibility.
- SSO / email / password-reset-by-email.

## Design

### 1. Roles

`users.role`: `admin | power | regular` (string column + CHECK constraint), default `regular`.
`users.is_active`: bool, default true. Disabled users cannot log in and existing sessions stop working
immediately.

Capability summary:

| Capability | regular | power | admin |
|---|:-:|:-:|:-:|
| Read standards, bank, all assessments; print | ✓ | ✓ | ✓ |
| Generate + save questions (becomes owner) | ✓ | ✓ | ✓ |
| Create assessments (becomes owner) | ✓ | ✓ | ✓ |
| Edit/version/restore/status-change/archive **own** questions | ✓ | ✓ | ✓ |
| Edit/delete/reorder/refresh items in **own** assessments | ✓ | ✓ | ✓ |
| Add any assessable question to own assessment | ✓ | ✓ | ✓ |
| Same actions on **others'** content | ✗ (403) | ✓ | ✓ |
| Restore soft-deleted assessments | own only | ✓ | ✓ |
| Manage accounts, roles, site settings | ✗ | ✗ | ✓ |

### 2. Authentication changes

- The JWT remains identity-only (`sub` = user id as string, plus `exp`). **Role and active state are
  never read from the token.**
- Replace `get_current_teacher` (returns a username string) with `get_current_user` that decodes the
  token, loads the `User` row, and raises 401 if missing or `is_active` is false. This makes demotion
  and disabling effective on the next request rather than at token expiry (7 days).
- Tokens issued before this change carry `sub=username`. `get_current_user` accepts a non-numeric
  `sub` by falling back to a case-insensitive username lookup, so current sessions survive the deploy;
  new tokens use the id.
- `require_role(*roles)` dependency for admin-only routers.
- `/api/auth/me` returns `{id, username, role}` so the frontend can show/hide admin navigation.
  (UI hiding is cosmetic; the server policy is authoritative.)

### 3. Case-insensitive usernames

- Migration adds a unique index on `lower(username)` (and drops the old case-sensitive unique
  constraint). Migration aborts with a clear message if existing rows collide case-insensitively
  (they do not today: `brandon`, `Nina`).
- Login, registration, and CLI lookups compare `lower(username)`. Display preserves the original case.
- Fixes the live trap where `set-password` without `--username` defaults to `nina` and would silently
  create a second account alongside `Nina`.

### 4. Ownership and actor tracking

Schema additions (migration `0003`):

| Table | Column | Notes |
|---|---|---|
| `questions` | `owner_id` FK users, NOT NULL | backfilled to 1 |
| `assessments` | `owner_id` FK users, NOT NULL | backfilled to 1 (none exist) |
| `assessments` | `deleted_at` timestamptz NULL | soft delete |
| `question_versions` | `created_by` FK users NULL | NULL for historical rows |
| `question_status_events` | `actor_id` FK users NULL | NULL for historical rows |
| `question_family_runs` | `created_by` FK users NULL | provenance of generation |

User FKs use `ON DELETE RESTRICT`; users are disabled, never deleted.

Soft-deleted assessments are hidden from everyone by default: excluded from `GET /assessments`, and
detail/print return 404. `GET /assessments?include_deleted=true` shows deleted ones the caller may
modify (own for regular; all for power/admin), and `POST /assessments/{id}/restore` clears
`deleted_at` under the same modify check.

Question "delete" is the existing `archived` status transition — no new mechanism.

### 5. Central permission policy

New module `app/core/policy.py` with pure functions, no FastAPI imports:

```python
def can_modify(user: User, owner_id: int) -> bool:
    return user.role in ("admin", "power") or user.id == owner_id

def require_modify(user: User, owner_id: int) -> None  # raises PermissionDenied -> 403
```

Every mutating route calls `require_modify` after loading its target. Route inventory (all must be
covered and each has a role-matrix test):

| Route | Check |
|---|---|
| `POST /generate/save` | none; sets `owner_id`, `created_by` = current user |
| `POST /questions/{id}/versions` | modify question |
| `POST /questions/{id}/restore/{v}` | modify question |
| `POST /questions/{id}/status` | modify question |
| `POST /questions/bulk-status` | modify **each** question; all-or-nothing — any 403 fails the whole batch and names the ids |
| `POST /assessments` | none; sets `owner_id` |
| `PATCH /assessments/{id}` | modify assessment |
| `DELETE /assessments/{id}` | modify assessment → sets `deleted_at` |
| `POST /assessments/{id}/restore` (new) | modify assessment |
| `POST /assessments/{id}/items` | modify assessment (question ownership irrelevant) |
| `DELETE /assessments/{id}/items/{item}` | modify assessment |
| `PUT /assessments/{id}/items/order` | modify assessment |
| `POST /assessments/{id}/items/{item}/refresh` | modify assessment |

A test enumerates `app.routes` and fails if any non-GET route under `/api` (excluding `/api/auth/*`)
is not listed in the policy test matrix, so new routes cannot silently skip the policy.

Question and assessment API responses gain `owner: {id, username}` and `can_modify: bool` so the UI can
disable edit controls for regular users on others' content.

### 6. Audit log

Table `audit_events`:

| Column | Type |
|---|---|
| `id` | bigserial |
| `at` | timestamptz default now() |
| `actor_id` | FK users NULL (NULL for failed/anonymous) |
| `actor_username` | text (snapshot; also records attempted username on failed login) |
| `action` | text, e.g. `auth.login`, `auth.login_failed`, `auth.logout`, `auth.register`, `question.version`, `question.status`, `question.bulk_status`, `assessment.create`, `assessment.update`, `assessment.delete`, `assessment.restore`, `assessment.items`, `admin.user_create`, `admin.user_update`, `admin.password_reset`, `admin.settings_update`, `cli.set_password`, `cli.set_role` |
| `target_type` / `target_id` | text / text NULL |
| `ip` | text NULL (`request.client.host`; uvicorn already runs with `--proxy-headers`) |
| `detail` | JSONB (small, never contains passwords or hashes) |

`record_audit(db, ...)` is written in the same transaction as the change it describes (so a rolled
back change leaves no audit row). Failed-login events commit on their own.
Append-only: no update/delete API. Retention is unbounded for now (low volume).
Reading the log (API + UI) is Phase 2; Phase 1 verifies rows via tests and `psql`.

### 7. Account management

Admin-only router `/api/admin` (`require_role("admin")`):

| Route | Purpose |
|---|---|
| `GET /admin/users` | id, username, role, is_active, created_at, last_login_at |
| `POST /admin/users` | create user with username, role, initial password |
| `PATCH /admin/users/{id}` | change role and/or is_active |
| `POST /admin/users/{id}/password` | set a new password (by **id**, never typed username) |
| `GET /admin/settings` / `PATCH /admin/settings` | `registration_open` |

Guards:
- Refuse (409) any change that would leave zero active admins (demoting or disabling the last one,
  including oneself).
- Password minimum 12 characters everywhere (CLI currently accepts 10 — align to 12).
- `users.last_login_at` column added, set on successful login.

Site settings: single-row table `site_settings` (`registration_open` bool). On first migration it is
seeded from the `REGISTRATION_OPEN` env value; thereafter the DB value is authoritative and the env
var is documented as "initial default only".

CLI additions (break-glass, always available from the container):

```sh
docker compose exec app python -m app.cli set-role --username brandon --role admin
docker compose exec app python -m app.cli set-active --username X --active true
docker compose exec app python -m app.cli list-users
```

`set-password` without `--username` now **errors** instead of defaulting to `TEACHER_USERNAME`
(when any user exists), removing the duplicate-account trap. Bootstrap's create-first-user path makes
that user an admin.

### 8. Frontend (minimal)

- `useMe` exposes `role`. Nav shows an **Admin** link only for admins.
- `/admin/users` page: table of users with role select, active toggle, reset-password action
  (dialog with password + confirm), create-user form, and a registration-open switch. Uses existing
  `ui.tsx` primitives and page conventions; no new design system.
- Question and assessment views disable/hide edit, status, delete, reorder controls when
  `can_modify` is false, with a short "Owned by X" note. (The "request a change" button arrives in
  Phase 3.)
- 403 responses show the existing `ErrorNotice` with the server message.

## Migration and rollout

1. Migration `0003_roles_ownership_audit`: add columns/tables, lower-username index, backfill
   `owner_id = 1`, set roles `brandon=admin`, `Nina=power` (matched case-insensitively; migration
   fails loudly if `brandon` is missing, since it would otherwise leave no admin), seed
   `site_settings` from env.
2. Take a `pg_dump` backup before deploying.
3. `docker compose up -d --build`; entrypoint runs migration.
4. Verify live: `/readyz`; log in as brandon → `/api/auth/me` shows `admin`; `/api/admin/users`
   lists both; as Nina, confirm `/api/admin/users` → 403 and she can archive a brandon-owned question;
   audit rows exist for these logins.

Rollback: restore the pre-deploy dump and redeploy the previous image tag. Alembic downgrade for
`0003` is implemented but the dump is the primary path.

## Testing

- Pure unit tests for `policy.py` (every role × own/other).
- Role × route matrix API tests (regular/power/admin × own/other) for every route in §5, plus the
  route-inventory completeness test.
- Auth: disabled user's existing cookie → 401 on next request; demoted admin loses `/api/admin` on next
  request; legacy username-`sub` token still works; case-insensitive login; duplicate-case
  registration → 409.
- Last-admin guard (demote self, disable self, demote other last admin).
- Audit: each action in §6 writes exactly one row with correct actor/target; rolled-back change writes
  none; failed login writes one row with NULL actor.
- Migration test: upgrade on a DB seeded with pre-0003 data (users `brandon`, `Nina`; questions without
  owners) yields correct roles and backfill.
- DB-backed tests require `TEST_DATABASE_URL`; the implementation plan must run them against a
  throwaway Postgres (they are currently skipped by default — 15 skipped). A green run with **zero
  skipped DB tests** is the acceptance bar.
- Frontend: `npm run lint`, `npm run build`, and a browser check of the Users page and a regular-user
  view with disabled controls.

## Open items deferred to later phases

- Phase 2 needs a build-arg app version/commit baked into the image and an in-app error ring
  buffer/table (the container has no `.git` and cannot read `docker logs`).
- Phase 3 change requests will reuse `policy.can_modify` and `audit_events`.
