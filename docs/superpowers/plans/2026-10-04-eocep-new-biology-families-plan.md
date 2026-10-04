# EOCEP Constraints for the New Biology 1 Families — Implementation Plan

**Goal:** Enable EOCEP Practice for the three deployed Biology 1 families by importing the 2025–2026 EOCEP Biology 1
Assessment Specifications constraints and applying the existing server-side selected-response/template filter.

**Architecture:** This is a constrained-data release, not a new generator. Add three objects to
`biology-1-eocep.json`; the importer already persists them and `services.generation.eocep_blocked_templates` already
combines their per-family exclusions with the universal constructed-response block. Replace the three API denial tests
with success/filtering tests. No migration, family code, schema, frontend code, API type regeneration, family version,
or golden digest changes.

**Spec:** `docs/superpowers/specs/2026-10-03-eocep-new-biology-families-design.md`

## Global constraints

- The official PDF is the sole source: `SCDoE Targets/State Assessment Specifications_EOCEP Biology 1_2025-2026.pdf`,
  pp. 3–4 (B-LS1-1), p. 15 (B-LS3-2), and p. 19 (B-LS4-4). Preserve the existing JSON shape and source metadata.
- EOCEP remains Biology 1 only and selected-response only. An explicit constructed-response type or template remains a
  422; no request is silently substituted with a different template.
- B-LS1-1 EOCEP permits only `gene_activity_by_cell`. The current sequence templates visibly use prohibited `3′/5′`
  notation, so `transcribe_mrna`, `translate_mrna`, and `dna_to_protein` are listed as exclusions. The existing generic
  constructed-response block handles `explain_dna_to_protein`.
- B-LS3-2 permits all four existing selected-response templates. It uses a supplied codon **chart**, not a codon wheel,
  and does not require named meiosis phases. B-LS4-4 permits all five existing selected-response templates and continues
  to avoid allele-frequency calculations, Hardy-Weinberg, and Chi-square.
- Classroom generation must remain unchanged, including every B-LS1-1 sequence template. This release does not change a
  deployed family's output, so it must not bump a family version or re-pin a golden digest.
- The existing Generate page knows only question type, not standard-specific exclusions. Under the approved
  no-frontend-change scope, it may submit a manually selected B-LS1-1 sequence template in EOCEP mode; the server must
  reject it with 422. Unfiltered EOCEP requests use only allowed templates. Exposing exclusions to the picker is a later
  API/frontend feature, not an implicit part of this release.
- Run backend commands from `backend/`, use only a throwaway `sb-testdb` on port 54332 for DB tests, and format only
  touched files. No production database, deployment, merge, or push.

## Review focus

- A typo or missing JSON constraint that enables a B-LS1-1 `3′/5′` sequence template in EOCEP mode.
- A test that passes merely because constructed response is filtered, without demonstrating the three B-LS1-1
  selected-response exclusions.
- Accidentally changing classroom output, family metadata, a family version, or a golden digest.
- Treating terminology arrays as runtime word filters. They record source constraints; the actual enforcement here is
  selected-response filtering and the explicitly excluded B-LS1-1 templates.
- Overstating targeted practice as full EOCEP or full-standard equivalence, especially for B-LS3-2's separate
  meiosis-model scope.

## File map

| File | Change |
|---|---|
| `data/standards/SC/2026-2027/biology-1-eocep.json` | Add B-LS1-1, B-LS3-2, B-LS4-4 source constraints. |
| `backend/tests/test_api.py` | Update import count; replace denial assertions with imported-data and endpoint enforcement tests. |
| `HANDOFF.md` | After implementation validation, update EOCEP coverage/current-state wording without claiming full equivalence. |

---

## Task 1: Import the source constraints and pin the data contract

**Files:**

- Modify: `data/standards/SC/2026-2027/biology-1-eocep.json`
- Modify: `backend/tests/test_api.py`

- [ ] **RED — write importer/data assertions first.**

  In `test_import_counts_and_idempotency`, change the expected `eocep_constraints` count from 2 to 5. Add
  `test_new_eocep_constraints_are_imported(db)`, querying the Biology 1 `Standard` rows by course/code and asserting:

  - B-LS1-1 has `source_pages == [3, 4]`, includes the `3'/5'` prohibition, includes the codon-chart requirement, and
    has exactly `{"dna-protein-synthesis": ["transcribe_mrna", "translate_mrna", "dna_to_protein"]}` as its
    `excluded_templates`.
  - B-LS3-2 has `source_pages == [15]`, the named-meiosis-phases and codon-wheel prohibitions, a codon-chart
    requirement, and `{}` exclusions.
  - B-LS4-4 has `source_pages == [19]`, the allele-calculation, Hardy-Weinberg, and Chi-square prohibitions, an empty
    requirements list, and `{}` exclusions.

  Assert representative terms from each official terminology list (`transcription`/`differentiation`, `frameshift`/
  `nondisjunction`, and `survival rate`/`gene frequency`) rather than copying production filtering logic. The JSON itself
  is the exact complete transcription specified in the approved design.

  **Expected:** the test fails because the three standards have no imported constraint object and the count is still 2.

