# Science Bank — Detailed Engineering Handoff

Last updated: 2026-10-04

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
- Working branch: `main` (PR #2 merged as `c24ead0`)
- **Production runs the `52e45c4` build, not a later `main` (2026-10-05).** The Biology 2 B-LS4-3 family
  `trait-distribution-shifts` was merged to `main` as `a9c55ba` (fast-forwarded, no PR, no review) at 23:56 on 2026-10-04 and
  deployed at 00:12 on 2026-10-05. A fresh-context review then found two answer-key defects, and Brandon had it rolled back.
  Production now runs image `83e1f84ba44b` (the 14:05 build of `52e45c4`, tag
  `science-bank-app:pre-trait-distribution-shifts-a9c55ba`, also tagged `latest`): nine families, migration `0005`,
  `/readyz` 200 locally and publicly. The withdrawn build is kept as
  `science-bank-app:withdrawn-trait-distribution-shifts-a9c55ba`. The rollback changed only the app container; the database
  was not touched. No questions or generation runs were ever saved from the family (previews are not audited, so preview use
  is unknown). One inert row remains: `question_families` still lists `trait-distribution-shifts 1.0.0`; the API reads
  families from code, so nothing uses it. **Until the revert PR for `a9c55ba` and `152d389` is merged, `main` still contains
  the family, and rebuilding production from `main` would bring it back.** See "Withdrawn family" below.
- Latest deploy: `52e45c4` (2026-10-04; merge of PR #8, `chore/eocep-cleanup`, no migration; migration remains `0005`):
  tests, docs and EOCEP data wording only. The first B-LS1-1 EOCEP prohibition now quotes the PDF (p. 4) and the
  differentiation requirement is complete; no generated question changed. Verified live: `/readyz` 200 locally and
  publicly, app container healthy, `alembic current` is `0005_results_and_variants`, nine families synced (versions
  unchanged), and the database holds the new B-LS1-1 prohibition text. The importer's startup counter always reports
  EOCEP constraints as "unchanged", so check the database, not the log, after a constraints-only change. Rollback:
  image `science-bank-app:pre-eocep-cleanup-52e45c4`. Deferred and still open (each needs a family version bump):
  `trait-probability` raises a GenerationError at seed `cmp-92` with quantity 40, and "so this is a insertion" in the
  `mutation-effects` identify explanation.
- Earlier deploy: `c27219e` (2026-10-04; merge of `codex/eocep-constraints`, no migration; migration remains `0005`):
  EOCEP constraints and generator enforcement for Biology 1 B-LS1-1, B-LS3-2, and B-LS4-4. B-LS1-1 EOCEP items omit
  3′/5′ strand-end labels and state their reading direction; B-LS3-2 displays its mutation-only scope note in the
  Generate page. Verified live: `/readyz` 200 locally and publicly, app container healthy, migration head
  `0005_results_and_variants`, and startup synced nine families. Not checked live: signed-in EOCEP generation for each
  of the three standards or the B-LS3-2 scope note in the browser. Rollback: image
  `science-bank-app:pre-eocep-c27219e`; no database data or schema changed.
- Latest deploy: `0c47781` (2026-10-03; merge of `feat/natural-selection`, no migration; migration still `0005`): the
  `natural-selection-trend` family for Biology 1 B-LS4-4 (see "Implemented families"). Verified live: `/readyz` 200
  locally and publicly, startup log shows 9 families synced, the database lists `natural-selection-trend 1.0.0`,
  Biology 1 B-LS4-4 is flagged as a family candidate, and the family generates a full six-item set inside the
  container (one generation table that totals 100 per row, one line chart). Not checked live: a signed-in Generate page
  for B-LS4-4 on production and how the line chart renders there with two series, and no questions have been saved from
  the new family. Rollback: image `science-bank-app:pre-natural-selection-0c47781`; nothing in the database changed
  beyond the standards importer's flag update. Any change to this family's output now needs a version bump.
- Earlier deploy: `46e4a36` (2026-10-03; merge of `feat/mutation-effects`, no migration; migration still `0005`): the
  `mutation-effects` family for Biology 1 B-LS3-2 (see "Implemented families"). Verified live: `/readyz` 200 locally and
  publicly, startup log shows 8 families synced, the database lists `mutation-effects 1.0.0`, Biology 1 B-LS3-2 is
  flagged as a family candidate (Biology 2 is not), and the family generates a set inside the container. Not checked
  live: a signed-in Generate page for B-LS3-2 on production, and no questions have been saved from the new family.
  Known design limit: every insertion/deletion item shows a longer changed protein (a frameshift that also ends early
  is excluded by the approved rule); a later family could add truncating frameshifts. Rollback: image
  `science-bank-app:pre-mutation-effects-46e4a36`; nothing in the database changed beyond the standards importer's flag
  update. Any change to this family's output now needs a version bump.
- Earlier deploy: `52126d9` (2026-10-03; merge of `feat/dna-protein-synthesis`, no migration; migration still `0005`):
  the `dna-protein-synthesis` family for Biology 1 B-LS1-1 (see "Implemented families"). Verified live: `/readyz` 200
  locally and publicly, startup log shows 7 families synced, the database lists `dna-protein-synthesis 1.0.0`,
  Biology 1 B-LS1-1 is flagged as a family candidate (Biology 2 is not), and the family generates a set inside the
  container. Not checked live: a signed-in Generate page for B-LS1-1 on production (not exercised in a browser), and
  no questions have been saved from the new family yet. Rollback: image `science-bank-app:pre-dna-protein-52126d9`;
  nothing in the database changed beyond the standards importer's flag update. From here, any change to this
  family's output needs a version bump.
- Earlier deploy: `5e12510` (2026-10-02; merge of `feat/coverage-grid`, no migration; migration still `0005`): the
  coverage grid (`/coverage`, `GET /api/coverage`; see "Coverage grid"). Verified live: `/readyz` 200 locally and
  publicly, the served bundle contains the new page strings, `/api/coverage` returns 401 when signed out, no errors in
  the app log. Not checked live: a signed-in view of the page on production (verified on a scratch stack only), a real
  touch device, Safari and Firefox. Rollback: image `science-bank-app:pre-coverage-grid-5e12510` (the image from before
  this deploy); nothing in the database changed.
- Earlier deploy: `132b82e` (2026-10-02; PR #6, frontend-only, no migration): the Overview dashboard, the standard
  Generate/View buttons on the Bundles page, Related standards on Generate, and the Azure-style look with the
  expanding icon rail everywhere (see "Frontend look and shell"). Verified live: the served assets are the new build
  (new accent colour, rail rules, strings), `/readyz` 200 locally and publicly, migration unchanged at `0005`, and the
  signed-in non-admin session renders the new Overview with real data and no error alerts. Rollback: image
  `science-bank-app:pre-pr6-132b82e` (the image from before this deploy). Not checked live: a real touch device,
  Safari and Firefox.
- Earlier deploy: `9f063c9` (2026-09-29; PR #4, frontend-only: in-page `ConfirmDialog` replaces the two native
  `window.confirm` boxes, for deleting an assessment and removing a section; no migration). Verified live.
  Rollback: image `science-bank-app:pre-pr4-9f063c9` (the image from before this deploy).
- Earlier deploy: `a0669db` (PR #3, frontend-only: strips Pydantic's "Value error, " prefix from validation
  messages). Rollback image `science-bank-app:pre-pr3-a0669db`.
- Live tests of results/variants done 2026-09-29 (browser sessions as `clicktest` regular, `brandon` admin,
  `clicktest2` regular, `Nina` power):
  - Passed as a regular teacher: record-use, grid validation, zero-vs-blank, cross-use aggregation, variants
    (single and multi, lineage distinct), print views, filters.
  - Passed as admin: reads and writes another teacher's administration (ownership unchanged), department-wide
    Results and per-question usage.
  - Passed as a second regular teacher (`clicktest2`): another teacher's administrations return 404 (UI and API
    GET, section add, delete, results PUT), Results, summary and question usage show none of it, and the other
    teacher's assessment is view/print-only. Note the results PUT validates the body before checking ownership,
    so an invalid body gets 422 rather than 404.
  - Signed-token expiry (variant preview tokens, 1800 s TTL): on the deployed code, valid through the expiry
    second and rejected one second later ("This candidate has expired; preview again"); wrong-user, tampered
    payload/signature and malformed tokens are each rejected. Over HTTP as Nina all of these (and a mixed
    batch) return 422 and create nothing. Not seen on screen: the UI expiry message (`ResultsPage` shows save
    errors via `ErrorNotice`, so it should render the server text). The app's API client captures `fetch` at
    startup, so a page-level fetch patch cannot intercept it; a real check needs a preview left over 30 minutes.
  - Variant in an assessment (as Nina): question 13 (variant of 4) added to an assessment, use recorded, results
    saved (V1 4/8, V2 6/10). The variant has its own results (10/18, 1 use, usage lists only its own
    administration) and the original is unchanged (q4 22/40, 2 uses); parent/variants links are correct both
    ways. Rows reference the variant's own question and version.
  - 20-at-a-time cap (read-only, no rows created): preview returns 200 for existing ids, and 422 "Choose at
    most 20 questions at a time" at 21 distinct ids (checked before any lookup, so it beats the 404 for missing
    ids); 20 distinct ids pass the cap (reach the existence check, 404 for missing). Duplicates are removed
    before counting (24 items / 3 distinct is 200). Empty list and >100 ids are schema 422s. Save rejects >20
    tokens with 422 "Save at most 20 variants at a time" (20 pass the cap and fail token validation). UI sets
    `MAX_SELECTION = 20` and disables extra checkboxes (read from code, not exercised: only 4 rows are listed).
    Not proven: a preview of 20 real existing questions returning 200 (the DB has only 13).
  - New dialogs: Escape, backdrop, Cancel and Confirm all behave for both delete-assessment and remove-section.
  - Passed as power (`Nina`): reads and writes another teacher's administrations (results, sections, label),
    edits another teacher's assessment, changes question status (status rules still apply: reviewed cannot go
    back to generated, 409); ownership unchanged; no Admin nav link; `/api/admin/*` returns 403. The dialogs
    appear for another teacher's assessment and administration.
  - Not covered: real mouse clicks on the dialogs (the browser automation dropped clicks, so some steps used
    page-level click handlers), the UI expiry message, and a 20-real-question preview.
  - Test rows still on the live DB, hard delete left to the owner: assessments 1-5, administrations 1-4,
    questions 6-13 (under `clicktest` / `clicktest2` / `Nina`; question 7 is now `reviewed` from the power test; 13 was saved by accident during the token test); `zz-clicktest` is disabled. Open question: an assessment
    soft-delete does not remove its administrations from Results, which matches the spec (only soft-deleted
    administrations are excluded).
