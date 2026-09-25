# Science Bank — Detailed Engineering Handoff

Last updated: 2026-09-24

## Executive summary

Science Bank is a self-hosted question bank and assessment builder for South Carolina high-school
science. It currently supports Biology 1, Biology 2, and Chemistry standards for the 2026–2027
cycle. The application is usable as an MVP: teachers can register accounts, browse standards,
generate deterministic question sets, edit/review/save questions, build assessments, and print
student and teacher versions.

The application is deliberately **not an AI question writer**. Every generated item is built by
versioned deterministic code from a seeded parameter set. Standards data is transcribed from SCDE
source documents and is the authority for alignment, boundaries, terminology, and observable
student performances. Do not add LLM-authored live questions unless the product decision is
explicitly changed.

The active deployment has been rebuilt after the EOCEP change and is healthy. The application
container is exposed only on `127.0.0.1:8420`; Caddy and Tailscale Serve are the supported access
paths.

## Current repository and deployment state

- Repository: `/home/brandon/apps/science-bank`
- Remote: `https://github.com/brownbeargreyfox/science-bank.git`
- Working branch: `claude/amazing-cray-apalq2`
- Latest deployed feature commit: `22f5d30` (roles, ownership, audit log, and account administration;
  migration 0003).
- Roles/ownership/audit/admin is live. The deployment backup is
  `backups/pre-0003-2026-09-24-1519.sql`; the previous app image is tagged
  `science-bank-app:pre-0003` for rollback. Nothing has been pushed to GitHub.
- The branch includes the SCDE source-document merge (`84c8d9c`).
- Deployment: Docker Compose, Postgres 16, FastAPI/Uvicorn, React/Vite SPA.
- Application service: `science-bank-app-1`
- Database service: `science-bank-postgres-1`
- Both services were healthy after the last rebuild.

### Access paths

| Purpose | Endpoint | Notes |
|---|---|---|
| Reverse-proxied web access | `https://science.maefranklin.com` | Existing Caddy route proxies to `127.0.0.1:8420`. |
| Private tailnet access | `https://jellyfin.tail4a63e4.ts.net:8443/` | Tailscale Serve terminates TLS and proxies privately to the loopback app. |
| Direct host port | `http://127.0.0.1:8420` | Host-only diagnostic path. Do not expose it publicly; production authentication requires HTTPS. |

Tailscale Serve configuration is persistent in Tailscale, not this repository. Its intended
configuration is:

```sh
sudo tailscale serve --bg --https=8443 127.0.0.1:8420
tailscale serve status
```

## Product decisions that must be preserved

1. **Deterministic generation only.** A seed, family key/version, options, and code determine the
   output. Saved questions contain full snapshots, so they never depend on future regeneration.
2. **SCDE standards are authoritative.** Do not paraphrase or infer standards at generation time.
   Use the JSON data in `data/standards/` and source provenance.
3. **Question versions are append-only.** Teacher edits create a new `question_versions` record.
   Assessments pin a version, preventing later edits from silently changing an assessment.
4. **Family changes require a version bump.** If generator output changes, increment the family
   version and update the associated deterministic/golden tests in the same commit.
5. **Classroom and EOCEP are different modes.** Classroom mode is default. EOCEP mode must obey
   imported assessment constraints and must not be presented as full state-test equivalence.

## Architecture

```text
Browser
  ├─ Caddy HTTPS -> 127.0.0.1:8420 -> FastAPI + built React SPA
  └─ Tailscale Serve HTTPS :8443 -> 127.0.0.1:8420

FastAPI
  ├─ Authentication/session cookies
  ├─ Standards, generation, question-bank, assessment APIs
  ├─ Deterministic family engine
  └─ SQLAlchemy/Alembic

PostgreSQL
  ├─ standards/course/source/bundle data
  ├─ teacher accounts
  ├─ family generation provenance
  ├─ immutable question versions
  └─ assessments with version-pinned items
```

The production container entrypoint runs, in order:

1. `alembic upgrade head`
2. `python -m app.cli bootstrap`
3. Uvicorn

Bootstrap imports standards JSON and synchronizes code-defined question-family metadata. Both are
idempotent. Do not manually modify database records that are owned by the standards importer.

## Accounts and authentication

Local username/password accounts (bcrypt) with cookie-backed JWT sessions. The JWT carries identity
only (`uid`); role and active state are loaded from the database on **every** request, so demoting or
disabling someone takes effect immediately. Tokens issued before migration 0003 (no `uid`) resolve by
username. Usernames are unique case-insensitively (`Nina` and `nina` are the same account).

Roles (design: `docs/superpowers/specs/2026-09-24-roles-ownership-audit-design.md`):

