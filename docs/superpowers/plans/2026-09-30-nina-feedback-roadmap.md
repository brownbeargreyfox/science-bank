# Nina feedback roadmap: landing flow, coverage, and Word study

Date: 2026-09-30
Status: Planning. Workstream A's design is presented and awaiting Brandon's explicit approval; B, C, and E need
their own design or spec before any build. Nothing here is implemented.

## Where this came from

Nina (teacher, Biology and Chemistry) and a coworker gave feedback on 2026-09-29 and 2026-09-30, relayed by
Brandon. What was said, and what was decided:

| Said | Decision |
|---|---|
| Home page should be Bundles. Clicking a standard is a button that opens the build-a-quiz page, with suggestions from other standards in the same bundle or domain. | **Do.** "Build-a-quiz" means the **Generate** page (Nina's answer). Workstream A. |
| Coworker: a standards page with links to activities, online resources, how to teach, testing strategies. | **Parked.** Nina: "put a pin in it"; nobody can vouch for outside links. If revived, use teacher-added, power-user-approved entries inside the app, never scraped or AI-written. |
| Coworker: align to ELA standards. | **Reframed.** Not a new subject. Nina's point: most students read below grade level, so complex vocabulary (often Greek/Latin roots) causes the struggle. She wants a **teaching aid**. Workstream C. |
| Coworker: long-term planning to see how all standards were covered. | **Do, after A.** Workstream B. |
| Coworker: upload a PDF and categorize questions to standards. | **Parked.** Conflicts with the no-LLM-authored-questions decision and PDF parsing is unreliable. Safe first version, if ever: teacher pastes or imports their own questions and picks the standard by hand. |
| Nina: needed for **Biology**, not Chemistry (Chemistry students are honors and above grade level). | Pilot the teaching aid in **Biology 1**. |
| Nina: she will **review the glossary**. | She is the reviewer, not the author (authoring is an open question, below). |

## Facts from the code that shape the plan

- `/api/standards` (`StandardSummary`) already returns `domain_code`, `domain_name`, and `families` (the
  generators bound to that standard), and supports `domain` and `with_family_only` filters. `StandardDetail`
  adds `bundles` (`BundleRef`: id, name, partial). `/api/bundles?course_id=` returns each bundle with its
  aligned standards. **Workstream A therefore needs no backend change.**
- The Generate page already accepts `?standard=<id>&family=<key>` and prefills from it
  (`frontend/src/pages/Generate.tsx`). Standard detail already links there.
- Bundles cards already link each standard code to `/standards/:id` (`frontend/src/pages/Bundles.tsx`). Other
  pages link to `/bundles?course=<id>#bundle-<id>`; those links must keep working.
- **Generator coverage is thin exactly where Nina needs help.** Biology 1: 2 of 14 standards have a generator
  (B-LS2-1, B-LS3-3). Biology 2: 0 of 12. Chemistry: 4 of 12 (C-PS1-2, -5, -7). So "click a standard, generate
  questions" dead-ends for most Biology standards today. Workstream D is the lever for that, and Workstream C
  does not depend on generators at all.
- Biology 1 bundles: 1 Structure and Function of Life, 2 Matter and Energy in Ecosystems, 3 Ecosystem
  Interactions and Dynamics, 4 Inheritance and Variation of Traits, 5 Changes in Populations Over Time,
  6 Common Ancestry and Speciation.

## Workstreams

| | Workstream | Path | Size | Depends on | Suggested owner |
|---|---|---|---|---|---|
| A | Bundles landing + standard button to Generate + suggestions | Bounded (short design approved in chat) | Small, frontend only | none | Codex builds, Claude reviews |
| B | Coverage grid per course (questions, approved, times used, last used, accuracy per standard and bundle) | Architectural (spec first) | Medium: one read endpoint + one page | A (nav), results data already exists | Claude backend, Codex frontend |
| C | Word study teaching aid for Biology 1 (glossary per standard or bundle, printable) | Architectural (spec first) | Medium: data model, editor, review step, printable page | none; content needs Nina | Claude spec + backend, Codex frontend, Nina reviews content |
| D | Biology generators (existing `2026-09-29-coverage-roadmap.md`, Tier A) | Per family, each has its own plan | Large, ongoing | none | Claude engines, Nina's input on units |
| E | Reading-level hint on questions and Results | Small, folds into C's spec | Small | C's word data helps but is not required | with C |

### Recommended order

1. **A now.** Small, unblocks the landing Nina asked for, and makes the dead ends visible.
2. **C spec in parallel with A.** It is the piece Nina most wants for Biology and does not need generators.
3. **D continues in parallel** (next Biology family per the roadmap); it is what makes A's button useful in Biology.
4. **B after A.** Reads the results data already recorded.
5. **E with C.**

## Working agreement (from the last two rounds)

- **Disjoint file sets, one owner each.** Codex: `frontend/**`. Claude: `backend/**`, `docs/**`, `HANDOFF.md`.
  Nobody edits the other's set. Shared surface is only the generated API types (`frontend/openapi.json`,
  `frontend/src/api/schema.d.ts`), regenerated by whoever changes the API.
