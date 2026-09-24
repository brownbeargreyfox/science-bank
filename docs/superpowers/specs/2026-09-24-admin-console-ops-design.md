# Phase 2a — Admin Console: Operational Visibility

Date: 2026-09-24
Status: Draft for review
Builds on: `2026-09-24-roles-ownership-audit-design.md` (Phase 1, deployed 2026-09-24)

## Context and intent

Phase 1 gave Science Bank roles, ownership, an audit trail, and a Users page. The admin (Brandon) still
cannot answer "what broke when Nina clicked X?" without `docker compose logs`. There is no error capture
(an unhandled exception is a bare 500 plus a container log line), no record of which build is running, and
no history of migrations, standards imports, or question-family syncs.

Phase 2 is split:

- **2a (this spec): operational visibility.** Request context, error capture, job history, retention, and
  four read-mostly admin pages: **Overview · Errors · Jobs · Audit** (next to the existing **Users**).
- **2b (separate spec): Content management.** Cross-teacher trash/restore, bulk archive, ownership
  reassignment with preview. Power users and admins; reassignment admin-only.
- **Phase 3:** change requests.

### Principles (owner's requirements)

1. **Read-mostly.** The console is for looking. The only mutation in 2a is changing an error group's
   status/note, which is explicit and audited. The console is never a database editor.
2. **Disciplined scope.** No browser/JS telemetry, SQL console, live log streaming, container controls,
   alerting, Prometheus/Grafana, or backup implementation. Backups get a placeholder on Overview.
3. **Best-effort recording.** Capturing an error or a job run must never hide, replace, or worsen the
   original failure. If Postgres is down or the tables do not exist yet, fall back to stderr.
4. **No sensitive data at rest.** Never store request bodies, query strings, cookies, auth tokens,
   passwords, password hashes, or assessment/answer content in diagnostics.

## Non-goals (2a)

- Content management (2b), change requests (Phase 3).
- Power-user access to any admin page (all `/api/admin/*` stays admin-only).
- Client-side error reporting, alerting/notifications, backups, "run job now" buttons.
- Capturing 4xx responses (validation, 403, 404, 409 are expected outcomes, not errors).

## Design

### 1. Request context

Middleware (outermost app middleware) runs for every request:

- **Request ID.** Generate a fresh random ID (16 lowercase base32 chars). An inbound `X-Request-ID` is
  used **only** if `TRUST_REQUEST_ID=true` (default `false`) **and** it matches `^[A-Za-z0-9-]{8,64}$`.
  Otherwise the supplied value is discarded, a fresh server-owned ID is used, and the request proceeds
  normally; a malformed diagnostic header never fails a request. Never reflect an unvalidated header.
- Stored in a `contextvars.ContextVar` together with, once auth resolves, the user id/username (set by
  `get_current_user`), plus method and matched route template.
- Response header `X-Request-ID` on every response.

**Build info** (`app/core/buildinfo.py`): `APP_COMMIT` and `APP_BUILD_TIME` from env, defaulting to
`unknown`; process start time for uptime. The Dockerfile declares `ARG APP_COMMIT=unknown` /
`ARG APP_BUILD_TIME=unknown` and exports them as `ENV`, so any build path works (`docker compose build`,
CI, `deploy.sh`). `docker-compose.yml` passes `build.args` from `${APP_COMMIT:-unknown}` /
`${APP_BUILD_TIME:-unknown}`. New `scripts/deploy.sh` sets them from `git rev-parse --short HEAD` (with
`-dirty` if the tree is dirty) and `date -u +%FT%TZ`, then runs `docker compose up -d --build`.

### 2. Error capture

#### Sources

| Source | How | `source` value |
|---|---|---|
| Unhandled exception in a request | exception boundary in the request-context middleware (request context in scope) | `unhandled` |
| Handled error logged by app code | `logging.Handler` on the `app` logger, level `ERROR` | `logged` |

- Only the `app` logger hierarchy is ingested (not `uvicorn.*`, `sqlalchemy.*`), so Uvicorn's own
  "Exception in ASGI application" line cannot create a duplicate.
- The exception boundary marks the exception object as captured (`exc.__sb_captured__ = <public_id>`).
  The log handler skips any record whose `exc_info` exception carries that marker. One exception → one
  occurrence.
- `logged` records without `exc_info` are captured with an empty stack; the message is the log message.

#### Unhandled response

`500` with body `{"detail": "Something went wrong on our side.", "error_id": "<public_id>",
"request_id": "<request_id>"}`. If recording failed, `error_id` is `null`. The frontend `ErrorNotice`
shows **"Reference: <error_id>"** (or **"Request: <request_id>"** when `error_id` is null) so a teacher
can report it.

#### Occurrence identity (the teacher-facing reference)

