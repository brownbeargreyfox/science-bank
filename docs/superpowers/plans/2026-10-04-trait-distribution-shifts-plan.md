# Trait Distribution Shifts (B-LS4-3) Implementation Plan

**Goal:** Add `trait-distribution-shifts`, a deterministic, classroom-only Biology 2 family for B-LS4-3. Students
calculate and interpret trait proportions across unequal samples, distinguish rates from raw counts, and support a
natural-selection explanation with displayed distribution and reproductive-success evidence.

**Architecture:** Create a self-contained family module with its own six-case bank, a distribution drawer, a fitness
drawer, and six templates. It takes the deterministic RNG and rejection-sampling patterns from `natural_selection.py`
as a model, but neither imports nor changes that Biology 1 family. Register the new family only after its unit tests pass.

**Spec:** `docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md`

## Constraints

- Bind only to `SC / biology-2 / B-LS4-3`; version `1.0.0`; `Rng` is the only randomness source.
- Biology 2 is classroom-only. Do not add EOCEP data, behavior, or tests.
- Use basic proportions, percentages, tables, and a line chart only. Never compute or mention allele/gene frequency,
  Hardy-Weinberg, chi-square, drift, gene flow, or speciation.
- New files belong to this workstream: `trait_distribution_shifts.py`, its tests, this plan, and its approved spec. Do
  not edit `natural_selection.py`, `mutation_effects.py`, or `HANDOFF.md` during implementation.
- Shared conflict points are `registry.py` and golden digests in `tests/test_engine.py`; keep their change minimal and
  leave conflict resolution to the later merger.
- Use only the throwaway test database on port **54333** for API/full-suite tests. Never stop a container not started by
  this workstream.
- Format only touched Python files. Run `ruff check app tests` and the backend suite with zero failures and zero skips.

## Finalized scenario contract

`CASES` contains six fictional/generalized cases: ground beetle shell color (anatomical), finch beak thickness
(anatomical), minnow reaction speed (behavioral), shrub root depth (anatomical), marsh-grass salt tolerance
(physiological), and desert-lizard water conservation (physiological). Each names one stable condition, two explicitly
heritable variants (`a`/`b`), a trait type, and which variant has higher survival/reproductive success. No case mentions
people, illness, treatment, medicine, drugs, or pathogens.

`draw_scenario(rng)` returns JSON-serializable parameters containing the case, favored variant, four samples, and one
fitness comparison. Each sample is `{time, total, a, b}`. Its total is 80–140 and all four totals differ. The chart uses
`round(100 * count / total)` for each displayed percentage; tests compute this independently from the table.

Underlying proportions use the relative-fitness update from the B-LS4-4 pattern. The implementation owns an equivalent
helper rather than importing it. A scenario redraws until both variants have at least two counted individuals per sample;
the favored proportion rises by at least 15 percentage points overall and at least 6 points on each queried interval;
and one adjacent raw-count comparison moves opposite the favored percentage change. This makes the numerical
distribution meaningful and supplies a count-versus-proportion trap.

`fitness.rows` has one row per variant: `{variant, started, survived, offspring}`. Starts are unequal multiples of five
between 40 and 90. The favored variant has a survival rate at least 0.15 higher and offspring-per-starter rate at least
0.20 higher. About half of draws are retained only when its raw survivor count is lower; the rest when it is higher.
All displayed values are integers and `0 <= survived <= started`, `0 <= offspring`.

## TDD tasks

### 1. Scenario tests and drawer

Create `backend/tests/test_trait_distribution_shifts.py` first with independent constants for case names, trait types,
and favored variants. Add tests over 200 seeds that verify JSON serialization, exactly four unequal totals in range,
row sums, count bounds, independently rounded chart percentages, the proportion margins, and the opposite-direction
raw-count trap. Add fitness checks that recompute survival and offspring-per-starter rates from table values, confirm the
favored variant, validate all bounds, and require substantial coverage of both raw-survivor trap states.