- **Separate git worktrees.** Codex: `git worktree add ../science-bank-codex -b codex/<topic> main`. Never share
  a checkout.
- **Ports for throwaway Postgres:** Codex 54333, Claude 54332. Check `docker ps`; never stop a container you did
  not start.
- **Codex does not deploy, push, or touch `main`.** Claude merges and deploys, with a tagged rollback image and a
  DB backup for any migration, then records it in `HANDOFF.md`.
- **Checks before every commit:** `npx tsc -b`, `npm run lint`, `npm run build` (from `frontend/`); backend
  `pytest` against a throwaway Postgres for any backend change.
- **Wording is product.** No mastery or verdict language. Blank is not zero. Reading-level output is a hint, not a
  verdict.
- **Confirmations** use `ConfirmDialog` (`frontend/src/components/ui.tsx`), never `window.confirm`.

## Workstream A: task list (bounded; awaiting approval of the design)

Goal: a teacher lands on Bundles, clicks a standard, and lands on Generate for it, with sibling-standard
suggestions. All frontend.

**A1. Route and nav.** `main.tsx`: `/` renders `BundlesPage`; add `/home` for the current `HomePage` (rename its
title "My work"); keep `/bundles` rendering `BundlesPage` so existing `?course=` and `#bundle-<id>` links work.
`Layout.tsx` nav: Bundles (`/`, end) first, then Standards, Generate, Question bank, Assessments, Results, and
"My work" (`/home`); brand link goes to `/`.

**A2. Recent assessments strip.** At the top of `BundlesPage`, the 5 most recently updated assessments
(`useAssessments`, sorted by `updated_at`), each a link to the assessment, plus a "Build an assessment" link.
Hidden when the teacher has none. Reuse the sort and formatting already in `Home.tsx`.

**A3. Standard button.** On each bundle card the standard's code chip becomes a real button-styled link:
- Standard has a generator (`families` non-empty): "Generate questions" to
  `/generate?standard=<id>&family=<key>&bundle=<bundleId>` (first family; if several, the Generate page's
  existing family picker handles it).
- No generator: link to `/standards/<id>` labelled "No question generator yet", visually distinct, so no
  teacher lands on an empty Generate page. Keep the existing "Partially addressed" badge.

**A4. Suggestions on Generate.** When `?standard=` is set, show "Also in this bundle" (siblings from the
originating `?bundle=` if present, otherwise from the standard's `bundles`), then "Same domain" (same
`domain_code`, excluding those already listed and the current standard, from `useStandards({course_id, domain})`).
Each row: code, short expectation, and either "Generate" (deep link) or "No generator yet" (link to the standard
page). Empty groups are omitted. Course without bundles: skip the bundle group, show only domain.

**A5. Verify.** `tsc`, `lint`, `build` clean; then click through against a running app: land on `/`, follow a
Biology 1 bundle to B-LS2-1 (generator) and to B-LS1-1 (none), confirm suggestions, confirm old `/bundles?...#bundle-N`
links still scroll, confirm a course with no bundles still renders. Record each result in the report.

Acceptance: no backend diff; no new API types; the Generate page's existing deep-link behaviour is unchanged.

## Workstream B: outline (needs a spec)

Read endpoint returning, per standard in a course: questions by status, times used, last used, and accuracy
(aggregate over the viewer's visible administrations, same access rules as `/api/results/summary`), grouped by
bundle. One new page, linked from the landing. Open decision: "covered" is *assessed*, not *taught*; say so on
the page. A pacing calendar is out of scope until Nina asks.

## Workstream C: outline (needs a spec)

- Data: a glossary entry (term, word parts with meaning, plain-language definition, example sentence), attached
  to a standard (optionally a bundle), with a review status (draft / reviewed by a power user).
- UI: a teacher-facing "Word study" section on the standard page and a printable handout; a power-user editor
  with a review action.
- Content is human-written and human-reviewed; no AI-authored entries. Pilot content is for one Biology 1 bundle.
- Not now: putting word parts on the student copy of assessments. Nina asked for a teaching aid, not test
  support. If revisited, record whether an administration had support so results stay interpretable.
- E, folded in: a rule-based reading-level estimate per question, shown on Results next to accuracy, labelled as
  a rough hint (readability formulas over-score long science words).

## Decisions needed

1. **Brandon: approve Workstream A's design** (above) so it can be handed to Codex.
2. **Pilot bundle for C.** Suggested Bundle 5, "Changes in Populations Over Time" (B-LS1-1, B-LS2-1, B-LS3-3,
   B-LS4-2, B-LS4-4, B-LS4-5): it contains both existing Biology generators and vocabulary-heavy evolution terms.
   Nina to confirm or pick another.
3. **Who drafts glossary entries.** Nina reviews; someone still has to write the first 10 to 15 terms. Candidates:
   Nina, Brandon, or Claude drafts for Nina's edit. The last is a change to the "human-written" rule and needs an
   explicit yes.
4. **Landing naming.** Keep "Bundles" as the page title on `/`, and rename the dashboard "My work". Confirm with
   Nina.
5. **Order of B versus C** once A ships.
