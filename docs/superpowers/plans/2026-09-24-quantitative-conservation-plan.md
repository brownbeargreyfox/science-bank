# Quantitative Conservation (C-PS1-7) — Implementation Plan

## Goal

Ship the classroom-only `quantitative-conservation` family, displayed as **Mole stoichiometry**,
for Chemistry C-PS1-7. Generated scenarios must use coefficients, particles/moles, and mass as
evidence for conservation rather than as isolated conversion drills.

## Constraints

- No database migration, API contract change, or EOCEP change.
- Preserve all existing family outputs and version numbers.
- Use only the six approved simple reactions in the design; atomic masses and formulas are fixed,
  reviewed data.
- The family key is `quantitative-conservation`; UI title is `Mole stoichiometry: quantitative conservation`.
- Each complete scenario contains a conservation-evidence template. Explicit template filtering may
  request a narrower scaffold only when the caller chooses it.

## Tasks

### 1. Data model and arithmetic tests (red first)

- Add `backend/tests/test_quantitative_conservation.py` with independent fixed reaction-catalog
  checks for balanced atom totals, formula-derived molar masses, coefficient/mole ratios, and total
  reactant versus product mass at displayed precision. Atom-count and mass-conservation tests must
  not share the same assertion helper.
- Add pure helper tests for exact `Fraction` arithmetic and dimensional-analysis paths.
- Test sample calculations for every curated reaction before adding rendering/templates.

### 2. Implement the deterministic family

- Create `backend/app/services/families/quantitative_conservation.py`.
- Keep atomic composition, atomic masses, and reaction coefficients as immutable curated data.
- Build scenarios from exact fractions; format only at the student-facing edge.
- Render one shared representation directly from those stored source-of-truth values: balanced
  equation, atom-count/molar-mass table, stated quantity, and clear units. Key calculations and
  displayed values must not use duplicate computation paths.
- Implement the six templates with distinct, named misconception-based distractors (for example
  `reversed_ratio`, `coefficient_as_mass`, and `skip_mass_to_moles`) and a constructed response
  that requires the reasoning chain, not merely a number.
- Register the family in `families/registry.py`.

### 3. Family invariants and golden output

- Extend `backend/tests/test_engine.py` to import/register the family and pin its golden digest.
- Across the seeded invariant suite, recompute every numerical answer from stored parameters and
  assert mass conservation, unit paths, balanced atom counts, unique MC choices, named distractor
  misconception classes, and no excluded advanced-stoichiometry terminology.
- Assert complete default generation includes `conservation_check` or `explain_conservation`.

### 4. Integration and presentation verification

- Confirm the imported C-PS1-7 standard advertises the family through `/api/families` and generation
  preview/save, including ordinary ownership/provenance behavior.
- Run backend tests against throwaway Postgres with zero skips; run backend lint, frontend lint, and
  frontend build. The existing Generate page should discover the new catalog entry without bespoke UI.
- Review at least one deterministic preview for each of the six curated reactions for equation
  readability, unit clarity, rounding, and a visible conservation-evidence progression.

### 5. Documentation and handoff

- Update `QUESTION_FAMILY_CATALOG.md`, `HANDOFF.md`, and README family summaries with the final key,
  display name, scope, and C-PS1-7 alignment.
- Record that this is classroom Chemistry work and does not extend EOCEP coverage.

## Acceptance criteria

- Every generated question is deterministic, scientifically valid, dimensionally valid, and aligned
  to the intended C-PS1-7 evidence pathway.
- Each default scenario explicitly assesses conservation through mathematical evidence.
- C-PS1-7 is the sole binding; no EOCEP behavior changes.
- Existing family golden tests are unchanged; the new family has a pinned golden digest.
- Full backend tests have zero skipped DB tests; all lint/build checks pass.
