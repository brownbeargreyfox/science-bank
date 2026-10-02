# Codex handoff: landing dashboard and standard-to-Generate flow (Workstream A)

> **Updated 2026-10-02 (PR #6).** After seeing the first build, Brandon asked for a trimmed overview and the Azure look
> everywhere. The overview is now a 30,000-foot view (summary tiles, compact bundle tiles, no per-standard buttons), the
> standard buttons live on the Bundles page, the Question families widget was dropped, and the shell (blue top bar,
> expanding icon rail, Fluent icons) and palette changed app-wide. The text below is the original brief and is kept
> for history; see `HANDOFF.md` ("Frontend look and shell") for what shipped.

Frontend only. Claude does not change `backend/`, and neither do you. Approved by Brandon on 2026-09-30:
the **Azure DevOps dashboard style** (a grid of widgets) for the new landing page, and the flow below.

## Goal

A teacher signs in and lands on an **Overview** dashboard for one course. Its centrepiece is the **Bundles** widget.
Each standard in a bundle is a button: if the standard has a question generator it opens the **Generate** page already
filled in; if it has none it opens that standard's page and says so. The Generate page then suggests the other
standards in the same bundle and domain.

Why: Nina (the teacher) asked for "Home page is bundles; click a standard and go to build a quiz, with suggestions
from other bundled standards", and wants the front page to look good. Most Biology standards have **no generator yet**
(Biology 1: 2 of 14; Biology 2: 0 of 12), so the no-generator path must be a first-class, honest state, not an error.

## Working rules (same as the last two rounds)

- Work in the worktree Claude created for you: `/home/brandon/apps/science-bank-codex-landing` (branch
  `codex/landing-dashboard`, currently identical to `main`). Do not reuse `../science-bank-codex` (it hosts an older
  branch) or `../science-bank-codex-review`. If you ever need another, use a new path, e.g.
  `git worktree add ../science-bank-codex-<topic> -b codex/<topic> main`.
- You own `frontend/**` only. Do not edit `backend/`, `docs/`, `HANDOFF.md`, or `ops/`. Do not regenerate API types
  (no backend change is needed; if you think one is, stop and say why).
- Do **not** deploy, push, merge, or touch `main`. Claude reviews, merges, and deploys.
- Throwaway Postgres for running the app: port **54333** (Claude uses 54332). Check `docker ps`; never stop or reuse
  a container you did not start. Never point anything at the production stack (`127.0.0.1:8420`, the live DB).
- Do not read or search for secrets (`.env`, key files, `ops/backup` material). Nothing here needs them.
- Checks before every commit, from `frontend/`: `npx tsc -b`, `npm run lint`, `npm run build`. All clean.
- Use `ConfirmDialog` (`frontend/src/components/ui.tsx`) for any confirmation; never `window.confirm`.
- Match the surrounding code: react-query hooks in `api/queries.ts` (no new dependencies, and no state library), `unwrap(api.GET(...))`, Tailwind utilities and the
  existing `panel` / `btn` / `field-label` / `input` classes, `Section`, `Notice`, `ErrorNotice`, `Loading`, `Empty`,
  `CodeTag` from `components/ui.tsx`. No new dependencies. No new test framework.

## Read first

1. `frontend/src/pages/Home.tsx` (what the landing page does today; you are replacing it)
2. `frontend/src/pages/Bundles.tsx` (bundle data and how standards link today)
3. `frontend/src/pages/Generate.tsx` (deep-link params: `standard`, `family`, `course`; family auto-select)
4. `frontend/src/pages/StandardDetail.tsx`, `frontend/src/pages/ResultsPage.tsx`, `frontend/src/components/Layout.tsx`
5. `frontend/src/api/queries.ts`, `frontend/src/api/types.ts`, `frontend/src/lib/results.ts`, `frontend/src/lib/format.ts`
6. `docs/superpowers/plans/2026-09-30-nina-feedback-roadmap.md` (context and what is out of scope)

## Decisions already made (do not re-open)

- **Keep the existing app shell and palette.** The current left sidebar, Atkinson Hyperlegible, and the petrol
  accent stay. The dashboard look comes from the widget grid, not from a new top bar or colour scheme. (A shell
  restyle is a separate, later phase; see Out of scope.)
- **`/` becomes the Overview dashboard.** It replaces `Home.tsx`. `/bundles` keeps working unchanged (other pages link
  to `/bundles?course=<id>#bundle-<id>`).
- **One course at a time**, chosen by a course select (default: the first course), remembered in `?course=<id>`.
- **No new state library.** No Zustand, Redux, Jotai, or React context. Server data stays in react-query (one hook per
  widget), and the selected course and bundle live in the URL (`?course=`, `?bundle=`), as `Bundles.tsx` and
  `Generate.tsx` already do. Everything else is local `useState`. If you believe shared client state is unavoidable,
  stop and say why instead of adding a dependency.
- **Widgets load independently.** One failing or empty widget never blanks the page.
- **No arranging, editing, tabs, "…" menus, favourites, or per-user layouts.** Fixed layout.

## Layout

Two columns from 1024px up, one column below. The Bundles widget spans both columns.

```
┌ Overview ───────────────────────────────────── [Course: Biology 1 ▾] ─ [Generate questions] [New assessment] ┐
│ ┌ Bundles ───────────────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Changes in populations over time        ▓▓▓░░░░░░  2 of 6 ready to generate              [Open]         │ │
│ │   [B-LS2-1 · Generate] [B-LS3-3 · Generate] [B-LS1-1 · View] [B-LS4-2 · View] ...                       │ │
│ │ Ecosystem interactions and dynamics     ▓▓▓▓▓░░░░  1 of 2 ready to generate              [Open]         │ │
│ │   [B-LS2-1 · Generate] [B-LS2-7 · View]                                                                 │ │
│ └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ Recent assessments ───────────┐  ┌ Question bank ────────────────┐                                       │
│ ┌ Standards coverage ───────────┐  ┌ Results: review these first ──┐                                       │
│ ┌ Question families ─────────────────────────────────────────────────┐                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Order on narrow screens: Bundles, Recent assessments, Question bank, Standards coverage, Results, Question families.

## Widgets and their data (all existing endpoints)

| Widget | Source | Content |
|---|---|---|
| **Bundles** | `GET /api/bundles?course_id` (as `Bundles.tsx`), `useFamilies()` | One row per bundle: name (link to `/bundles?course=<id>#bundle-<bundleId>`), a progress bar and text `N of M ready to generate`, an **Open** link to the same place, and below it one **standard button** per aligned standard (below). "Ready" = the standard appears in some family's `bindings[].standard_ids`. Keep the existing "Partially addressed" badge on partial alignments. |
| **Recent assessments** | `useAssessments()` | Up to 5 by `updated_at` desc, each linking to `/assessments/<id>` with relative date. Footer link "All assessments". Empty text: "No assessments yet. Create one from reviewed questions." |
| **Question bank** | `useQuestions({course_id, page: 1, page_size: 1})` → `status_counts` | A tile per status (Generated, Reviewed, Approved, Rejected, Archived) linking to `/questions?status=<s>&course=<id>`. Keep the existing line "Review the N generated questions before adding them to an assessment." |
| **Standards coverage** | `useStandards({course_id})`, and `GET /api/results/summary?course_id=<id>&limit=200` (as `ResultsPage.tsx`) | One stacked bar and a three-line legend: **Used in a recorded assessment** (distinct `standard_id` in the summary rows), **Has a question generator** (`families.length > 0`), **Neither**. Show counts as `n of N`. Add a note under it: "Used means a teacher recorded results for it." Empty `used` is normal. |
| **Results: review these first** | same summary query | The first 3 rows with a non-null `accuracy` (the API already sorts lowest first). Each: stem (truncated), `standard_code`, accuracy via `accuracyText`, and the "Limited response count" tag when `limitedResponses(attempted)`. Link each to `/questions/<question_id>`. Footer "All results". Empty text: "Record a use from an assessment page, then enter results." No verdict or mastery language. |
| **Question families** | `useFamilies()`, `useCourses()` | Move the existing "Question families" content from `Home.tsx` here unchanged in behaviour (title, standard code and course, version, "Generate from this family" link), scoped to families bound to the selected course. |

Header actions: **Generate questions** → `/generate?course=<id>`; **New assessment** → `/assessments`.

## Tasks

### A1. Route, nav, and the new page shell
- Files: `src/main.tsx`, `src/components/Layout.tsx`, new `src/pages/Overview.tsx`.
- `/` renders `OverviewPage`. Nav item label becomes **Overview** (still `/`, `end: true`). Keep **Bundles** in the nav.
- Course select + header actions as above; reuse the select pattern from `Bundles.tsx`.
- Do not delete `Home.tsx` until A6.

### A2. Widget components
- New `src/components/dashboard/` with one component per widget and a small `Widget` wrapper (a `<section
  aria-labelledby>` with a header row and body; header title bold ~15px, hairline under it, `panel` look, small radius).
- Each widget owns its own query state: loading (`Loading`), error (`ErrorNotice`, scoped to that widget), empty.

### A3. The standard button (Bundles widget)
- For each aligned standard in a bundle:
  - **Has a generator:** a primary-style button, text `<code> · Generate`, links to
    `/generate?standard=<standardId>&family=<firstFamilyKey>&bundle=<bundleId>`. Accessible name:
    "Generate questions for <code>". If several families are bound, link without `family` so the Generate page's
    existing picker handles it.
  - **No generator:** an outline button, text `<code> · View`, links to `/standards/<standardId>`, with a visible
    secondary label or tooltip "No question generator yet" (not colour alone). Accessible name:
    "View <code> (no question generator yet)".
- Show the standard's short performance expectation as a `title`/tooltip. Do not truncate the code.
- A standard that appears in several bundles is fine; each button carries its own `bundle` id.

### A4. Suggestions on the Generate page
- File: `src/pages/Generate.tsx` (plus a small new component, e.g. `src/components/StandardSuggestions.tsx`).
- Shown only when a `standard` is selected. Reads optional `?bundle=<id>`.
- **Also in this bundle:** siblings from the bundle named by `?bundle` (via `/api/bundles?course_id`), otherwise from
  the first entry of the standard's `bundles` (`useStandard`). Exclude the current standard.
- **Same domain:** `useStandards({course_id, domain: standard.domain_code})`, excluding the current standard and
  anything already listed above.
- Each row: code, expectation shortened to about 110 characters, and either **Generate** (same deep link as A3, keeping
  `bundle`) or **No generator yet** (link to the standard page). Omit empty groups. A course with no bundles shows only
  the domain group. Place it in an aside on wide screens and below the form on narrow ones. Must not change any
  existing Generate behaviour or its URL parameters.

### A5. Keep existing links alive
- `/bundles?course=<id>#bundle-<id>` must still scroll to the bundle (it does today; do not break it).
- Every link that pointed at `/` for "Home" still works. Update copy that says "Home" if any.

### A6. Remove `Home.tsx` last
- Before deleting, list every link and behaviour `Home.tsx` offers and tick each off against the new page (question
  bank tiles and the "Review the N generated questions" link, recent assessments, question families, the header
  actions). Report that list. Delete `src/pages/Home.tsx` and its import only when all are covered.

## Visual and UX spec

- **Tokens:** existing ones only (`petrol` accent, `line` / `line-soft` borders, `muted`, `paper`, `surface`).
  Widgets are white `panel`s on the existing page background, 12px gaps, ~16px body padding, 2 to 4px radius.
- **Progress bar:** 6px tall, `line-soft` track, petrol fill, with `role="progressbar"`, `aria-valuenow/min/max`, and a
  text label next to it. Never rely on the bar or its colour alone.
- **Buttons:** reuse `.btn`, `.btn-primary`, `.btn-sm`. Generate = primary; View = default outline. Only standards
  with a generator are filled, so the filled buttons mean something. A bundle with many standards must stay readable
  (buttons wrap, consistent height).
- **Responsive:** two columns at `lg` and up, one below; no horizontal scroll at 360px wide; buttons wrap.
- **Accessibility:** each widget is a labelled `<section>`; heading order is `h1` (page) then `h2` (widgets);
  everything reachable and operable by keyboard with the existing focus ring; text contrast at least AA; links are
  distinguishable without colour.
- **Wording:** sentence case; no "successfully", "please", or "!"; verbs first on buttons; no mastery or verdict
  language ("Limited response count", never "few responses"); blank is not zero.
- **Numbers:** accuracy only through `accuracyText`; counts as plain integers.

## Edge cases to handle explicitly

- Course with **no bundles** (empty state, other widgets still work).
- Bundle whose standards all lack generators (`0 of N ready`, bar empty, all buttons are View).
- Standard with **several** families; standard in **several** bundles.
- **No recorded results** (coverage "used" = 0; results widget shows its empty text).
- **No assessments**; **no questions** (zero tiles still render).
- A widget's request **fails** (only that widget shows `ErrorNotice`).
- `?course=` pointing at an unknown id (fall back to the first course).
- Very long bundle or standard text (wrap, never overflow).
- A regular teacher vs a power/admin user: the dashboard shows what the API returns for that user; do not add
  role-specific code.

## Verification (record every result in your report)

1. `npx tsc -b`, `npm run lint`, `npm run build` from `frontend/`: paste the output.
2. Run the app locally (see `README.md` "Local development"): throwaway Postgres on **54333**, then from
   `backend/`: `DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54333/sb .venv/bin/alembic upgrade head`,
   `... .venv/bin/python -m app.cli bootstrap`, `... .venv/bin/python -m app.cli set-password --username <name>`,
   `... .venv/bin/uvicorn app.main:app --port 8791`; then from `frontend/`:
   `API_PROXY_TARGET=http://127.0.0.1:8791 npm run dev`. Stop and remove everything you started afterwards.
3. Manual walkthrough (there is no frontend test runner):
   - Sign in; you land on Overview for the first course. Switch to **Biology 1**: bundles listed with correct
     `N of M ready` (B-LS2-1 and B-LS3-3 are the two Biology 1 standards with a generator).
   - Click a **Generate** standard button: lands on `/generate` with the standard and family filled in and the
     bundle's suggestions shown. Click a suggestion; confirm it works.
   - Click a **View** standard button: lands on the standard page; the "No question generator yet" wording was visible
     before clicking.
   - Switch to **Biology 2** (0 generators) and **Chemistry**: both render; Biology 2 is all View.
   - Visit `/bundles?course=<id>#bundle-<id>`: still scrolls to that bundle. `/standards/<id>`, `/questions`,
     `/assessments`, `/results` unchanged.
   - Create an assessment, add a question, record a use with results: the Results and Coverage widgets reflect it
     after a reload.
   - Keyboard-only pass (Tab order, focus ring, every button operable); a 360px-wide viewport; browser zoom 200%.
   - Course select deep link: `/?course=<id>` and an invalid id.
4. Report anything you could not verify and why.

## Out of scope (do not start)

App shell restyle (top bar, icon rail, colour scheme), arrangeable or per-user widgets, tabs, the "…" widget menus,
a favourite star, any backend or API change, the coverage grid page (Workstream B), the Word study aid (Workstream C),
resource links, ELA alignment, PDF import.

## Report back

What changed (files), the exact `tsc`/`lint`/`build` output, the `Home.tsx` parity list from A6, each walkthrough
step's result, screenshots at desktop and 360px if you can take them, and anything you could not verify. Do not
push or merge.
