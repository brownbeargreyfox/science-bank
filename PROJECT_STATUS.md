# Science Bank — Project Status & Handoff

Last updated: 2026-09-22 (MVP vertical slice). Written so a fresh Claude session (or Nina, or Codex) can pick this up
cold with zero prior context.

## 1. What this project is

A self-hosted **teacher question-bank and assessment-generation tool** for South Carolina high
school science (Biology 1, Biology 2, Chemistry to start), being built for **Nina**, a science
teacher. The person driving this build is Nina's spouse/colleague (the user in this chat),
working from a homelab (existing Docker/Caddy/Ollama setup).

### The core design decision — read this before writing any generation code

The very first draft of this idea leaned on an LLM to generate questions live. **That direction
was explicitly rejected.** Nina didn't ask for an AI tool, and the user does not want to build one.
The agreed approach instead:

> The site does not generate questions by asking an LLM to invent them. It's a **deterministic
> question-family engine** — templated question generators (parameterized by real, valid data:
> population tables, Punnett crosses, titration curves, gene-frequency scenarios, etc.) built
> against the *actual SC standards content*, which is stored as structured reference data, not
> reconstructed from a model's memory.

The product is a teacher productivity tool: pick a course → standard → DOK → question
type/stimulus → get a usable set with an answer key, built from templates and real SCDE
Performance Target language, not prose an LLM improvised.

**Do not build an AI chat/generation feature into this app unless the user explicitly reverses
this decision again in a future session.** If a future me (or anyone) reads only the original
long-form brainstorm messages earlier in conversation history and starts building an LLM
question-writer, stop — that plan was superseded.

### Why this matters for architecture
- Standards data (Performance Expectations, SEP/DCI/CCC, assessment boundaries, terminology) is
  the **authority**. It lives in versioned JSON files under `data/standards/`, sourced directly
  from official SCDE PDFs, never invented or paraphrased by a model at generation time.
- The "AI" work in this project, if any ever happens, is confined to *authoring assistance*
  (e.g., "help me write a distractor") — never the system of record for what a standard means.

## 2. Decisions already made (don't re-litigate these)

Asked and answered via AskUserQuestion on 2026-09-22:

1. **Initial scope**: small set of question families first (2-3 families, e.g.
   data/graph interpretation + one Biology 1 topic), not the full catalog. Ship something usable
   in weeks, then expand.
2. **Deployment**: homelab Docker Compose behind the existing Caddy reverse proxy. Backend talks
   to the existing Ollama service if/when any AI-assist features are added later — but the core
   app does NOT require Ollama or any LLM to function.
3. **Build order**: standards data extraction first (done — see below), then app skeleton next
   (this document is the plan for that).

Tech stack (from the original brief, not yet reversed):
```
Frontend:  React + Vite + TypeScript + Tailwind
Backend:   Python + FastAPI + Pydantic + SQLAlchemy + Alembic
Database:  PostgreSQL 16
Deploy:    Docker Compose, behind existing Caddy
```

## 3. What's done: the standards data layer

Location: `data/standards/SC/` (relative to repo root `science-bank/`).

```
data/standards/
  README.md                          <- schema documentation, READ THIS for field-by-field detail
  SC/
    sources.json                     <- provenance manifest: every source PDF, ingest status
    2026-2027/
      biology-1.json                 <- DONE: all 14 Biology 1 Performance Expectations
      biology-2.json                 <- DONE: all 12 Biology 2 Performance Expectations
      chemistry.json                 <- DONE: all 12 Chemistry Performance Expectations
      biology-1-bundles.json         <- DONE: 6 anchoring-phenomenon bundles
      biology-2-bundles.json         <- DONE: 4 bundles
      chemistry-bundles.json         <- DONE: 5 bundles
```

**Every one of these JSON files has been validated as well-formed** (checked with `node -e
"require(...)"` and PE/bundle counts confirmed to match the source PDFs).

