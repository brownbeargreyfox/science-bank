# Science Bank — Project Status & Handoff

Last updated: 2026-09-22. Written so a fresh Claude session (or Nina, or Codex) can pick this up
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

None of the above blocks starting the app skeleton. They can be ingested incrementally later,
same pattern as the files already done (read PDF → structure into JSON → validate → update
`sources.json` + README).

## 4. What's next: the app skeleton (not yet started)

This is genuinely unstarted — no `frontend/`, `backend/`, `docker-compose.yml`, or any code
exists yet. Everything below is a plan, not a status report.

### 4.1 Target repo layout
```
science-bank/
├── frontend/
│   ├── src/
│   └── Dockerfile
├── backend/
│   ├── app/
│   │   ├── api/            <- FastAPI routers
│   │   ├── models/         <- SQLAlchemy models
│   │   ├── schemas/        <- Pydantic schemas
│   │   ├── services/       <- question-family engine, business logic
│   │   ├── standards/      <- importer that loads data/standards/**/*.json into Postgres
│   │   └── main.py
│   └── Dockerfile
├── data/
│   └── standards/          <- DONE, see section 3 above
├── postgres/
├── docker-compose.yml
├── .env.example
└── README.md
```

### 4.2 Database schema (core tables, from the original brief — not yet built)
```
courses
standards            <- populated from data/standards/**/*.json via an importer script
standard_topics
bundles              <- populated from *-bundles.json

stimuli
questions
question_choices
question_versions     <- version history; editing a question creates a new version, never
                          destroys the original

assessments
assessment_items

question_families      <- NEW concept vs. original brief: defines a deterministic generator
                          (e.g. "population-growth-graph") and which standard(s)/topics it can
                          satisfy
question_family_runs   <- NEW: records of a specific generation (parameters used, seed) so a
                          teacher can regenerate/vary a set deterministically
```

No `generation_jobs` / `ai_reviews` tables from the original AI-centric brief — those belonged to
the rejected LLM-writer design. Only add them back if the AI-generation decision is explicitly
reversed later.

### 4.3 The question-family engine (the actual hard/interesting part)
This is a deterministic content generator, not a template-filler with random numbers only — it
needs to produce **scientifically valid** variations. Concretely, for each `question_family`:
- A parameter space (e.g. for a carrying-capacity dataset: species name, starting population,
  growth pattern shape, units) that stays within realistic/plausible bounds
- A dataset/stimulus renderer (table or graph)
- A question template bank tied to the dataset (e.g. "what relationship is shown between X and
  Y", "predict the value at time Z") with DOK-appropriate phrasing pulled from the standard's own
  `observable_performances` language, not an invented DOK label
- An answer-key generator computed from the same parameters (not a second guess)

Suggested first families to build (from `question_family_candidate: true` flags already set in
the data):
- **B-LS2-1** (Biology 1) — carrying capacity / population growth data table + graph interpretation
- **B-LS3-3** (Biology 1) — Punnett square / trait distribution and probability
- One Chemistry family, e.g. **C-PS1-5** (reaction rate vs. temperature/concentration) or
  **C-PS1-7** (stoichiometry/mole conversion)

Pick 2-3 for the true "small set first" MVP per the scope decision in section 2.

### 4.4 Phased build order (adapted from original brief, Phase numbering kept for continuity)
- **Phase 1 — Foundation**: Docker Compose skeleton, React+Vite+TS+Tailwind shell, FastAPI shell,
  Postgres, Alembic migrations, health endpoints, local auth (single-teacher account is fine for
  MVP — Nina is the only user).
- **Phase 2 — Standards**: DB schema for courses/standards/bundles, the importer script that
  loads `data/standards/**/*.json` into Postgres, a standards browser/search UI.
- **Phase 3 — Question Bank**: CRUD for questions/choices/stimuli, question editor UI,
  `question_versions` history, filtering by course/standard/DOK/type.
- **Phase 4 — Question-family engine**: build the 2-3 MVP families from 4.3, wire them to a
  "Generate Question Set" UI flow (course → standard → DOK → format → stimulus → quantity →
  generate), save generated output into the question bank as `status: generated`.
- **Phase 5 — Review workflow**: question status states (Generated → Reviewed → Approved →
  Rejected → Archived), a review queue UI. No AI quality-check pass — that was part of the
  rejected AI-writer design.
- **Phase 6 — Assessments**: Assessment Builder (assemble questions/stimulus sets into a named
  assessment), DOK distribution + standards coverage display, print-friendly Teacher (with
  answers) and Student (without) views.
- **Phase 7 — Polish**: responsive UI, backups, import/export, settings.

### 4.5 Immediate next action recommendation
Start Phase 1: scaffold the repo layout in 4.1, get a `docker-compose.yml` with `frontend`,
`backend`, `postgres` services running with health checks, then build the Phase 2 standards
importer against the JSON already sitting in `data/standards/` — that's the fastest path to
something visibly real (a standards browser) built on top of the finished data layer.

## 5. Useful facts for whoever resumes this

- Repo root: `C:\Users\howellbj\OneDrive - charlestoncpw.com\Documents\science-bank\` (not a git
  repo yet as of this writing — check before assuming `git status` works).
- Source PDFs: `C:\Users\howellbj\OneDrive - charlestoncpw.com\Documents\Nina's question thing\`
- This machine's PDF tooling: `pdftoppm`/poppler is **not installed**, so the Read tool's `pages`
  parameter (page-range rendering) fails on large PDFs. Reading a whole PDF without `pages` still
  works and is what was used throughout — just expect large token usage for big source PDFs
  (some of the untouched ones, like ESC633_GRHS_BIOL_IS_SAMP.pdf, are 1.8MB+ and may need
  chunked/careful reading).
- SC standards versioning: SCDE republishes Performance Targets ~yearly (most recent: July 2026,
  "for use 2026-2027"). The data layer is already structured to add a new year folder under
  `data/standards/SC/` without touching the current one — see the "Updating" section of
  `data/standards/README.md`.
- The user's standing preference from this session: work incrementally, validate each JSON file
  after writing it, keep `sources.json` and the README in sync with what's actually been
  ingested — don't let the manifest drift from reality.