- [ ] **GREEN — add the three JSON objects.**

  Preserve top-level metadata. Add the complete source-derived arrays from the spec, in source order, with these
  required keys for every object:

  ```json
  {
    "source_pages": [],
    "allowed_terminology": [],
    "prohibitions": [],
    "requirements": [],
    "excluded_templates": {}
  }
  ```

  Set only B-LS1-1's `excluded_templates` to the three `dna-protein-synthesis` sequence templates above. Do not list
  constructed response: `eocep_blocked_templates` supplies that universal exclusion at request time.

- [ ] **Verify.**

  From `backend/` run:

  ```sh
  .venv/bin/python -m pytest tests/test_api.py -q
  ```

  **Expected:** importer/idempotency and source-data assertions pass; all still-unmodified EOCEP-denial assertions now
  fail, proving the data changes the request gate before Task 2 changes their expected outcome.

## Task 2: Prove EOCEP filtering and classroom preservation through the API

**Files:**

- Modify: `backend/tests/test_api.py`

- [ ] **RED — replace the three denial expectations with behaviour tests.**

  Keep the existing successful B-LS3-3 EOCEP check and Chemistry denials. Replace `denied_3`, `denied_4`, and
  `denied_5` with a parametrized helper over:

  ```python
  EOCEP_FAMILIES = (
      ("B-LS1-1", "dna-protein-synthesis", {"gene_activity_by_cell"},
       {"transcribe_mrna", "translate_mrna", "dna_to_protein"}),
      ("B-LS3-2", "mutation-effects",
       {"identify_mutation_type", "new_protein_after_change", "effect_on_protein", "inheritance_of_mutation"}, set()),
      ("B-LS4-4", "natural-selection-trend",
       {"compare_survival", "trait_trend", "effect_of_change", "explain_adaptation", "predict_new_change"}, set()),
  )
  ```

  For each entry, request an unfiltered EOCEP preview with enough items to exercise selection. Assert 200, EOCEP mode
  in the returned options, the returned constraints' source pages, all question types are `multiple_choice`, and every
  returned template key belongs to the declared allowed set. For B-LS1-1, assert the returned keys are exactly
  `{"gene_activity_by_cell"}`.

  Parametrize each B-LS1-1 exclusion as an explicit EOCEP `template_keys` request and assert 422 with the template key
  in the detail. Also explicitly request `gene_activity_by_cell` in EOCEP mode and assert 200.

  Finally, parameterize the three B-LS1-1 exclusions in **classroom** mode and assert 200 plus the requested template
  key. This is the regression proof that the EOCEP data filter has not altered classroom generation.

  **Expected:** after Task 1's data edit these tests pass against the existing filter; before the JSON edit, successful
  EOCEP previews fail with the existing “constraints” 422. The explicit B-LS1-1 rejection cases would fail if the
  exclusion list were removed.

- [ ] **Mutation proof.**

  In a scratch copy only, remove `translate_mrna` from B-LS1-1's JSON exclusions. Re-run the focused API test and
  observe the explicit-template rejection test fail. Restore the exact constraint before any commit.

- [ ] **Verify.**

  Run the focused file with the throwaway database, then the full backend suite:

  ```sh
  TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest tests/test_api.py -q
  TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q
  .venv/bin/ruff check app tests
  ```

  **Expected:** zero failures and zero skips. There is no new generator module, no frontend build, and no golden-digest
  update for this constraints-only release.

## Task 3: Document the supported scope

**Files:**

- Modify: `HANDOFF.md`

- [ ] Update **EOCEP practice mode** to list B-LS1-1, B-LS3-2, and B-LS4-4 alongside the two earlier standards; record
  their source pages and that only selected-response templates are enabled.
- [ ] State the intentional B-LS1-1 limitation: only `gene_activity_by_cell` is offered in EOCEP because the deployed
  sequence templates use prohibited `3′/5′` notation. State that B-LS3-2's mutation family is targeted sequence
  practice and does not add the separate meiosis-model work.
- [ ] Do not change the deployed-family table, versions, golden-digest language, or claim EOCEP equivalence. Record
  verification results only after they actually pass.

## Final verification and handoff

- [ ] Review `git diff` to confirm only the JSON, API tests, and handoff documentation changed.
- [ ] Run `git diff --check`, then format only touched Python files (expected: `backend/tests/test_api.py`) and rerun
  `ruff check app tests`.
- [ ] Confirm `git status` is clean after task commits and report exact focused/full pytest output, the mutation-test
  result, and the supported/template-excluded matrix.
- [ ] Do not merge, deploy, push, tag an image, or modify production. Request a fresh-context review after the full
  suite; address any Critical or Important finding with a failing test first. Merge/deploy remain Brandon decisions.