Each occurrence gets `public_id`: 8 lowercase base32 chars, unique (retry on collision). This is the
reference Nina reports and identifies the exact failed request. From it the admin sees the group
("37 occurrences").

#### Fingerprint (grouping)

`sha256(exception_type | route_template | method | app_frames)` where `app_frames` is the list of
`module:function` for traceback frames inside the `app` package (no line numbers, so reformatting or
unrelated edits do not split groups). For `logged` records without a traceback: `sha256(logger_name |
route_template | message_template)` using the unformatted `record.msg`.

#### What is stored per occurrence

time, `public_id`, `request_id`, `source`, user id + username snapshot (null if anonymous), method,
**route template** (e.g. `/api/questions/{question_id}`; never the raw path or query string), HTTP status
(unhandled only), **entity IDs**, user agent (truncated to 300 chars), `app_commit`, exception type,
sanitized message, sanitized stack.

**Entity IDs** come only from matched path params whose name is in
`{question_id, assessment_id, item_id, version_no, user_id, standard_id, course_id, group_id}` and whose
value is an integer. Nothing else from the URL is kept.

#### Sanitization (`app/services/sanitize.py`, applied to message and stack before storage)

1. Remove SQLAlchemy parameter blocks: `[parameters: ...]` → `[parameters: <redacted>]`.
2. Postgres `DETAIL:` values: `Failing row contains (...)` → `Failing row contains (<redacted>)`;
   `Key (...)=(...)` keeps the key expression, redacts the value: `Key (lower(username))=(<redacted>)`.
3. Mask bcrypt hashes (`\$2[aby]?\$\d{2}\$[./A-Za-z0-9]{53}`), JWTs (`eyJ[\w-]+\.[\w-]+\.[\w-]+`), and hex
   or base64 runs ≥ 32 chars that are not inside a file path → `<redacted>`.
4. Mask `password|passwd|secret|token|authorization|cookie` followed by `=`/`:` and a value.
5. Shorten file paths: strip everything up to `app/` for app frames and up to `site-packages/` for
   library frames.
6. Truncate: message 2,000 chars; stack 20,000 chars (keep head and tail with a marker).

Tracebacks are formatted with `traceback.format_exception` (no local variables). Request bodies, headers
(other than user agent), cookies, and query strings are never read by the capture code.

#### Recording (`app/services/errors.py`)

- Uses its **own** `SessionLocal()` and transaction, independent of the request's session (which may be
  mid-rollback). Upserts the group (`INSERT … ON CONFLICT (fingerprint) DO UPDATE` incrementing
  `total_occurrences`, setting `last_seen_at`, latest message) and inserts the occurrence.
- If the group was `resolved`, it becomes `open` again, `reopened_count += 1`, and a status event is
  written with actor `system` ("regressed").
- Any exception during recording is caught, written to stderr with the request ID, and swallowed. The
  original 500 response is still returned.

### 3. Error groups: lifecycle and history

- Status: `open → investigating → resolved` (any transition allowed between these three, with an
  optional note). Changing status requires admin, is audited (`admin.error_status`, detail
  `{from, to, note}`), and appends an `error_group_events` row.
- **Lifetime metadata survives pruning:** `first_seen_at`, `last_seen_at`, `total_occurrences`,
  `reopened_count`, current status/note, and the full `error_group_events` history stay forever. Only
  individual occurrences are pruned. The detail page shows lifetime counts and says "N occurrences
  retained (older ones pruned after 90 days)".

### 4. Jobs

`job_runs` records **migrate**, **import_standards**, **sync_families**, and **prune**, each with trigger
`startup` or `cli`.

- `track_job(kind, trigger)` context manager: inserts a `running` row, and on exit sets `succeeded` +
  counts, or `failed` + sanitized error text, and `finished_at`. Uses its own session. If recording
  fails, stderr only; the job itself still runs and its exit status is unchanged.
- **Startup order** (`backend/docker-entrypoint.sh`): `python -m app.cli migrate` → `python -m app.cli
  bootstrap` (mark-interrupted, import_standards, sync_families, prune) → Uvicorn.
- **migrate**: records `from_revision` (read before upgrading) and `to_revision`. It runs Alembic
  programmatically and writes the job row **after** the upgrade, because `job_runs` may not exist
  beforehand. If the upgrade fails and `job_runs` exists, a `failed` row is written. If the table does
  not exist, the failure is stderr-only and the Jobs page states that pre-schema migration failures
  appear only in container logs. The container still exits non-zero (unchanged behaviour).
- **Interrupted runs:** at the start of `bootstrap`, any `running` row is marked `interrupted` (with
  `finished_at` = now). This assumes one app container, which is the documented deployment.
- **Critical** jobs: migrate, import_standards, sync_families. **Non-critical:** prune.

### 5. Retention (`prune` job)

Runs at every startup (within bootstrap) and via `python -m app.cli prune`. Cutoffs are code constants:

| Data | Kept | Pruned |
|---|---|---|
| `error_occurrences` | 90 days | older rows deleted; groups and group events kept |
| `job_runs` | 180 days | older rows deleted (the prune run being recorded is never deleted) |
| `audit_events` | 2 years | older rows deleted |

The prune job's counts record how many rows each table lost.

### 6. Audit log viewer and target labels

- Migration adds `audit_events.target_label` (text, nullable). `record_audit` gains `target_label=`,
  and every existing caller passes a human label at write time: question → `Q<id> <standard code>`,
  assessment → its title, user → username, error group → `<exception_type> at <route>`. Pre-2a rows
  have no label, and the viewer shows `<type> #<id>`.
- The entry is always viewable even if its target was since archived, deleted, or disabled. The viewer
  shows the stored type/id/label; the link is shown only when the target is still reachable
  (question exists; assessment not soft-deleted; user exists), otherwise the label is plain text marked
  "(no longer available)".
- Filters: actor (user id), action (exact or prefix like `question.`), target type + id, date range
  (`since`/`until`, UTC ISO). Keyset pagination on `id` (`before_id`, `limit` ≤ 200, default 50), newest
  first.

### 7. Overview and health rules

`GET /api/admin/overview` returns build info, uptime, checks, counts, sizes, latest jobs, error summary,
and `backup: null` (placeholder: "Backups are not tracked yet").

**Checks and status** (worst wins):

| Check | Problem | Warning |
|---|---|---|
| Database reachable (`SELECT 1`) | unreachable | — |
| Schema revision vs code head | DB behind code head, or latest migrate run failed | DB ahead of or unknown to this code (e.g. image rolled back) |
| Latest import_standards / sync_families run | failed | interrupted, or none recorded |
| Latest prune run | — | failed or interrupted |
| Disk free on the data volume | < 10% | < 20% |
| Errors | — | any unresolved group with ≥ 3 occurrences in 24h, **or** a group that regressed (reopened) in 24h, **or** an unresolved group seen by ≥ 2 distinct users in 24h |

Anything else is **Healthy**. A single transient error does not change the status. The Overview always
shows the separate facts regardless: "N errors in the last 24h", "M unresolved groups". Each non-healthy
check contributes a one-line reason shown under the banner.