- Latest deployed feature commit: `c24ead0` (2026-09-29; PR #2: results recording/review and linked variants;
  migration `0005_results_and_variants`; backend 268 tests on Postgres, Playwright e2e 26/26). Deployed from
  `main`. Rollback needs both: image `science-bank-app:pre-0005-c24ead0` and database backup
  `backups/pre-0005-2026-09-29-2039.sql` (the backup alone does not undo the schema change). The live
  record-use and variants flows have not been click-tested yet; only `/readyz` and the SPA were smoke-tested.
- Earlier deployed feature commit: `0d6756e` (adds the standalone `reaction-outcome` family for
  Chemistry C-PS1-2 and flags C-PS1-2 as a family candidate; no migration). Rollback: image `science-bank-app:pre-reaction-outcome-0d6756e`, database backup
  `backups/pre-reaction-outcome-2026-09-29-1229.sql`.
- Earlier deployed feature commit: `451ef0a` (C-PS1-7 quantitative conservation `1.0.1` chlorine-molar-mass
  correction and the first shared Chemistry bundle generator; migration `0004`). Its previous image is tagged
  `science-bank-app:pre-bundle-451ef0a` for rollback.
- Roles/ownership/audit/admin is live. The deployment backup is
  `backups/pre-0003-2026-09-24-1519.sql`; the previous app image is tagged
  `science-bank-app:pre-0003` for rollback. The branch is pushed to GitHub (PR #1).
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
| `chemical-system-stability` | Chemistry C-PS1-5 + C-PS1-7 | 1.0.0 | One magnesium + hydrochloric-acid shared stimulus: rate evidence and quantitative conservation. |
| `quantitative-conservation` | Chemistry C-PS1-7 | 1.0.1 | Curated reactions, moles/particles/mass as evidence for conservation. |
| `reaction-outcome` | Chemistry C-PS1-2 | 1.0.0 | Curated main-group/combustion reactions: bond type, electrons lost/gained/shared, product formula, same-family reactivity trends. Classroom-only. |
| `dna-protein-synthesis` | Biology 1 B-LS1-1 | 1.0.0 | Template strand to mRNA, mRNA to amino acids with a displayed partial codon table, gene activity across two cell types, and a DOK 3 explanation. Classroom and EOCEP practice (EOCEP items show strands without 3′/5′ and say "read left to right"); no mutation-effect items (those belong to B-LS3-2, which can reuse `CODONS`/`translate`). |
| `mutation-effects` | Biology 1 B-LS3-2 | 1.0.0 | One-nucleotide substitution, insertion, or deletion in a gene: identify it, find the protein from the changed gene with a displayed codon table, describe the effect (frameshift taught explicitly for indels), decide whether it can be inherited, and defend a claim. Classroom and EOCEP practice (EOCEP shows a note that only the mutation part of the standard is covered); meiosis and mutagen-dataset items are a later B-LS3-2 family. |
| `natural-selection-trend` | Biology 1 B-LS4-4 | 1.0.0 | Six fictional cases (beetles, a lab bacterium, finches, marsh hares, minnows, desert shrubs): compare survival rates (with trap cases where counts mislead), read a trait trend across generations of 100 sampled individuals, the effect of an environmental change, explain adaptation as population-level change (not individuals changing because they need to), predict the direction of a reversal, and a DOK 3 data-based explanation. Classroom and EOCEP practice; no allele-frequency calculations. |

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

C-PS1-2 now has the standalone `reaction-outcome` family. The `chemical-system-stability` bundle
still serves only C-PS1-5/C-PS1-7; wiring `reaction-outcome` into that bundle is a separate,
unplanned step.

The first bundle-driven generator, `chemical-system-stability`, is live for the
**Stability & Change in Chemical Systems** bundle. It uses a single Mg + HCl investigation to
generate C-PS1-5 rate questions and C-PS1-7 quantitative-conservation questions with one shared
stimulus and per-question standard provenance. It is classroom-only. `0004` adds the nullable
generation-run bundle link; every saved question still records its own standard and provenance.

### Withdrawn family: `trait-distribution-shifts` (B-LS4-3, Biology 2), 2026-10-05

Built by Codex (spec and plan `docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md` and
`docs/superpowers/plans/2026-10-04-trait-distribution-shifts-plan.md`, kept on `main`; code in commits `152d389` and `a9c55ba`,
reverted). Six templates over fictional cases, citing five Biology 2 observable-performance bullets. The standard's boundary
(basic statistical and graphical analysis, no allele-frequency calculations) and the citations were respected, EOCEP stayed
rejected, no existing golden digest changed, and the suite passed (444). It was withdrawn for these defects, found by a
fresh-context review and reproduced independently (rates are over 12,000 to 13,000 generated items):

- **Critical: two correct answers.** `interpret_fitness_rate`: the distractor "The variant with more survivors had the higher
  survival rate" is true whenever the favoured variant also started larger (about half of items). `represent_distribution`:
  at sample time 4 the total is 100, so the "count misread as percent" distractor is exactly true (about 23% of items).
  A student who picked a true statement was marked wrong.
- **Important:** (1) cross-item leaks in the default mixed set (a sibling item's key appears in the analyze choices in about
  half of sets); (2) `calculate_proportion` shows the chart that plots its answer, and every chart caption says the values are
  in the table when the table holds counts, not the plotted percentages; (3) `_pct` uses Python's round-half-to-even, so 50/80
  shows "about 62%"; (4) `support_selection_claim`'s key is always the longest choice and says organisms "are heritable";
  (5) the spec's count-versus-proportion trap is built into the data but no item uses it.
- **Minor, for the redo:** wording slips ("its" after a plural, "are the physiological variant"), a trivially eliminable
  distractor, `calculate_proportion` can never ask about time 4, the constructed-response rubric does not reject a
  need-based account, fitness start sizes cue the trap, and the tests mirror the module (`round()`, `CASES`) and never check
  that distractors are false.

To bring the family back: re-apply it on a new branch (revert the revert, or cherry-pick `152d389` and `a9c55ba`), fix all
Critical and Important items, and give it a new version (**1.1.0**, because 1.0.0 was live and generated different items).
Add a test that evaluates every choice's claim against the displayed data with independent ground truth and asserts exactly
one is true, a full-set leak test, a half-up rounding test with typed ground truth, and prove each guard with a planted
mutation. Then a fresh review, then Brandon's explicit yes to merge and again to deploy.

Status (2026-10-05): the redo is built and tested on `feat/bls4-3-redo` (independent tests recompute truth from the displayed
tables; 462 backend tests). A fresh-context review found six Important issues (a support-stem leak, a missing rounding
note in calculate-only sets, an unimplemented 3-point spacing rule, a per-clause-majority cue in the support item, an
over-100 distractor, and leak tests that could not fail); all are fixed with tests that failed first. Not merged, not
deployed.

## Results tracking and linked variants

Design: `docs/superpowers/specs/2026-09-29-results-and-variants-design.md`. Plan:
`docs/superpowers/plans/2026-09-29-results-and-variants-plan.md`. Schema: migration `0005`.

- **Record use.** An *administration* records that an assessment was given (label, date, one or more sections such
  as "Period 2"). Its items are a snapshot of the assessment's items at that moment (exact question version and
  position), so later edits, reorders, refreshes, or removals never change it. Owner = the user who records it.
