# Results Tracking and Linked Variants — Design

Date: 2026-09-29
Status: Proposed (revised after whiteboard review), pending review

## Goal

Close the teacher loop Nina described: give a saved assessment, enter how each section did on each
question, see which questions were missed, and get a newly generated item from the same family and
template without repeating the exact question. Sources: the consolidated Codex handoff of 2026-09-26
(Nina's transcript requests at 00:03–00:47, 01:53–03:08, 05:33–07:00, 11:24–12:15) and the gap assessment
of 2026-09-29.

Nina is a department head over Biology 1, Biology 2 and Chemistry, so this is shared platform
infrastructure, not a per-standard feature: every future family inherits usage history, per-section
results, version-safe interpretation, and a path to fresh practice. Coverage of more standards runs in
parallel (see `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`) and is not a prerequisite.

Two features share this spec because the review step feeds the practice step, but they are independent in
code: **results tracking** and **linked variants**. Either can be built and tested alone.

## Non-goals

- Canvas/QTI export, new question types (multiple-select, dropdown, drag-and-drop), cumulative test
  builder, ELA links, real-data stimuli, results file import. Separate slices.
- Student names, IDs, or per-student records; a roster or `students_tested` field. Results are per-section
  totals only, and the app cannot check totals against class size.
- Partial credit and multipart scoring. "Correct" means students earning full credit; stated in the UI and
  to be defined before it is ever extended.
- Any mastery level, verdict, or claim that a percentage identifies a misconception or a cause.
- Any claim that a variant is equivalent in difficulty, interchangeable, or diagnostically comparable.
- Variants of bundle-family questions (`chemical-system-stability`) in v1 — see Variants.
- LLM-generated content. Variants come from the existing deterministic engine only.

## Access rule

Existing policy: `core/policy.py` `can_modify(user, owner_id)` is true for the owner or a moderator
(`admin`, `power`). Assessments are viewable by every signed-in user, so any teacher can give a colleague's
assessment to their own classes. An administration is therefore **owned by the user who records it** (the
assessment's owner is irrelevant to ownership), and recording requires only that the user can view the
assessment. Results reuse `can_modify` for both viewing and editing:

- A **regular** teacher sees and manages only their own administrations, results, and usage totals.
- A **power user or admin** sees and manages all of them (department-wide, matching Nina's role).
- **Question text stays broadly viewable** as it is today. Anything derived from results — usage counts,
  `times_used`, `last_used`, accuracy, the usage panel, the summary — is filtered to the administrations the
  viewer may see. A teacher can see that a question exists without seeing another teacher's class numbers.
- A response never reveals that a hidden administration exists (no counts that include it).

## Data model (migration 0005, with a working downgrade)

| Table | Purpose | Key columns |
|---|---|---|
| `administrations` | An assessment actually given | `id`, `assessment_id` FK, `label`, `administered_on` date, `notes`, `owner_id` FK users, `created_at`, `updated_at`, `deleted_at` (soft delete, as assessments) |
| `administration_items` | Snapshot of the assessment's items when the use was recorded | `id`, `administration_id` FK cascade, `source_assessment_item_id` (plain integer, no cascading FK, so removing an item from the assessment later cannot erase the record), `question_id` FK, `question_version_id` FK, `position`; unique (`administration_id`, `position`) |
| `administration_sections` | Groups tested, e.g. "Period 2" | `id`, `administration_id` FK cascade, `name`; unique (`administration_id`, `name`) |
| `item_results` | Totals for one section on one item | `id`, `section_id` FK cascade, `administration_item_id` FK cascade, `correct`, `attempted`, `note`; unique (`section_id`, `administration_item_id`); check `attempted >= 1` and `0 <= correct <= attempted` |
| `questions.variant_of_id` | Parent link (new nullable column) | self-referencing FK, indexed |

Rules:

- **No row in `item_results` means no data.** Never treated as 0. Accuracy is `null` with no attempts; an
  item with 0 of 30 is distinctly 0%.
- Accuracy is always computed (`correct / attempted`), never stored. Across sections and across
  administrations it is total correct divided by total attempted.
- The snapshot preserves the assessment's order and exact item identity (assessment item id, question id,
  question version id). Later edits, "refresh", or removal of assessment items do not change it.
- Historical results always point at the exact question version students saw.
- Results work for **every saved assessment item**, whatever its family.

## API

All routes require a login. Writes are audited and covered by the ownership policy (the existing test that
fails on an uncovered mutating route must pass). Hidden or missing records return the existing 404
`Not found`, including administrations the viewer may not access.

### Administrations and results

- `POST /api/assessments/{id}/administrations` — body: `label`, `administered_on`, `notes?`,
  `sections: [name, ...]` (at least one). Rejects an assessment with no items (422). Creates the
  administration and its snapshot in one transaction. Returns the detail.
- `GET /api/assessments/{id}/administrations` — list (filtered by the access rule).
- `GET /api/administrations/{id}` — snapshot items, sections, results, computed accuracy per item (per
  section and overall), and how many items have data.
- `PATCH /api/administrations/{id}` — `label`, `administered_on`, `notes`.
- `POST /api/administrations/{id}/sections`; `PATCH` / `DELETE /api/administrations/{id}/sections/{sid}`
  — add, rename, remove (removal deletes that section's results). At least one section must remain.
- `PUT /api/administrations/{id}/results` — atomic batch upsert of `{section_id, item_id, correct,
  attempted}`. Rejected with 422, saving nothing: duplicate `(section_id, item_id)` rows; any section or
  item id not belonging to this administration; totals that violate `attempted >= 1` and
  `0 <= correct <= attempted`; a row with only one of the two counts null. `{correct: null, attempted:
  null}` clears that row (restores "no data").
- **Locking:** the results batch, section add/rename/delete, and administration edits/deletes all take the
  same row lock on the administration (`SELECT ... FOR UPDATE`) before validating, so a batch cannot
  validate against a section that is removed a moment later.
- `DELETE /api/administrations/{id}` (soft) and `POST /api/administrations/{id}/restore`.

### Review and usage

- `GET /api/results/summary?course_id&standard_id&family_key&limit&offset` — one row per question that
  appears in at least one **visible, non-deleted** administration (including an administration where no
  results are entered yet, which shows `accuracy: null`). Questions never used are not listed. Soft-deleted
  administrations are excluded from summary and usage; restoring one returns it to both. Each row has:
  `attempted`, `correct`, `accuracy` (`null` when no data), `times_used`, `last_used`, plus
  per-administration figures, all computed only over administrations the viewer may see. Sorted lowest
  accuracy first, no-data rows last. `limit` default 50, max 200; returns `total`. No verdict or mastery
  field.
- `GET /api/questions/{id}/usage` — every visible, non-deleted administration the question appeared in, identifying the
  **pinned question version** used in each (not just the current version), with that use's accuracy; plus the
  question's parent and variants (question links are as visible as the questions themselves).

### Variants

Two operations, matching the existing `generate/preview` and `generate/save` pattern.

- `POST /api/questions/variants/preview` — body `{question_ids: [...]}`, at most 20 after removing
  duplicates. **Persists nothing.** The whole request fails (422 malformed body or too many ids; 404 if any
  id does not exist) before any generation. Otherwise it returns 200 with one record per parent:
  `{parent_id, status: "candidate", candidate, candidate_token}` or
  `{parent_id, status: "unavailable", reason}`. A mixed selection therefore yields usable candidates plus
  inline reasons. A 422 for an unavailable parent is used only when the client asked about a single parent.
- `POST /api/questions/variants/save` — body `{tokens: [...]}` only; never client-supplied content, seeds, or
  EOCEP settings. One transaction for the whole batch. Only selected candidates are saved; unselected ones
  never exist in the bank.

Who may create a variant: any user who can view the parent question. The variant is a new question owned by
the person saving it. The parent, its versions, and its results are never modified; provenance and the
audit event record the source.

**Supported parents (v1):** the question row records a `family_key` and `template_key` (engine origin), the
family is still registered, it is an ordinary single-standard family, and the template still exists in the
current family and is bound to the question's standard. Anything else — hand-written or orphaned questions,
retired families or templates, and **bundle-family questions** — is "unavailable" with a plain reason. Bundle
support waits on a proof of concept showing a one-item variant keeps the shared stimulus and per-standard
alignment.

A variant is generated from the **current family code** with a new seed and the parent's saved
`generation_mode`; it never re-derives the parent, so the parent's family version need not match. A
teacher-edited parent is supported: the variant comes from the family template, not the edited wording, and
the UI says so. The variant's own provenance records the family version that produced it. If the family
version changes between preview and save, the token no longer verifies and save returns 409 ("regenerate
this candidate").

`candidate_token` is an HMAC-signed payload (server secret) containing a token id, an expiry (30 minutes),
the requesting user id, parent question id, **parent version id**, seed, and family version. The browser
cannot build or alter it. On save the server verifies signature, expiry and user binding; re-checks the
viewing rule for each parent; re-derives the question through the shared generation service using the
parent's **saved provenance options** (generation mode), never browser input; and re-checks the fingerprint.
There is no consumed-token table: a replay re-derives the same content and collides with the variant the
first save created, returning 409 without creating another. Add stateful one-time tokens only if replay
proves to be a real problem.

Generation:

- The nonce is created only on the server. Candidate seeds are derived from the nonce, parent id and attempt
  number, up to 25 attempts. The generation logic is factored out of `api/generate.py` into a shared service
  so preview and variants call the same code; the existing generate endpoints keep identical behavior.
- **Fingerprint:** `question_type`, whitespace-normalised stem, canonically serialised stimulus, the set of
  (choice text, correct) pairs (labels and order ignored), and answer text with any multiple-choice label
  stripped. A candidate must differ from every version of every question in the root lineage (root, parent,
  all siblings and descendants) and from candidates already accepted in the same preview batch. A different
  scenario with the same correct answer is valid. The fingerprint proves the output differs structurally; it
  says nothing about difficulty or novelty of the idea assessed.
- **Lineage ceiling:** 50 variants per root question; past it preview marks that parent "unavailable" and
  save returns 422. Ancestry and descendant
  lookups use the `variant_of_id` index. Saving locks the root question row so sibling saves serialise.
- A family with a small parameter space can run out of distinct variants; preview then returns an
  "unavailable" record for that parent ("no distinct variant available").
- Saved variant: `variant_of_id` set, status `generated`. Provenance keeps `variant_of`, `parent_version_id`,
  seed and family version. It stays valid if the parent is later edited, archived, or restored.
- Save-time collision (another user saved a fingerprint-identical sibling first, or a replay) returns 409
  with the parent id and a message to regenerate that candidate. Nothing is substituted; the batch rolls
  back.
- One audit event per batch: parent ids, created variant ids, count. No stems or answers.

## UI

- **Assessment detail page:** "Record use" (label, date given, section names, at least one). The app has no
  "finalized" or "printed" state, so it is available for any non-empty assessment the user can view; choosing
  the date given and clicking Record is the teacher's confirmation that it was administered. Also reachable
  from the builder. Lists past uses (only those the viewer may see) linking to results.
- **Results grid (`/administrations/:id`):** frozen items by section columns; each cell has correct and
  attempted inputs with accessible labels such as "Period 2, Question 4, correct". Blank stays "no data" and
  item accuracy shows `—`, never 0%. Overall accuracy and `correct / attempted` update locally while typing
  but persist only on Save. Save is disabled until every filled cell is valid. Sections can be added and
  removed. A note states that "correct" means full credit and partial credit is not supported.
- **Review (`/results`):** filters for course, standard, and family; paginated table lowest accuracy first
  showing `correct / attempted`, times used, last used. **"Limited response count"** shows whenever
  aggregate attempted is under 10, including totals from several sections; it is a display hint, not a
  statistical or quality judgment. A fixed caution says a low percentage does not show why students missed
  a question, and lists things to check: wording and reading load, format, whether it was taught, key or
  ambiguity. No mastery label.
- **Make practice:** tick rows, "Make practice variants" runs the preview and shows each parent beside its
  candidate. The final action is **"Save selected variants"**; unchecked candidates are never persisted.
  Items that cannot have a variant show their "unavailable" reason inline. Copy calls a candidate "a new generated
  item from the same family and template," with results tracked separately from the original's.
- **Question detail:** usage panel (each visible use with date, accuracy, and the pinned version number) and
  links to parent and variants.

## Error handling and concurrency

Route-by-route contract:

| Situation | Response |
|---|---|
| Administration, section, results, or restore on an administration the caller may not access, or that does not exist | 404 `Not found` (so colleagues' administrations cannot be enumerated) |
| Record use on an assessment that does not exist or is deleted | 404 |
| Record use on an empty assessment; invalid results; malformed bodies | 422, nothing saved |
| Variant preview: malformed body, more than 20 ids | 422; an id that does not exist: 404 |
| Variant preview: viewable parent that is unsupported | 200 with an `unavailable` record |
| Variant save: bad signature, expired, wrong user, or family version changed | 422 for bad signature/expired/wrong user; 409 for family version changed |
| Variant save: fingerprint collision or replay | 409 naming the parent; whole batch rolls back |
| Variant save: lineage ceiling reached | 422 |
| Mutating shared content the caller can view but not modify (existing behavior) | 403, unchanged |
- The administration row lock above covers every write to an administration's sections and results.
- The migration downgrade drops the new tables and column; a migration test in the style of
  `test_migration_0003.py` covers upgrade and downgrade.

## Testing

Backend, pure functions first (no database), then database-backed:

- Accuracy: 12 of 30 is 40%; no attempts is `null`; 0 of 30 is 0%; the limited-response flag flips between
  aggregate attempted of 9 and 10, including across sections.
- Fingerprint: a label-only or order-only reshuffle is rejected; a different scenario with the same answer
  is accepted; `question_type` and stimulus changes count.
- Snapshot: ids and order survive later assessment edits, refresh, and item removal; an empty assessment
  returns 422.
- Results: each rejection case (duplicates, foreign items or sections from another administration, bounds,
  half-null pair), null-pair clearing, all-or-nothing on error, section removal deleting only that section's
  results; section mutations and batch updates serialise through the administration lock.
- Access: a regular teacher cannot view or modify another teacher's administration or results, even when
  they can view the underlying question; summary and usage never include hidden totals; power and admin see
  all.
- Summary and usage: pagination and filters; usage lists every pinned version; results stay attached to the
  version used after a question is edited.
- Variants: preview creates no rows and saving only selected tokens creates rows; tampered, expired, and
  other-user tokens are rejected; a replayed token returns 409 and creates nothing; whole-request failures
  happen before any generation and a mixed selection returns candidates plus "unavailable" records; batch cap and duplicate ids; collision returns 409 and rolls back the whole batch;
  the lineage ceiling; parent and its results untouched; a saved variant stays valid after the parent is
  edited, archived, or restored; a bundle-family, hand-written, retired-family, or missing-template parent is "unavailable" with a reason;
  a teacher-edited parent still produces a variant from the family template; a family-version change
  between preview and save returns 409; an EOCEP parent stays
  EOCEP; audit detail contains no stems or answers.
- Policy: every new mutating route is covered by the ownership policy.
- Full backend suite against a throwaway Postgres with zero skips; backend lint.

Frontend: `npm run lint` and `npm run build`. The grid's validation is **manually verified, not
automatically tested**, by a walkthrough before deploy. `playwright` is already a devDependency; if it is
usable for the app, a small smoke test of the grid may be added without introducing a new test runner
(to be checked at plan time, not assumed).

## Decisions to confirm during review

1. Token lifetime of 30 minutes, batch cap of 20, lineage ceiling of 50.
2. "Limited response count" threshold of fewer than 10 aggregate attempts.
3. Any user who can view a question may create a variant that they own (alternative: owner, power, admin
   only).
4. Administration owner = the user who records it (chosen so a teacher can record her own classes on a
   colleague's assessment). The alternative, owner = assessment owner, would stop that teacher from seeing
   her own results and would make a power user recording on someone's behalf the record's owner in name only.