### What's in the PE files (biology-1.json / biology-2.json / chemistry.json)
Each Performance Expectation record has: `code`, `performance_expectation` (full official text),
`clarification_statement`, `state_assessment_boundary`, `sep` (Science and Engineering Practice
name+description), `dci[]` (Disciplinary Core Idea(s), code+name+text), `ccc` (Crosscutting
Concept name+description), `observable_performances` (SCDE's "observable features of student
performance" bullets — the closest thing to a DOK rubric SCDE provides, grouped by the source
doc's own subheadings), `topics[]` (tag list for a course/topic picker UI), `terminology[]`
(SCDE's vocabulary list), and on some PEs `question_family_candidate: true` flagging PEs that are
strong fits for a deterministic dataset-generator (anything already quantitative: carrying
capacity, Punnett ratios, gene frequency, stoichiometry, reaction rate, thermodynamics, etc.).

Biology 2 PEs additionally carry `repeat_of_biology_1: true` on the 4 PEs shared with Biology 1
(B-LS1-1, B-LS3-2, B-LS3-3, B-LS4-1) — Biology 2 is **not EOCEP-assessed**, so instruction on
those extends past the Biology 1 state assessment boundary; don't apply the Bio-1 boundary
verbatim to Bio-2 questions on those 4 PEs.

Full field-by-field schema doc: **`data/standards/README.md`** — read this before writing any
code that consumes these files.

### What's in the bundles files
Each bundle = an SCDE-suggested anchoring phenomenon (a real-world hook like "Isle Royale
populations" or "CRISPR") with a narrative paragraph, a list of `aligned_pes` (with a `partial`
flag for PEs that connect but aren't fully met), `connected_pes` (cross-course/cross-discipline
codes, mostly out of scope for this app, kept for reference), and
`example_anchoring_phenomena[]`. **Use case**: when a teacher's request spans multiple related
standards, a bundle suggests a shared stimulus set instead of generating disconnected standalone
questions.

### What's NOT yet ingested (still just source PDFs, not JSON)
All source PDFs live in:
`C:\Users\howellbj\OneDrive - charlestoncpw.com\Documents\Nina's question thing\`

Tracked in `sources.json` with `ingested_into: null`:
- **EOCEP Biology 1 Performance Level Descriptors User's Guide_v.2.pdf** — state-test-mode
  reference, distinct from classroom Performance Targets. Should become the constraint layer for
  a future "EOCEP Practice" generation mode (vs. default "Classroom" mode).
- **State Assessment Specifications_EOCEP Biology 1_2025-2026.pdf** — item-writer guidance,
  vocabulary limits, state-assessment boundaries for EOCEP-style items specifically.
- **Using Science and Engineering Practices in Secondary Science Classrooms.pdf** — reference
  library of legitimate SEP-aligned task types. Candidate for a future `sep.json`.
- **Using Crosscutting Concepts in Secondary Science Classrooms.pdf** — CCC reasoning-pattern
  library with elicitation prompts. Candidate for a future `ccc.json`.
- **ESC633_GRHS_BIOL_IS_SAMP.pdf** — a sample instructional/assessment item set, not yet reviewed
  (large PDF, needs page-range read).

Also present but out of current course scope (Nina/the user only asked for Biology 1, Biology 2,
Chemistry): Anatomy and Physiology, Earth and Space Science, and Physics Performance Targets +
Bundling Guides. Leave these alone unless the user asks to add those courses.

None of the above blocks the app. They can be ingested incrementally later,
same pattern as the files already done (read PDF → structure into JSON → validate → update
`sources.json` + README).

## 4. What's built: the MVP vertical slice

Everything below exists, is tested, and runs as one Docker image + Postgres. See README.md for
deploy/dev commands.

### 4.1 Data model (Alembic migration `0001`)
- `source_documents`, `courses`, `standards`, `topics`/`standard_topics`, `bundles`/`bundle_standards`
  — loaded by `backend/app/standards/importer.py`.
  - **Standards are keyed per course and year**: a course is unique on (state, use_year, slug) and a
    standard on (course, code). B-LS1-1, B-LS3-2, B-LS3-3, B-LS4-1 exist in both Biology 1 and 2 with
    different boundaries, so *never look a standard up by code alone* — use its id, or course + code.
  - The importer only reads the JSON, upserts on natural keys with per-record sha256, reports
    created/updated/unchanged, never deletes (questions reference standards), and resolves each
    bundle's `aligned_pes` inside that bundle's own course. Re-running is a no-op (tested).
- `users` (single teacher; bcrypt hash set via `python -m app.cli set-password`).
- `question_families` (catalog mirror of code-defined families, synced at start-up after checking
  every template's observable-performance citation exists), `question_family_runs` (seed + options +
  parameters of each saved generation), `stimuli`, `questions` (status + provenance snapshot),
  `question_versions` (append-only; `origin` = engine | teacher_edit), `question_status_events`,
  `assessments`, `assessment_items` (pin a specific question version).
- The planned `question_choices` table was folded into `question_versions.choices` (JSONB) so a
  version is one immutable snapshot of stem + choices + key.

### 4.2 Deterministic question-family engine (`backend/app/services/engine/`, `.../families/`)
Invariants (all covered by `backend/tests/test_engine.py`):
- Sub-seeds are sha256(seed, family, version, group, template, attempt) — never Python `hash()`.
  Randomness goes only through `Rng`, built on `random.Random.random()` (the one stream CPython
  guarantees across versions). Same seed + options ⇒ byte-identical output, also across processes
  with different PYTHONHASHSEED. Golden digests are pinned per family: **if a change alters output,
  bump the family `version`** rather than editing the digest, so saved seeds stay reproducible.
- Keys and distractors are computed from exactly the values rendered to students (rounded/noised
  table values), and ambiguous draws (ties, near-duplicate distractors) are rejected and redrawn
  deterministically. Every MC item has exactly one key and four distinct choices, each with a rationale.
- Each family binds to exact (state, course slug, PE code) pairs; each template cites the
  `observable_performances` category/index it elicits. Saving snapshots provenance onto each question
  (PE text, boundary, source document + published date + file hash, family version, template, cited
  observable performance, seed, group, attempt).
- Save re-generates server-side from the seed; client-edited payloads are never trusted.

Families (version 1.0.0):
| Key | Standard | Notes on alignment |
|---|---|---|
| `population-carrying-capacity` | Biology 1 B-LS2-1 | Logistic survey data with one limiting-factor change (drought, predators, forage, dissolved O₂, food supply, salinity) and a constant control factor; items on fastest growth, estimating K, identifying/classifying the factor, predicting reversal, scale (PE mentions scale). No equation derivation (boundary). |
| `trait-probability` | Biology 1 B-LS3-3 | Punnett enumeration for complete/incomplete/codominance; observed-vs-expected compared qualitatively (boundary excludes chi-square and Hardy-Weinberg); genotype × environment data (hydrangea soil pH, Himalayan rabbit temperature) for the LS3.B environmental emphasis. Not bound to the Biology 2 copy of B-LS3-3 (different boundary). |
| `reaction-rate` | Chemistry C-PS1-5 | Two-reactant reactions only (thiosulfate + HCl, Mg + HCl, marble + HCl); concentration varies only for a dissolved reactant; temperature items are qualitative (boundary); time-to-endpoint data are handled as inverse rate. No enzymes (would need an optimum model). |

### 4.3 API (`backend/app/api/`)
All `/api/*` routes except login/logout require the session cookie (enforced at router level; a
test walks every route). Unknown `/api/*` paths return JSON 404s. The student print endpoint is
built without any key fields (tested), so the answer key cannot leak through the UI.

### 4.4 Frontend (`frontend/`)
React + Vite + TS + Tailwind; API types generated from the backend OpenAPI schema
(`npm run gen:api`). Pages: login, dashboard, standards browser/detail/bundles, generate
(preview → save), question bank, question detail (edit/versions/status/provenance), assessments
(builder + student/teacher print views with SVG charts and table alternatives).

### 4.5 Deployment
Root `Dockerfile` builds the SPA and serves it from FastAPI; the entrypoint runs
`alembic upgrade head` → `app.cli bootstrap` (import + family sync + optional first-account
bootstrap) → uvicorn. `docker-compose.yml` publishes only `${APP_BIND:-127.0.0.1}:${APP_PORT:-8420}`;
Caddy (host network) proxies to it — see README. `ENVIRONMENT=production` makes cookies Secure,
hides `/docs`, and refuses to start with a weak `JWT_SECRET`.

## 5. What's next (suggested order)
1. Nina uses it for a unit; collect edits she makes to generated items — they show which templates'
   wording to improve (bump the family version when output changes).
2. More families from the `question_family_candidate: true` PEs: C-PS1-7 (stoichiometry),
   C-PS3-4 (thermal equilibrium), B-LS4-4 (natural selection data), Biology 2 B-LS2-2/B-LS2-4.
   Each new family: bind to exact (course, code), cite observable performances, add invariant tests.
3. Bundle-driven sets: one shared stimulus serving several aligned PEs of a bundle.
4. Ingest the EOCEP documents (section 3) for an "EOCEP practice" constraint mode.
5. Polish: export (DOCX/PDF) beyond browser print, question tagging, backups on a schedule.

## 6. Useful facts for whoever resumes this
- Repo: `/home/brandon/apps/science-bank` on the homelab (git; branch `claude/amazing-cray-apalq2`).
  Other services on this host already use ports 80/443/3000/8000/8123/…; the app defaults to 8420.
- Source PDFs (original authoring machine): `C:\Users\howellbj\OneDrive - charlestoncpw.com\Documents\Nina's question thing\`
- SC standards versioning: SCDE republishes Performance Targets ~yearly. Add a new
  `data/standards/SC/<year>/` folder rather than editing the old one; the importer creates new course
  and standard rows for the new year and old questions keep pointing at the version they were built
  against.
- The user's standing preferences: work incrementally, validate each JSON file after writing it,
  keep `sources.json` and the README in sync with what has actually been ingested.