- **Results.** Teachers enter correct/attempted totals per question per section. No row means no data (accuracy
  is `null`, shown as `—`); 0 of 30 is 0%. "Correct" means full credit; partial credit is not supported. Batch
  saves are atomic and validated (no duplicates, ids must belong to the administration, `attempted >= 1`,
  `0 <= correct <= attempted`, a null pair clears a cell). "Limited response count" (aggregate attempted 1–9) is
  a display hint only. No student names or IDs are stored.
- **Access.** Administrations, results, `times_used`/`last_used`, the summary and the usage panel are visible and
  editable only to the owner and to admin/power users (`core/policy.can_modify`). Other users get 404. Question
  text stays broadly viewable.
- **Routes.** `POST/GET /api/assessments/{id}/administrations`; `GET/PATCH/DELETE /api/administrations/{id}`
  (+ `/restore`, `/sections`, `/results`); `GET /api/results/summary`; `GET /api/questions/{id}/usage`;
  `POST /api/questions/variants/preview` and `/save`.
- **Variants.** A variant is a new generated item from the same family and template as its parent (a new seed,
  current family code, the parent's saved generation mode), linked by `questions.variant_of_id`. It is never
  described as equivalent in difficulty. Preview persists nothing and returns signed, expiring (30 min),
  user-bound candidate tokens; save accepts tokens only and re-derives everything server-side. Distinctness uses a
  content fingerprint (stem, stimulus, unordered choice text/correct pairs, answer, question type) against every
  version in the whole lineage. Limits: 20 per batch, 50 variants per root question, 25 attempts. Bundle-family,
  retired-family and family-less parents are reported as "unavailable". A replayed token or a sibling saved first
  returns 409.
- **Locking.** Creating an administration locks the assessment row; the existing assessment mutators now lock it
  too. Results and section edits lock the administration row.
- **Coverage caveat.** Variants only exist for standards that have a question family (see
  `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`).

## Coverage grid (deployed 2026-10-02 as `5e12510`)

Spec: `docs/superpowers/specs/2026-10-02-coverage-grid-design.md`. Plan: `docs/superpowers/plans/2026-10-02-coverage-grid-plan.md`.
Workstream B of `2026-09-30-nina-feedback-roadmap.md`. No migration.

- **Endpoint.** `GET /api/coverage?course_id=&year=` returns bundle groups (then "Other standards"), each standard with
  question counts by all five statuses (department-wide, not date-scoped), times assessed, last assessed, summed
  correct/attempted, accuracy (`null` with no data), and a limited-response hint. A standard in several bundles appears
  under each with `also_in`, and is counted once in `summary`.
- **Scope.** `year` omitted is the current school year (Aug 1 to Jul 31, server clock via `services/coverage.today`),
  an integer 2000-2100 is that school year's start, `all` is explicit all-time; anything else is 422. The response
  carries the resolved `scope` (kind, year, label, start, end) and `available_years`; the page prints the server's
  label and dates and computes none itself.
- **Visibility.** Administration figures use `visible_clauses(user)`, identical to `/api/results/summary`; a test
  checks the per-standard `attempted` equals the summary's for regular, power and admin users.
- **Page.** `/coverage` (rail item "Coverage", link from the Overview coverage widget). Course and school-year selects
  live in the URL. Wording is "assessed", never "covered" or "mastered", and says assessed is not taught.
- **Verified.** Backend: 314 tests pass on Postgres, none skipped. Browser (headless Chromium against a scratch
  stack, 42 checks): no overflow or console errors at 1440, 1024, 768, 360px; scope line equals the API; 0 of 30 shows
  0%, blank shows a dash, 9 attempted shows "Limited response count"; Jul 31 vs Aug 1 land in different years; bad
  `?year=` shows the error notice; keyboard reaches both selects and Generate; print hides selects, rail and buttons;
  a second teacher sees no administration figures but the same question counts; a bad `?year=`, an unknown `?course=`, failed or empty course lists all recover (link back, fallback course, error, empty state); row Generate links carry
  `standard`, `bundle`, `family`. Not verified: a real touch device, Safari, Firefox.
- **Known small things.** In all-time view an unassessed standard still reads "Not assessed in this period".

## EOCEP practice mode

EOCEP mode was completed for the currently EOCEP-eligible implemented Biology 1 families.

### What exists

- Alembic migration `0002_eocep_constraints` adds `standards.eocep_constraints` (JSONB).
- `biology-1-eocep.json` holds structured, source-page-referenced constraints.
- The standards importer recognizes `*-eocep.json` separately from course and bundle files and
  stores constraints on their matching Biology 1 standard.
- The Generate API accepts `generation_mode: "classroom" | "eocep"`.
- EOCEP requests are accepted only for Biology 1 standards with imported EOCEP constraints.
- EOCEP mode now enforces the constraints instead of only displaying them: it always excludes
  constructed-response templates (the EOCEP is entirely selected-response), and it excludes any
  template keys listed under a standard's `excluded_templates` map in `biology-1-eocep.json` (keyed
  by family key; empty today because no implemented template currently constructs a pedigree,
  dihybrid cross, or growth-rate calculation — add entries there if a future template does). An
  explicit request for a blocked type or template is rejected with 422 rather than silently dropped.
  The Generate UI disables the same options when EOCEP mode is selected.
