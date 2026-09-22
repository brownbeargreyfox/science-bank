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

**App: not started.** No frontend, backend, or database code exists yet.

👉 **For full context — what's decided, what's next, and where to pick up — read
[`PROJECT_STATUS.md`](PROJECT_STATUS.md).** It's written as a complete handoff document for
anyone (or any AI session) resuming this project cold.

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
├── frontend/             <- not started
├── backend/               <- not started
├── PROJECT_STATUS.md    <- full project handoff / decision log
└── README.md              <- this file
```
