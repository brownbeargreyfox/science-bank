# Coverage grid design

Date: 2026-10-02
Status: Design approved in chat (Brandon, 2026-10-02, with one addition: the endpoint returns the resolved scope).
Written spec awaiting review. Workstream B of `docs/superpowers/plans/2026-09-30-nina-feedback-roadmap.md`.

## Purpose

Answer "which standards have I **assessed** this year, and where are the gaps?" for one course, grouped by SCDE
bundle. The grid reports assessment activity and bank readiness. It does not report whether a standard was taught,
covered, or mastered, and the page says so. No verdict language anywhere (no "covered", "mastered", "gap", "behind").

## Decisions

1. **Time scope.** A school-year filter. Default is the current school year, **Aug 1 to Jul 31**. "All time" is an
   explicit choice, never a silent fallback.
2. **Visibility.** Administration figures use `visible_clauses(user)` exactly as `/api/results/summary` does: not
   soft-deleted, and the user's own unless admin or power. No new access rule.
3. **Scope is server-resolved.** The endpoint returns the resolved date range and a year label. The UI displays them
   and never computes or restates the range itself.
4. **No migration.** Read-only over existing tables.

## Endpoint

`GET /api/coverage?course_id=<int>&year=<int|"all">` (authenticated; `course_id` required).

- `year` omitted: the current school year, from the server date. An integer is the school-year start (2026 means
  2026-08-01 to 2027-07-31 inclusive). `all` means no date filter. Anything else is a 422.
- Unknown `course_id` is 404 (same helper the standards routes use).

Response `CoveragePage`:

```text
scope:            { kind: "school_year" | "all_time",
                    year: int | null,                 # start year; null for all_time
                    label: str,                       # "2026-27 school year" | "All time"
                    start: date | null, end: date | null }   # inclusive; null for all_time
available_years:  [int]            # school-year starts with at least one visible administration, newest first;
                                   # always includes the resolved year if kind is school_year
course:           { id, name }
groups:           [ CoverageGroup ]       # bundle order (sort_order), then "Other standards" last if non-empty
summary:          { standards_total, standards_assessed }   # distinct standards across the page
```

`CoverageGroup`: `{ bundle_id: int | null, name: str, assessed: int, total: int, standards: [CoverageStandard] }`
(`bundle_id` null for "Other standards"). `assessed` and `total` count the group's standards.

`CoverageStandard`:

```text
standard_id, code, expectation (short), domain_code,
partial: bool                     # BundleStandard.partial; false in "Other standards"
also_in: [str]                    # names of the other bundles containing it (empty if one)
families: [str]                   # generator keys (same source as StandardSummary.families)
questions: { generated, reviewed, approved, rejected, archived }   # all five statuses, ints
times_assessed: int               # distinct visible administrations in scope that include this standard
last_assessed: date | null
correct: int, attempted: int
accuracy: float | null            # null when attempted = 0 (shared accuracy() helper)
limited_responses: bool           # shared limited_responses() helper
```

Rules:

- `questions` counts every question of the standard, variants included, **department-wide** (the bank is broadly
  viewable, matching the question list). Counts are not date-scoped.
- `times_assessed` / `last_assessed` / `correct` / `attempted` come from `AdministrationItem` joined to
  `Administration` with `visible_clauses(user)` plus the date range on `Administration.administered_on`, grouped by
  the question's `standard_id`. `times_assessed` is `count(distinct Administration.id)`.
- A standard "assessed" in scope means `times_assessed > 0`. It does not require results to be entered.
- A standard in several bundles appears under each, with `also_in` set. `summary` counts it once.
- Standards in no bundle go in the "Other standards" group.
- `accuracy` is computed from the summed counts, never an average of averages. Blank is never zero.
- Ordering: bundles by `sort_order`; standards by `BundleStandard.position` (Other: `Standard.sort_order`).
- School-year helper is a pure function in `services/coverage.py` (`school_year_for(date) -> int`,
  `school_year_range(year) -> (date, date)`, label formatting) with its own unit tests, so the boundary is tested
  without a database.

## Page