- EOCEP selection is stored in generation options/provenance.
- Generate UI has Classroom and EOCEP Practice choices.
- Classroom mode is the default and is unchanged.

### Current imported EOCEP coverage

| Standard | Family | Source pages | Key constraints |
|---|---|---|---|
| B-LS2-1 | population-carrying-capacity | Assessment Specifications pp. 11–12 | No population-growth calculations, specific nutrient cycles, or multi-population relationships; use carrying-capacity/limiting-factor models. |
| B-LS3-3 | trait-probability | Assessment Specifications pp. 15–16 | No constructed pedigrees/dihybrid crosses, specific disorders, Hardy-Weinberg, or chi-square; monohybrid ratios/probabilities are permitted. |
| B-LS1-1 | dna-protein-synthesis | Assessment Specifications pp. 3–4 | No 3'/5', intron, exon, Okazaki fragment, initiation, elongation or termination; no codon wheel; codon chart supplied; no recall of codon meanings. EOCEP items print strands without ends. |
| B-LS3-2 | mutation-effects | Assessment Specifications p. 15 | No meiosis phase names; no codon wheel. Family covers the mutation part only (shown as a note in EOCEP mode). |
| B-LS4-4 | natural-selection-trend | Assessment Specifications p. 19 | No allele-frequency calculations, Hardy-Weinberg or chi-square. |