| Capability | Teacher (regular) | Power user | Admin |
|---|:-:|:-:|:-:|
| Browse standards, the bank, and all assessments; print | ✓ | ✓ | ✓ |
| Generate and save questions (you become the owner) | ✓ | ✓ | ✓ |
| Create assessments (you become the owner) | ✓ | ✓ | ✓ |
| Edit, restore versions, change status of **your own** questions | ✓ | ✓ | ✓ |
| Change, reorder, delete, restore **your own** assessments | ✓ | ✓ | ✓ |
| Add anyone's question to your own assessment | ✓ | ✓ | ✓ |
| Do the above to **other teachers'** content | — | ✓ | ✓ |
| Manage accounts, roles, passwords, registration (Admin → Users) | — | — | ✓ |

- Live roles after migration 0003: `brandon` = admin, `Nina` = power user; new registrations are
  regular teachers.
- Ownership: `questions.owner_id` and `assessments.owner_id`; existing content was backfilled to
  `brandon`. Every mutating route goes through `app/core/policy.py`; `tests/test_permissions.py`
  fails if a new mutating route is not in its policy matrix.
- Assessments are soft-deleted (`deleted_at`) and restorable; questions are archived, never deleted.
- Registration is a DB setting (`site_settings.registration_open`), toggled in Admin → Users.
  `REGISTRATION_OPEN` in `.env` only seeds it at migration time.
- The last-active-admin guard uses row locks so concurrent demotions cannot remove every admin.

Break-glass CLI (audited as `cli`):

```sh
docker compose exec app python -m app.cli list-users
docker compose exec app python -m app.cli set-password --username <name>     # creates the account if missing
docker compose exec app python -m app.cli set-role --username <name> --role admin|power|regular
docker compose exec app python -m app.cli set-active --username <name> --active true|false
```

### Audit log

`audit_events` is append-only: logins, failed logins (attempted username, no password), logouts,
registrations, question/assessment changes, admin and CLI actions, each with actor, target, IP, and a
small JSON detail. There is no UI yet (Phase 2). Query it directly:

```sh
docker compose exec -T postgres psql -U science_bank science_bank -c \
  "select at, actor_username, action, target_type, target_id, ip, detail from audit_events order by id desc limit 50;"
```

### Public-product caveat

The product may ultimately become public-facing for Nina and other teachers. Do **not** simply
leave the current local registration open on a public hostname. Before a public launch, implement:

- managed OpenID Connect identity (hosted provider such as Auth0 or Clerk),
- verified email, self-service recovery, MFA/passkeys, Google/Microsoft sign-in,
- per-user/private workspaces and explicit sharing,
- anti-abuse controls and edge rate limits,
- off-host database backups, monitoring, privacy/terms pages.

The recommended model is private workspaces by default, with teacher-managed sharing. MFA secures
accounts but does not provide data isolation.

## Standards data

### Structured reference data

`data/standards/SC/2026-2027/` contains the application’s structured source of truth:

- `biology-1.json` — 14 Biology 1 PEs
- `biology-2.json` — 12 Biology 2 PEs
- `chemistry.json` — 12 Chemistry PEs
- `*-bundles.json` — 15 SCDE anchoring-phenomenon bundles total
- `biology-1-eocep.json` — EOCEP constraints currently imported for supported Biology 1 families

Each PE includes official text, clarification statement, assessment boundary, SEP/DCI/CCC,
observable performances, terminology, topics, and provenance. A standard must always be resolved
by its course plus code; four Biology codes occur in both Biology 1 and Biology 2 with distinct
boundaries.

### Original SCDE PDFs

`SCDoE Targets/` contains the official PDFs committed for reference, including:

- Biology 1/2 and Chemistry Performance Targets
- Biology 1/2/Chemistry Bundling Guides
- EOCEP Biology 1 Performance Level Descriptors User Guide
- EOCEP Biology 1 Assessment Specifications 2025–2026
- SEP and CCC instructional reference guides
- sample Biology instructional/assessment material

The PDFs are reference source materials. The generator must consume validated, structured JSON
rather than extract PDF text at request time.

## Question-family engine

Family implementation lives in `backend/app/services/families/`. Core deterministic machinery is
in `backend/app/services/engine/`.

### Implemented families

| Family key | Standard | Version | Scope |
|---|---|---:|---|
| `population-carrying-capacity` | Biology 1 B-LS2-1 | 1.0.0 | Logistic survey data, carrying capacity, limiting factors, scale. |
| `trait-probability` | Biology 1 B-LS3-3 | 1.1.0 | Monohybrid genetics, complete/incomplete/codominance, qualitative observed-vs-expected data, genotype/environment effects. |
| `reaction-rate` | Chemistry C-PS1-5 | 1.0.0 | Simple two-reactant concentration/temperature experiments and collision-theory reasoning. |