**Data volume disk check.** The Postgres data volume is mounted in the app container read-only at
`/mnt/pgdata` (compose: `postgres_data:/mnt/pgdata:ro`), used **only** for `statvfs`. Setting
`DISK_CHECK_PATH` (default `/mnt/pgdata`) chooses the path. There is **no automatic fallback**: if the
configured path does not exist, the disk figure is `unavailable` and the check is a Warning ("data volume
not mounted at /mnt/pgdata"), never a reading of some other filesystem. Local development can opt in with
`DISK_CHECK_PATH=/`. The app never reads files there. Database size comes from `pg_database_size()`.

**Counts:** users (active/total by role), questions (by status), assessments (active/deleted),
audit events (last 24h).

### 8. Admin API (all `require_role("admin")`)

| Route | Purpose |
|---|---|
| `GET /api/admin/overview` | §7 |
| `GET /api/admin/errors` | groups; filters `status`, `route`, `user_id`, `since`, `until`, `q` (matches exception type/message); keyset on `last_seen_at,id` |
| `GET /api/admin/errors/lookup/{reference}` | occurrence `public_id` or `request_id` → `{group_id, occurrence_id}`; 404 if unknown |
| `GET /api/admin/errors/{group_id}` | group with lifetime metadata and status history |
| `GET /api/admin/errors/{group_id}/occurrences` | retained occurrences, keyset paginated |
| `GET /api/admin/errors/occurrences/{public_id}/diagnostics` | `text/plain` sanitized "Copy diagnostics" block |
| `PATCH /api/admin/errors/{group_id}` | `{status, note}` → audited |
| `GET /api/admin/jobs` | filters `kind`, `status`; keyset paginated |
| `GET /api/admin/jobs/{job_id}` | one run |
| `GET /api/admin/audit` | §6 |

Every admin route is tested for admin-only access (403 power/regular, 401 anonymous). The one 2a
mutation, `PATCH /api/admin/errors/{group_id}`, is tested to write exactly one audit row. (The Phase 1
content-route inventory guard excludes `/api/admin/*` by design.)

**Copy diagnostics block** (plain text, already sanitized):

```
Science Bank error report
Reference: 7f3k2q9d   Request: k2m4...   Group: #12 (37 occurrences, first 2026-09-20, status open)
When: 2026-09-24T19:20:12Z   Commit: 22f5d30   Built: 2026-09-24T19:18Z
User: Nina (power)   Route: POST /api/questions/{question_id}/status   HTTP 500
Entities: question_id=12
User agent: Mozilla/5.0 ...
Exception: sqlalchemy.exc.IntegrityError: ... [parameters: <redacted>]
Stack:
  app/api/questions.py in set_status
  ...
```

### 9. Frontend

- Admin area gets a sub-navigation: **Overview · Errors · Jobs · Audit · Users**. `/admin` is Overview;
  the sidebar "Admin" link points there.
- **Overview:** status banner with reasons; build/uptime; data-volume disk bar; DB size; counts; latest
  run per job kind; error summary with links; backup placeholder.
- **Errors:** filterable group list; a "Find reference" box (goes straight to the group with that
  occurrence highlighted); group detail with lifetime stats, status control + note, status history,
  occurrences (expandable trace), and **Copy diagnostics** per occurrence (clipboard write; a text area
  fallback if clipboard write is unavailable).
- **Jobs:** list with kind/status filters and duration; detail shows counts and error; note about
  pre-schema migration failures.
- **Audit:** filter bar + paginated table; target labels with conditional links.
- `ErrorNotice` shows the reference for 500 responses (§2).

### 10. Data model (migration `0004_admin_ops`)

`error_groups`: `id` PK, `fingerprint` char(64) unique, `exception_type` text, `message` text,
`route` text null, `method` text null, `source` text, `status` text check in (open, investigating,
resolved) default open, `note` text null, `first_seen_at`, `last_seen_at` timestamptz,
`total_occurrences` bigint, `reopened_count` int default 0, `status_changed_at` timestamptz null,
`status_changed_by` FK users null.

`error_group_events`: `id` PK, `group_id` FK cascade, `at`, `actor_id` FK users null, `actor_username`
text (`system` for regressions), `from_status`, `to_status`, `note`. Never pruned.

`error_occurrences`: `id` bigserial PK, `public_id` char(8) unique, `group_id` FK cascade (indexed),
`at` (indexed), `request_id` (indexed), `source`, `user_id` FK users null, `username` text null,
`method`, `route`, `status_code` int null, `entity_ids` jsonb, `user_agent` text null, `app_commit`,
`exception_type`, `message`, `stack`.

`job_runs`: `id` PK, `kind` text, `trigger` text, `status` text check in (running, succeeded, failed,
interrupted), `started_at`, `finished_at` null, `app_commit`, `counts` jsonb, `error` text null; index
(`kind`, `started_at desc`).

`audit_events`: add `target_label` text null.

## Testing and acceptance

Backend (DB tests on the throwaway Postgres; zero skipped):

- Request ID: generated when absent; inbound header ignored by default; accepted only when trusted and
  valid; an invalid or oversized inbound value is discarded and replaced by a fresh server ID while
  the request itself is processed normally (never failed); present on every response.
- Unhandled exception (triggered via a test-only route or a monkeypatched service) → 500 with
  `error_id` + `request_id`; one group, one occurrence; the same error again → same group, count 2;
  same exception on a different route → a new group.
- No duplicate: an unhandled exception that app code also logs yields exactly one occurrence.
- `logged` source: `log.error(...)` inside a request creates an occurrence with user/route context.
- Recording failure (recording service forced to raise) still returns the original 500 with
  `error_id: null`; nothing else breaks.
- Sanitization unit tests for every rule in §2, including a real `IntegrityError` from inserting a
  duplicate user (hash and username values redacted).
- Entity IDs: only allow-listed integer params stored; no query string persisted.
- Regression: resolving then re-triggering reopens with a `system` event and `reopened_count` 1.
- Status change: admin-only, audited, event row written; power/regular → 403.
- Lookup by `public_id` and by `request_id`; unknown → 404.
- Jobs: success/failure/counts recorded; `running` rows become `interrupted` on bootstrap; migrate job
  records from/to revisions; recording failure does not change job outcome.
- Prune: boundary tests at 90d/180d/2y; groups and group events survive with lifetime counters intact.
- Health rules: one test per row of §7, including "single transient error stays Healthy".
- Audit viewer: each filter, pagination, target label written for each action type, and a
  deleted/archived target still viewable with `available: false`.
- Overview and all admin GET routes: 403 for power/regular, 401 anonymous.
- Build info defaults to `unknown` when env is unset.

Frontend: `npm run lint`, `npm run build`, and a browser check that walks Overview → Errors (find a
reference, change status, copy diagnostics) → Jobs → Audit as admin, and confirms that a power user has
no Admin link.

Deploy acceptance: `scripts/deploy.sh` → Overview shows the real commit and build time; Jobs shows this
startup's migrate/import/sync/prune; the data-volume disk figure matches `df` for the Docker volume path.

## Open items for 2b

- Content page reuses audit `target_label` and the admin sub-nav (adds **Content**, visible to power
  users too).
- Ownership reassignment preview endpoint and bulk archive are 2b's own spec.
