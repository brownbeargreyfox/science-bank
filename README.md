# Science Bank

A self-hosted question bank and assessment builder for South Carolina high school science
(Biology 1, Biology 2, Chemistry), built for one teacher.

## What this is — and isn't

Science Bank is **not** an AI question writer. Questions come from **deterministic question
families**: seeded generators that draw scientifically valid datasets (population surveys,
Punnett crosses, reaction-rate experiments) and compute every answer and distractor from the same
parameters the student sees. Each family is bound to one exact Performance Expectation in the
official SCDE standards data under [`data/standards/`](data/standards/), and every template cites
the SCDE "observable feature of student performance" it targets. The same seed and family version
always regenerate the same set; saved questions store their full content, so they never depend on
regeneration.

## What works today (MVP)

- **Standards browser** — all 38 PEs and 15 anchoring-phenomenon bundles for 2026-2027, with search,
  filters, the state assessment boundary, SEP/DCI/CCC, observable performances, and source-document
  provenance.
- **Generate** — pick course → standard → family → DOK / question type / templates → quantity,
  preview with the answer key, then save to the bank. Three families:

  | Family | Standard | What students do |
  |---|---|---|
  | Carrying capacity: population survey data | Biology 1 **B-LS2-1** | Read logistic survey data, estimate K, identify and classify the limiting factor that shifted it, predict effects, reason about scale |
  | Trait probability and distribution | Biology 1 **B-LS3-3** | Punnett probabilities and ratios (complete/incomplete/codominance), compare observed offspring to expected (qualitatively — no chi-square), environment × genotype data |
  | Reaction rate: temperature and concentration | Chemistry **C-PS1-5** | Interpret two-reactant rate experiments, explain with collision theory, make qualitative predictions |

- **Question bank** — filter/search, review workflow (generated → reviewed → approved, or rejected /
  archived) with history, editing that appends versions (originals are never overwritten), restore.
- **Assessments** — build from bank questions (versions are pinned), reorder, DOK and standards
  coverage, and print-ready **student** (no answers) and **teacher** (key + rationales) views.

Full handoff, decisions, and roadmap: [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## Stack

```
Frontend:  React 19 + Vite + TypeScript + Tailwind v4   (built into the app image)
Backend:   Python 3.12 + FastAPI + Pydantic + SQLAlchemy 2 + Alembic
Database:  PostgreSQL 16
Deploy:    Docker Compose (postgres + app), behind the existing Caddy reverse proxy
```

## Deploying (homelab)

```sh
cp .env.example .env         # set POSTGRES_PASSWORD, JWT_SECRET (32+ random chars), APP_PORT
docker compose up -d --build
docker compose exec app python -m app.cli set-password    # create Nina's login (prompts)
```

On every start the container runs `alembic upgrade head`, then imports the standards JSON and
syncs question families (both idempotent), then serves the API and the built frontend on
`${APP_BIND}:${APP_PORT}` (default `127.0.0.1:8420`).

### Behind Caddy

The existing Caddy runs with host networking and proxies to host ports, so add a site block like
this to the Caddyfile (the app does not modify it):

```caddyfile
science.example.com {
	reverse_proxy 127.0.0.1:8420
}
```

With `ENVIRONMENT=production` the session cookie is `Secure`, so serve it over HTTPS (Caddy does).
Browsing to plain `http://<lan-ip>:<port>` (e.g. with `APP_BIND=0.0.0.0`) will appear to log in
and then bounce back to the login page; use the Caddy HTTPS hostname, or `ENVIRONMENT=development`
for LAN-only testing.

### Operations

| Task | Command |
|---|---|
| Set / change password | `docker compose exec app python -m app.cli set-password` |
| Re-import standards after editing `data/standards` | rebuild the image (`docker compose up -d --build`); import runs on start |
| Back up | `docker compose exec postgres pg_dump -U science_bank science_bank > backup.sql` |
| Restore | `docker compose exec -T postgres psql -U science_bank science_bank < backup.sql` |
| Logs | `docker compose logs -f app` |

## Development

```sh
# Backend (needs a Postgres; e.g. docker compose -f docker-compose.yml -f docker-compose.dev.yml up postgres)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://science_bank:<pw>@127.0.0.1:54329/science_bank
.venv/bin/alembic upgrade head && .venv/bin/python -m app.cli bootstrap
.venv/bin/python -m app.cli set-password
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm ci
API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
npm run gen:api     # regenerate src/api/schema.d.ts after API changes
                    # (first: backend/.venv/bin/python backend/scripts/dump_openapi.py)
```

Or everything with hot reload: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`.

### Tests and checks

```sh
cd backend
.venv/bin/ruff check app tests
.venv/bin/python -m pytest                     # engine tests (no database needed)
TEST_DATABASE_URL=postgresql+psycopg://user:pw@127.0.0.1:5432/sb_test .venv/bin/python -m pytest
                                               # + migration, importer, API tests (db is recreated)
cd ../frontend && npm run lint && npm run build
```

## Repository layout

```
science-bank/
├── data/standards/          SC standards reference data (authoritative, versioned by year)
├── backend/
│   ├── app/api/             FastAPI routers (auth, standards, generate, questions, assessments)
│   ├── app/models/          SQLAlchemy models
│   ├── app/schemas/         Pydantic request/response models
│   ├── app/services/engine/ deterministic engine core (seeding, validation, set assembly)
│   ├── app/services/families/  the question families + registry
│   ├── app/standards/       idempotent standards importer
│   ├── app/cli.py           import / bootstrap / set-password
│   ├── alembic/             migrations
│   └── tests/
├── frontend/                React app (src/api/schema.d.ts is generated from the OpenAPI schema)
├── Dockerfile               multi-stage production image
├── docker-compose.yml       production-style deployment
├── docker-compose.dev.yml   hot-reload override
└── PROJECT_STATUS.md        handoff / decision log
```