Engine invariants are tested in `backend/tests/test_engine.py`:

- SHA-256-derived sub-seeds, never Python `hash()`.
- Randomness only through the custom `Rng` wrapper.
- Keys/distractors calculated from values students see.
- Ambiguous outputs redraw deterministically.
- MC items have one key and distinct choices/rationales.
- Every template cites an existing observable-performance bullet.

`QUESTION_FAMILY_CATALOG.md` is the detailed expansion plan. The Tier 1 catalog entries refer to
the three original conceptual family shapes; their production keys are the names above.

### Next family work

`quantitative-conservation` (displayed as Mole stoichiometry) is implemented for Chemistry C-PS1-7.
It uses only the reviewed reaction/molar-mass catalog and makes conservation reasoning—not a bare
conversion—the required default endpoint. The next Chemistry bundle target is **Stability & Change
in Chemical Systems**, where a future shared reaction stimulus can support C-PS1-5 reaction-rate
items and C-PS1-7 quantitative-conservation items.

Bundle-driven generation is **not implemented**. Current bundle browsing is implemented, but there
is no multi-standard shared-stimulus generation API, schema, persistence model, or UI yet.

## EOCEP practice mode

EOCEP mode was completed for the currently EOCEP-eligible implemented Biology 1 families.

### What exists

- Alembic migration `0002_eocep_constraints` adds `standards.eocep_constraints` (JSONB).
- `biology-1-eocep.json` holds structured, source-page-referenced constraints.
- The standards importer recognizes `*-eocep.json` separately from course and bundle files and
  stores constraints on their matching Biology 1 standard.
- The Generate API accepts `generation_mode: "classroom" | "eocep"`.
- EOCEP requests are accepted only for Biology 1 standards with imported EOCEP constraints.
- EOCEP selection is stored in generation options/provenance.
- Generate UI has Classroom and EOCEP Practice choices.
- Classroom mode is the default and is unchanged.

### Current imported EOCEP coverage

| Standard | Family | Source pages | Key constraints |
|---|---|---|---|
| B-LS2-1 | population-carrying-capacity | Assessment Specifications pp. 11–12 | No population-growth calculations, specific nutrient cycles, or multi-population relationships; use carrying-capacity/limiting-factor models. |
| B-LS3-3 | trait-probability | Assessment Specifications pp. 15–16 | No constructed pedigrees/dihybrid crosses, specific disorders, Hardy-Weinberg, or chi-square; monohybrid ratios/probabilities are permitted. |

Do not claim EOCEP support for other Biology 1 standards until their source constraints are
structured, imported, and generator-specific enforcement/tests are added.

## Operations

### Deploy/rebuild

```sh
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

### Database backup and restore

```sh
docker compose exec postgres pg_dump -U science_bank science_bank > backup.sql
docker compose exec -T postgres psql -U science_bank science_bank < backup.sql
```

Set up scheduled, encrypted, **off-host** backups before teachers accumulate meaningful content.
Also preserve `.env`, especially `JWT_SECRET`; do not commit it.

### Development checks

```sh
cd backend
.venv/bin/ruff check app tests
.venv/bin/python -m pytest

cd ../frontend
npm run lint
npm run build
```

Database-backed tests require `TEST_DATABASE_URL`; without it they are skipped. Run them against a
throwaway Postgres (never production):

```sh
docker run -d --rm --name sb-testdb -p 127.0.0.1:54330:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54330/sb_test .venv/bin/python -m pytest -q
```

The acceptance bar is zero skipped DB tests.

## Immediate recommended work

1. Use `quantitative-conservation` (Mole stoichiometry) for C-PS1-7 in a classroom unit, then use it
   to design the first bundle-driven shared Chemistry stimulus set. This is classroom Chemistry work
   and does not extend Biology EOCEP coverage.
2. Nina should use the current families in an actual unit and record edits; revise templates only
   with a family version bump and updated deterministic tests.
3. Administration: Phase 2a operational visibility (Overview, Errors, Jobs, Audit) is being designed
   in parallel. Follow with Phase 2b content management, then Phase 3 change requests; both reuse
   `policy.can_modify` and `audit_events`.
4. Expand `biology-1-eocep.json` progressively as each Biology 1 family is added. Treat the EOCEP
   Assessment Specifications as item-writer constraints, not merely display text.
5. Add scheduled off-host Postgres backups and a Uptime Kuma `/readyz` monitor.
6. If moving toward a public product, do identity/workspaces before opening registration to
   strangers; do not postpone data isolation until after content has accumulated.