`/coverage` (`frontend/src/pages/Coverage.tsx`), linked from the rail (new icon in `navIcons.tsx`) and from the
Overview coverage strip.

- Header: title "Coverage", a **course** switcher and a **school year** select (the available years plus "All time").
  Selection lives in the URL (`?course=&year=`) so it can be linked and survives refresh. The scope line under the
  header is the server's `scope.label` plus the server's start and end dates; the UI computes nothing.
- Standing note under the scope line: "This shows what you have assessed, not what has been taught."
- One section per group: heading, progress line ("4 of 6 standards assessed in 2026-27 school year"), then a table.
  Columns: Standard (code link to the standard page, expectation), Questions in bank (counts by status, zeros
  shown as 0 because a count of none is a real count), Times assessed, Last assessed, Accuracy, and an action.
- Status text beside a standard: "Not assessed in this period" (times_assessed = 0), "No questions in bank"
  (all five counts zero), "No question generator yet" (families empty), "Limited response count" (attempted 1 to 9),
  "Partially addressed" (the existing badge), "Also in <bundle>". Accuracy shows `—` when null.
- Action: filled **Generate** when a generator exists (deep link as on the Bundles page, with `bundle` set when the
  group has one), outlined **View** otherwise (same screen-reader wording as the Bundles page).
- Responsive to 360px without horizontal page scroll (tables become stacked rows below the md breakpoint). Prints
  cleanly (rail and top bar hidden by the existing print rules).
- Empty course (no standards) shows an empty state; a year with no administrations still renders every standard as
  "Not assessed in this period".
- Uses existing UI primitives (`ErrorNotice`, loading state, tokens). No new state library, no new dependencies.

## Out of scope

Pacing calendar, per-teacher breakdowns, CSV or print export beyond the browser print, trend charts, and any
"recommended next" logic. Each can follow if Nina asks.

## Testing

Backend (`backend/tests/test_coverage.py`, Postgres):

- Access matrix: a regular teacher sees only their own administrations' figures; admin and power see all; both see
  the same department-wide question counts. Output for a regular user equals the same figures that
  `/api/results/summary` aggregates for that user.
- School-year boundaries: administrations on Jul 31 and Aug 1 land in different years; `year=all` includes both;
  default year follows the server date (patched clock); invalid `year` is 422; unknown course 404.
- Soft-deleted administrations are excluded; soft-deleted assessments still count (spec of results feature).
- Null versus zero: no results entered gives `accuracy: null`; 0 of 30 gives `0.0`; 5 attempted is
  `limited_responses`.
- A standard in two bundles appears in both with correct `also_in`, counted once in `summary`; a standard in no
  bundle appears under "Other standards"; empty "Other standards" is omitted.
- `scope` fields: label, start, end, kind for a year and for all time; `available_years` lists only years with a
  visible administration plus the resolved year.
- Question counts include all five statuses and are not date-scoped.
- Unit tests for the school-year helper (leap day, Jul 31, Aug 1, year label "2026-27").
- `tests/test_permissions.py` policy matrix: the route is read-only, so it must not require a mutating entry; the
  existing guard test must still pass.

Frontend: `npx tsc -b`, `npm run lint`, `npm run build`, then a headless-browser pass against a scratch stack at
1440, 1024, 768, and 360px: no horizontal overflow, scope line matches the API response, switching course and year
updates the URL and data, a year with no administrations, print output, keyboard reach to the selects and action
buttons.

## Files

Claude (backend and docs): `backend/app/api/coverage.py`, `backend/app/services/coverage.py`, schemas in
`backend/app/schemas/`, router registration, `backend/tests/test_coverage.py`, `HANDOFF.md`, regenerated
`frontend/openapi.json` and `frontend/src/api/schema.d.ts`.

Frontend: `frontend/src/pages/Coverage.tsx`, `frontend/src/main.tsx` (route), `frontend/src/components/Layout.tsx` and
`navIcons.tsx` (rail item), Overview strip link. Per the working agreement this can go to Codex in its own worktree
once the API types are regenerated; otherwise Claude builds it.

## Open items

None blocking. Wording of the standing note and status strings may be adjusted after Nina sees it.