Enforcement: each entry's `banned_terms` is scanned in `tests/test_eocep_families.py` over many
seeds. The `allowed_terminology` lists are reference only (the source says terms "could be used"). The scan covers generated
text only: the standards' observable-performance wording is official SCDE text attached afterwards and is not scanned
(a test pins that `generate_set` attaches none).
Do not claim EOCEP support for other Biology 1 standards until their constraints are imported and
tested the same way. `eocep_constraints` is not stored in saved-question provenance; only
`options.generation_mode` and, for B-LS3-2, `options.eocep_scope_note` are stored.

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

**Status (2026-09-30): built and tested, not installed.** `ops/backup/` holds an encrypted backup job modelled on
the Life app's pipeline (age, the `gdrive-backup` rclone remote, ntfy via the Life `notify.sh`, a watchdog), with a
restore drill, per-artifact signatures (age only encrypts, so a forged file could otherwise be planted), a strict
bundle extractor, a signature-verifying watchdog, and 181 end-to-end tests. Runbook: `ops/backup/README.md`. Review brief for Codex:
`docs/superpowers/plans/2026-09-30-backup-ops-review-handoff.md`. **Nothing is scheduled, nothing has been uploaded,
and there is no real key yet.** To finish: Brandon generates a Science Bank age key pair on his own machine (private
key into the password manager), puts the `age1...` public key in `~/.config/science-bank-backup/recipients.txt`,
creates the signing key and `allowed_signers` (README step 3; keep the public line in the password manager too),
runs one backup and one restore drill, then installs the timers from the README. The Life private key's location is
unconfirmed (it may be in a Notepad++ buffer); that decides whether the Life backups can be read at all.

