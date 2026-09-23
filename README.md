# Science Bank

A self-hosted question-bank and assessment-generation tool for South Carolina high school
science teachers, built for Biology 1, Biology 2, and Chemistry.

## What this is

Not an AI chat tool. Science Bank is a **deterministic question-family engine**: a teacher picks
a course, standard, DOK level, question format, and stimulus type, and gets back a generated
question set with an answer key — built from templated generators parameterized by real, valid
data (population tables, Punnett crosses, titration curves, gene-frequency scenarios, etc.),
not prose invented by a language model at generation time.

The SC state standards (Performance Expectations, SEP/DCI/CCC, assessment boundaries,
terminology) are the authority. They're stored as structured, versioned reference data sourced
directly from official South Carolina Department of Education documents — see
[`data/standards/`](data/standards/) — never reconstructed from a model's memory.

## Status

**Data layer: done.** All Performance Expectations and anchoring-phenomenon bundles for
Biology 1, Biology 2, and Chemistry (2026-2027) are extracted and structured. See
[`data/standards/README.md`](data/standards/README.md) for the schema.

**App: Phase 1 skeleton.** Docker Compose brings up Postgres, a FastAPI backend (health checks,
single-teacher cookie auth, Alembic wired up), and a React+Vite+Tailwind frontend shell. No
domain features (standards browser, question bank, generators) yet — that's Phases 2+.

👉 **For full context — what's decided, what's next, and where to pick up — read
[`PROJECT_STATUS.md`](PROJECT_STATUS.md).** It's written as a complete handoff document for
anyone (or any AI session) resuming this project cold.

## Running locally

```
cp .env.example .env   # fill in TEACHER_PASSWORD_HASH and JWT_SECRET
docker compose up --build
```

- Frontend (dev server): http://localhost:5173
- Backend: http://localhost:8000 — health checks at `/healthz` (liveness) and `/readyz`
  (DB connectivity)

In the homelab deployment, the existing Caddy reverse proxy fronts the `frontend`/`backend`
services — this repo's `docker-compose.yml` doesn't include Caddy itself.

## Planned stack

```
Frontend:  React + Vite + TypeScript + Tailwind
Backend:   Python + FastAPI + Pydantic + SQLAlchemy + Alembic
Database:  PostgreSQL 16
Deploy:    Docker Compose, behind an existing Caddy reverse proxy
```

## Repository layout

```
science-bank/
├── data/
│   └── standards/       <- SC standards reference data (done — see its own README)
├── frontend/             <- React + Vite + TS + Tailwind shell (Phase 1)
├── backend/               <- FastAPI + SQLAlchemy + Alembic shell (Phase 1)
├── docker-compose.yml    <- postgres + backend + frontend
├── .env.example          <- copy to .env before running
├── PROJECT_STATUS.md    <- full project handoff / decision log
└── README.md              <- this file
```