Run the test file and observe collection failure. Then create
`backend/app/services/families/trait_distribution_shifts.py` with the case bank, `next_proportion`, distribution/fitness
drawers, and `draw_scenario`. Re-run until these tests pass. Add a planted mutation locally—such as returning a row whose
counts no longer equal its total—and confirm the independent row-total test fails before restoring it.

### 2. Family shell and stimuli

Add `TraitDistributionShifts(QuestionFamily)` with the single binding and six `TemplateSpec` entries exactly as cited in
the approved spec. Implement stimulus selection so distribution templates receive only the distribution table/chart,
fitness-rate receives only the fitness table, and evidence/explanation templates receive both. The chart must point to
the distribution table with `table_index: 0`; when both tables render, the fitness table follows it.

Write failing tests for catalog identity/binding/citations, selected-stimulus minimality, table/chart linkage, and chart
values recomputed from the displayed table. Implement the shell and renderer, then run the targeted tests. Plant an
incorrect chart percentage or table index and verify the independent check fails before restoring it.

### 3. DOK 1–2 multiple-choice templates

Implement, test-first, these templates:

- `represent_distribution` (`organizing_data[0]`, DOK 1): select the accurate proportion statement for a named sample.
- `calculate_proportion` (`identifying_relationships[0]`, DOK 1): calculate one rounded percentage from displayed
  count and total; raw count, complementary proportion, and plausible arithmetic error are distractors.
- `analyze_distribution_shift` (`identifying_relationships[0]`, DOK 2): select the proportional comparison supporting
  the trend; use the constructed raw-count trap as a distractor when applicable.
- `interpret_fitness_rate` (`interpreting_data[0]`, DOK 2): identify the advantage by rates, not survivor totals.
- `support_selection_claim` (`interpreting_data[1]`, DOK 2): select the explanation that jointly states heritability,
  displayed rate advantage, and increasing proportion.

For each, write a test that derives the answer from the rendered tables rather than module helpers. Across 200 seeds,
assert four distinct choices, exactly one recomputed key, all answer positions represented, and no position above 40%.
Test that the rate and count/proportion traps occur and key the correct normalized conclusion. Ensure the term “need” is
not in any key, stem, or shared stimulus and appears only in the intended misconception choice/rationale. Run each test
red before implementation, then green; plant a wrong key for one table-derived template and observe failure.

### 4. Constructed response and family-wide guards

Implement `explain_shift_with_data` (DOK 3; `interpreting_data[2]`). Its model answer and four-point scoring guide must
be generated from the rendered case trait type, two exact displayed proportions/percentages, and the displayed normalized
fitness values. It must describe the population-level trend and reproductive-success link, never individual need-based
change.

Add independent tests for the model answer's data references, case trait type, no cross-item key leaks in a full set,
and scope vocabulary. Scan all rendered text over 200 seeds for prohibited terms and health-context terms. Plant a banned
term and a leaked key to prove their guards fail, then restore. Confirm the exact template/DOK map and constructed
response's empty choices.

### 5. Registration and integration checks

Only after the isolated family tests pass:

1. Import/register `TraitDistributionShifts` in `backend/app/services/families/registry.py`.
2. Extend API generation/browse assertions to recognize Biology 2 B-LS4-3 and reject the family for Biology 1 B-LS4-4.
3. Add the family’s deterministic golden digest to `backend/tests/test_engine.py` after generating it with the established
   test helper.
4. Update any coverage/catalog assertions that enumerate family count or B-LS4-3 status. Do not alter standards data.

Run targeted unit tests, engine tests, API/coverage tests with `TEST_DATABASE_URL` using port 54333, then the complete
backend suite. Format only the new module and its test, run `ruff check app tests`, and confirm `git diff --check`.

## Completion evidence before review

- The new family is deterministic for repeated seeds, registered for Biology 2 B-LS4-3 only, and all template citations
  resolve to the five SCDE observable bullets.
- Independent tests validate every key from visible values and prove their highest-risk guards by planted mutation.
- All tests pass with zero skips against the assigned test database; static checks and diff whitespace checks are clean.
- The worktree changes contain only this family, its tests, required registry/integration updates, the approved spec, and
  this plan. `HANDOFF.md` remains untouched until a completed family is ready for its approved merge/deploy path.