Backup job review and state:

- **Merged to `main` (PR #5, `5bc6126`, 2026-10-01). Still not switched on:** nothing is installed or scheduled, nothing
  has been uploaded, and there is no real key. Merging changed no running behaviour. Finish with the steps above.
- **Codex round 1 (2026-09-30), one Medium finding, fixed:** age encrypts but does not authenticate, so anyone with
  the public key and write access to the Drive folder could plant a forged "latest" that the drill would accept.
  Fix: every artifact is signed (OpenSSH `ssh-keygen -Y sign`) and the drill verifies the signature **before**
  decrypting; the decrypted tar is unpacked by an allowlist extractor (`ops/backup/bundle.py`: exact member names,
  regular files only, no links, devices, absolute or `..` paths); the manifest is validated before any of it is used
  (table names go into SQL, strings may reach a terminal); the file name must match the signed manifest time, so a
  renamed old backup is refused; the drill's throwaway Postgres has no network. The signing key sits on the host
  (it signs at backup time, no passphrase); Drive write access alone cannot forge a backup, and the verifying
  `allowed_signers` line lives in the password manager. The backup refuses to run without a signing key.
- **Tests:** 181 end-to-end checks in `ops/backup/tests/run-tests.sh` (scratch Postgres, throwaway keys, a local
  directory as the "remote", fake notifier), including a forged `latest` on the remote and 13 hostile signed
  bundles. Each new security check was verified by breaking it on purpose. A read-only run of the real commands
  against production restored cleanly into a throwaway Postgres (counts matched), before and after the change.
- **Codex round 2 (pre-merge verdict MERGE AFTER FIXES), all addressed:**
  - *Rename window (Medium).* The 15-minute skew let a genuine signed backup be accepted under a name up to 15 minutes
    different, and the label was not bound. The file name and time are now chosen once and recorded in the signed
    manifest as `artifact_name`; `bundle.py` requires an exact match (one second off, or relabelled, is refused).
  - *Watchdog trusted any `.sig` (Medium).* `--check-remote` now downloads the newest remote artifact and signature and
    verifies them against `allowed_signers` on this host (nothing decrypted); a missing signers file alerts. It also
    alerts when the last artifact this host uploaded (`last-upload-artifact`) is no longer on the remote, so deleting
    the newest backup is noticed at the next run rather than after 30 hours. Rolling back to an older genuine backup
    cannot be prevented by signatures alone; the README says so.
  - Low/info: remote orphan signatures are pruned (old ones only); the "never reached decryption" test now uses a
    recording `age` wrapper with a positive control; a per-member (4 GiB) and a total (8 GiB) size cap; a signer
    rotation test; the drill works on private copies (no check-then-use gap); README, PR text and handoff corrected.
  - Mutation tests for every new check were run (removing the exact-name check, the total cap, the watchdog's
    signature verification, its vanished-artifact check, the orphan prune and its age guard, and moving decryption
    ahead of signature verification); each makes the suite fail. Two of these first exposed weak tests (a "fresh
    orphan" test whose name collided with the run's own artifact; the original decrypt-ordering test), which were fixed.
    A read-only run of the real commands against production restored cleanly, and a 10-minute rename of a genuine
    backup was refused.
- **Still unverified:** real Google Drive/rclone behaviour (all upload tests used a local directory; the size check
  via `rclone lsjson --include` needs confirming on the first real run), the systemd units in the README (never
  created or validated; unit files and an installer were blocked by the permission system and left to Brandon),
  `loginctl` linger state, the Life `notify.sh` interface (assumed `ntfy_alert title msg [priority]`, never read),
  ShellCheck (not installed; `bash -n` only), and OpenSSH 8.0+ on any machine used for a recovery.

### Frontend look and shell (2026-10-02, PR #6)

The app follows an Azure DevOps look, applied everywhere in one pass:
- **Palette:** the accent token is now `accent` (renamed from `petrol`): `#106ebe`, dark `#0f548c`, soft `#ebf3fc`
  (`frontend/src/index.css`). `#106ebe` is white-on-blue 5.3:1 (Azure's brighter `#0078d4` is about 4.1:1 and fails for
  small text). Neutral text tokens (ink, muted, line) are unchanged **on purpose** so the printed student and teacher
  copies are identical to before (verified pixel by pixel). Corners are 2px. Font stays Atkinson Hyperlegible.
- **Shell:** a blue top bar (brand, user, log out) and an icon rail that expands over the page on hover or keyboard
  focus in `--rail-duration` (**375ms**, one CSS variable). The active page gets the Filled icon. Keyboard-only
  expansion uses `:has(:focus-visible)` so a mouse click does not leave the rail stuck open. A pin button ("Keep menu
  open") holds it open and pushes the content over; the choice is remembered in `localStorage`
  (`science-bank:rail-pinned`). Below 1024px the rail becomes a Menu button. Motion is off under reduced-motion.
- **Icons:** Microsoft Fluent System Icons (MIT) via the **full** `@fluentui/react-icons` package, chosen by Brandon.
  Only the eight nav icons are imported, all in `components/navIcons.tsx`, and tree-shaking keeps the bundle growth
  to about 16 kB. Plan: once the icon set is settled, trim to the few SVGs actually used (vendor them with the MIT
  notice) or move them off-site; only `navIcons.tsx` and `Layout.tsx` would change.
- **Overview (`/`)** is a 30,000-foot view: four summary tiles, compact bundle tiles (name, progress, "n of m ready"),
  three recent assessments, three results to review, a one-line standards coverage strip. No per-standard buttons.
- **Working buttons moved to the Bundles page:** each aligned standard has a filled **Generate** (opens
  `/generate?standard=&family=&bundle=`) or an outlined **View** (no question generator yet; says so to screen readers).
  The Generate page shows **Related standards** (also in this bundle, same domain) below the form.
- Fixed while restyling (all pre-existing): horizontal overflow on `/bundles` at 360px, `/standards/:id` at 360px,
  `/admin/users` at 360px (hidden `sr-only` text escaping a scroll wrapper; wrappers are now `relative`), and
  `/generate` at 768px (three columns forced into too little room).
- Verified in headless Chromium against a scratch stack (42 checks): every page at 1440, 1024, 768, 360px with no
  overflow, rail timing (207px at 150ms, 224px by 450ms), hover, keyboard, pin, reduced motion, contrast measured on
  the real elements, focus rings, console errors, and print compared with the baseline.

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

## Working method and lessons (2026-10-02 and 2026-10-03 sessions)

Four features shipped in these sessions (coverage grid `5e12510`, `dna-protein-synthesis` `52126d9`, `mutation-effects`
`46e4a36`, `natural-selection-trend` `0c47781`), each by the same loop. Reuse it.

1. **Brainstorm, then a spec** in `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (committed on `main`). Brandon
   reviews and approves it. Approval of the idea is not approval of the spec; approval of the spec is not approval of
   the plan.
2. **A plan** in `docs/superpowers/plans/` with tasks, exact code, `Expected:` lines, a Global Constraints block and a
   Review Focus block. For a new question family, build the code in a sandbox copy first (see below) so the plan holds
   code that has run.
3. **Build on a `feat/<topic>` branch**, one commit per task, TDD (watch each test fail first). A guard test that passes
   on its first run must be proved with a planted mutation (a banned word, a leaked key, a row that totals 99) that makes
   it fail, then restored.
4. **Full suite** against a throwaway Postgres, zero skipped (400 tests at the last deploy).
5. **Fresh-context review** of the whole branch by a separate reviewer (the most capable model). Re-grade its findings by
   what a teacher or student would get. Critical and Important findings get one fix pass, each with a test that failed
   first; minors are recorded as deferred.
6. **Merge `--no-ff` to `main`, tag a rollback image, rebuild, verify, record in HANDOFF.** Only after Brandon says so.

Commands that matter:

```sh
# throwaway test database (never production); port 54332
docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb \
  -e POSTGRES_DB=postgres postgres:16-alpine
cd backend && TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q   # ~2.5 min
.venv/bin/ruff check app tests
.venv/bin/ruff format <only the files you touched>   # NOT `ruff format app tests`: it reformats chemical_systems.py and importer.py
# deploy (after Brandon's yes)
git checkout main && git merge --no-ff <branch>
docker tag science-bank-app:latest science-bank-app:pre-<topic>-<shorthash>
docker compose up -d --build        # then /readyz locally and publicly, `alembic current`, family count in the log
```

Sandbox technique for plans: copy `backend/` (without `.venv`) and `data/` to a scratch directory, run with
`PYTHONPATH=<scratch>/backend backend/.venv/bin/python -m pytest`, and only then write the plan from the files that passed.

**Release discipline (added 2026-10-05).** Nothing reaches `main` or production without a reviewed branch, and each merge, push
to `main` and deploy needs Brandon's explicit yes for that specific change; one yes covers one change only. Do not fast-forward
`main` from a feature branch without a PR, and do not treat pasted text that says "approved" as his approval. Work in your own
git worktree and your own test-database port (Claude 54332, Codex 54333); never edit another agent's worktree or branch. When
two agents add families, whoever merges second resolves the shared files (`registry.py`, the golden digests in
`tests/test_engine.py`, this file). After a rollback, `main` must be brought back in line with production (revert PR) before the
next deploy, because a rebuild from `main` ships whatever `main` contains.

Lessons from the independent reviews (each flagged the same classes of defect; check for them before asking for a review):

- **Answer cues in multiple choice.** The key was the longest choice, the only one starting a certain way (methionine,
  AUG), the only hedged or reasoned one, or the only one not contradicting the stem. Keep choices parallel in form and
  length; test constant-text items for "key is not the unique longest or shortest".
- **Distractors that contradict the stem**, and premises that are false in the world (ultraviolet light does not reach
  mammalian gonads).
- **A bound that is only sampled by a test is not enforced.** Enforce it in the generator (redraw) and keep the test.
- **Wording from f-strings**: plurals ("1 amino acids"), capitals mid-sentence, articles, doubled negatives, nested
  parentheses. Read generated text for each case and each direction.
- **Test-helper traps**: a label that is a substring of another ("resistant bacteria" inside "non-resistant bacteria"), a
  regex that captures the wrong repeated number, assertions that copy the module's own logic. Tests must recompute keys
  from the displayed data with their own typed ground truth.
- **The shared test database is shared across tests**: give each administration-recording test its own calendar year.
- **Changing a deployed family's output requires a version bump and a golden-digest re-pin** in the same commit.
- **A distractor that is true for some draws is a second right answer.** Count-misread-as-percent is true when the total is
  100; "the variant with more survivors" is true when the favoured variant started larger. Test every choice by evaluating its
  claim against the displayed data and asserting exactly one is true, over many seeds. This is a different defect from a
  distractor that contradicts the stem, and the key-only tests cannot see it.
- **Cross-item leaks in mixed sets.** Items in one group share a stimulus: check that no key (a number plus its variant) appears
  in another item's stem or choices, in generated full sets.
- **Rounding.** Python's `round()` is half-to-even (62.5 becomes 62); students round half up. Use `Decimal` half-up, or
  redraw values that land on .5, and type the ground truth in the test.
- **A chart that plots the answer, and captions that claim the table holds what the chart plots.** Check what each stimulus
  piece shows against what the item asks.

State at the end of these sessions: production runs the `52e45c4` build (the app image `science-bank-app:latest`); nine families
registered; migration `0005`; 429 backend tests on that build; frontend `npx tsc -b`, `npm run lint` and `npm run build` clean.
Rollback images exist for every deploy (`science-bank-app:pre-*`).

The deployed EOCEP implementation covers B-LS1-1, B-LS3-2, and B-LS4-4. Its final isolated-database verification was
427 passed, zero skipped (one third-party deprecation warning); ruff, TypeScript, lint, and production build were clean.

**Not verified in a real browser on production** (verified in the container and on scratch stacks only): the signed-in
`/coverage` page, the Generate pages for B-LS1-1, B-LS3-2 and B-LS4-4, and how the two-series line chart renders for
`natural-selection-trend`, and the EOCEP scope note on the Generate page (verified by type-check and build only).
Brandon should open each once.

## Immediate recommended work

See `docs/superpowers/plans/2026-10-03-codex-handoff-next-work.md` for the ranked list, the open decisions that need
Brandon, and the deferred minor issues per feature. In short:

1. **Biology 2 B-LS4-3 redo: built on branch `feat/bls4-3-redo`, awaiting a fresh-context review, then Brandon's explicit yes to
   merge and a separate yes to deploy.** It is `trait-distribution-shifts` 1.1.0. See "Withdrawn family" for why 1.0.0 was
   pulled and `docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md` for the design.
2. **A second B-LS3-2 family**: meiosis and mutagen/replication-error dataset items, and frameshifts that also end the
   protein early (the current family excludes them by design).
3. **Word study aid for Biology 1** (Workstream C): blocked on Brandon choosing who drafts the first 10 to 15 glossary
   terms. Bundle 5, "Changes in Populations Over Time", is the agreed pilot.
4. Nina should use the current families in a real unit and record edits; revise templates only with a family version
   bump and updated deterministic tests.
5. Administration: Phase 2a operational visibility (Overview, Errors, Jobs, Audit), then Phase 2b content management,
   then Phase 3 change requests; both reuse `policy.can_modify` and `audit_events`.
6. Switch on the backups (`ops/backup/README.md`; key generation and timers are Brandon's steps) and add an Uptime
   Kuma `/readyz` monitor.
7. If moving toward a public product, do identity and workspaces before opening registration to strangers.
