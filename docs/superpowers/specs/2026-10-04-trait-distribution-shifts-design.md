# Trait Distribution Shifts — B-LS4-3 Family Design

Date: 2026-10-04
Status: Design approved in chat (Brandon, 2026-10-04). Written specification awaiting review.
Builds on: the seeded, rejection-sampled population-data patterns in `natural_selection.py`, without importing or
editing that Biology 1 family.

## Goal

Add `trait-distribution-shifts`, a deterministic, Biology 2-only question family for **B-LS4-3**: “Apply concepts of
statistics and probability to support explanations that organisms with an advantageous heritable trait tend to increase
in proportion to organisms lacking this trait.” The family focuses on numerical distributions and normalized probability
measures, not the Biology 1 B-LS4-4 adaptation-explanation templates already implemented by
`natural-selection-trend`.

Items use curated fictional populations with two variants of one explicitly heritable anatomical, behavioral, or
physiological trait. Students analyze changing proportions over time and survival/reproduction rates with unequal sample
sizes, then use those data as evidence for a bounded natural-selection explanation. Biology 2 is classroom-only.

## SCDE alignment and boundary

The authoritative Biology 2 record states:

- **Clarification:** analyze shifts in numerical trait distributions and use them as evidence for explanations.
- **Boundary:** basic statistical and graphical analysis only; no allele-frequency calculations.
- **SEP:** Analyzing and Interpreting Data.
- **CCC:** Patterns.

The templates cite every relevant observable-performance bullet:

| Category | SCDE observable feature | Family use |
|---|---|---|
| `organizing_data[0]` | organize tables, charts, and graphs by distribution of genetic traits over time | read a representation of the displayed distribution |
| `identifying_relationships[0]` | analyze probability measures for patterns of change in numerical trait distributions over time/population scales | calculate and compare proportions; identify the trend |
| `interpreting_data[0]` | positive or negative effects on fitness relating to expression of a variable trait | compare normalized survival/reproduction measures |
| `interpreting_data[1]` | natural selection causes increases/decreases in heritable traits over time only if reproductive success is affected | support a selection claim with the displayed evidence |
| `interpreting_data[2]` | changes in distribution of anatomical, behavioral, and physiological adaptations | explain a type-specific distribution shift with evidence |

No item names, computes, infers, or uses allele frequency, gene frequency, Hardy-Weinberg, chi-square, genetic drift,
gene flow, speciation, or genetic mechanisms beyond the stated fact that parents pass the focal trait to offspring.

## Data model

The new module owns its case bank and data functions. It follows `natural_selection.py`'s deterministic-RNG,
rejection-sampling, student-visible-value, and two-variant conventions, but does not import from or alter it. The distinct
dataset design makes B-LS4-3 statistical rather than a duplicate of B-LS4-4's environmental-reversal narrative.

Each curated case supplies:

- a plural organism, focal trait, and exactly two named inherited variants;
- one stable, plainly described environmental condition;
- a trait type: anatomical, behavioral, or physiological;
- a factual condition linking one variant to higher survival or reproduction in that condition.

The initial case bank will use six fictional or generalized classroom cases, with the favored variant and trait type
balanced across seeds: dark/light ground-beetle shells (anatomical), thick/thin finch beaks (anatomical), quick/slow
minnow response (behavioral), deep/shallow shrub roots (anatomical), salt-tolerant/non-tolerant marsh grass
(physiological), and high/low water-conservation desert lizards (physiological). Lab, health, treatment, pathogen, and
human contexts are excluded.

### Distribution table and graph

For each scenario, four time samples are drawn. Each sample total differs and is in the inclusive range 80–140. The table
shows the total sampled and the count for each variant; every row sums exactly to that total. The line chart, linked to
the table as its accessible alternative, plots the computed percentage for each variant at each time.

The underlying proportion follows the same relative-fitness update pattern as the existing natural-selection family,
with the favored variant increasing every interval. Counts are rounded only after each sample total is selected. A draw
is rejected unless all of the following are true:

- each variant count is between 2 and `total - 2` in every displayed sample;
- the favored variant rises by at least 6 percentage points from the first to last sample and is at least 15 percentage
  points higher by the last sample;
- the unfavored variant falls by the complementary amount;
- no time-point comparison used by an item is within 3 percentage points;
- at least one sampled raw count changes in the opposite direction from the favored variant's percentage, creating a
  deliberate count-versus-proportion trap without making the graph inconsistent with the table.

### Fitness table

A second table gives each variant's `started`, `survived`, and `offspring from survivors` for one interval under the same
condition. Starting groups differ (40–90, in multiples of five). The favored variant has both a higher survival
probability (`survived / started`) and higher offspring-per-starter probability; rates differ by at least 0.15 and 0.20
respectively. Roughly half the draws make the higher-rate variant have fewer raw survivors, so a student must normalize
rather than choose the largest count. All counts are nonnegative integers and `survived <= started`.

Every displayed number is stored in the scenario. Every key, rationale, percentage, chart point, and constructed model
answer is recomputed from those stored values only.

## Templates

| Key | DOK | Type | Observable citation |
|---|---:|---|---|
| `represent_distribution` | 1 | multiple choice | `organizing_data[0]` |
| `calculate_proportion` | 1 | multiple choice | `identifying_relationships[0]` |
| `analyze_distribution_shift` | 2 | multiple choice | `identifying_relationships[0]` |
| `interpret_fitness_rate` | 2 | multiple choice | `interpreting_data[0]` |
| `support_selection_claim` | 2 | multiple choice | `interpreting_data[1]` |
| `explain_shift_with_data` | 3 | constructed response | `interpreting_data[2]` |

Single-standard family: bind only to `SC / biology-2 / B-LS4-3`; no template declares a separate standard code.

### Item details

- **`represent_distribution`** shows the distribution table and line chart. It asks which statement accurately describes
  the graph at one named time point. Choices distinguish count, total, proportion, and the opposite variant. The keyed
  statement uses the plotted percentage and table values; no chart-reading answer relies on color alone.
- **`calculate_proportion`** shows the distribution table only. It asks for the percentage of one named variant at a
  specified sample. Choices are the computed percentage, the raw count misread as a percent, the other variant's
  percentage, and a plausible arithmetic error. The key is exact to the displayed whole-percent rounding convention.
- **`analyze_distribution_shift`** shows table and graph. It asks which comparison supports a claim that the named
  variant increased *in proportion* over the study. The key compares two displayed percentages; a raw-count comparison
  that points the wrong way is a required distractor whenever the scenario's trap supports it.
- **`interpret_fitness_rate`** shows the fitness table only. It asks which variant had the fitness advantage in the
  stated condition. The key follows normalized survival and offspring-per-starter measures, not the greater raw survivor
  count. Choices include the raw-count trap, the other variant, and an unsupported tie.
- **`support_selection_claim`** shows both data sources. It asks which explanation is best supported. The key connects
  the trait's heritability, the named variant's higher survival/reproduction probability, and its increasing proportion.
  Distractors respectively claim individuals developed the trait because they needed it, use a distribution shift without
  reproductive-success evidence, or assert that a favorable trait must increase regardless of conditions.
- **`explain_shift_with_data`** shows both data sources and asks for a data-based explanation of the numerical change in
  the named anatomical, behavioral, or physiological trait. Its computed four-point model/rubric requires: (1) identify
  the trait type and the variant whose proportion changed; (2) cite two proportions or percentages from the table/graph;
  (3) cite the relevant normalized survival or offspring evidence; and (4) explain that the trait is heritable, so
  higher survival and reproduction can increase its proportion over time. It explicitly rejects an account of individual
  organisms changing because they need to.

All multiple-choice sets contain four distinct, parallel choices, exactly one correct key, and engine-controlled
deterministic shuffle. No template exposes another template's answer in a shared stimulus or stem.

## Engine invariants and tests

The family starts at version `1.0.0`, subclasses `QuestionFamily`, uses `Rng` only, and redraws ambiguous scenarios.
`backend/tests/test_trait_distribution_shifts.py` will independently verify across at least 200 seeds:

- every table row totals exactly to its displayed sample total; chart percentages equal independently recomputed
  `count / total * 100` values under the published rounding rule;
- displayed fitness counts are valid, and independently recomputed normalized rates select the keyed fitness variant;
- all distribution-shift keys follow percentages, not raw counts; count/proportion trap cases occur in a substantial share
  of seeds;
- the favored variant, trait type, and case vary across seeds; all retained trends meet the stated margins;
- every MC key is independently recomputed from student-visible table/chart values; choices are unique and all correct
  positions occur, with none above 40%, across the seed sample;
- the constructed model answer cites the actual displayed trait type, proportions, and rate values;
- each rendered stimulus includes only tables and charts needed by its selected templates, and no cross-item answer leak
  occurs;
- a vocabulary/scope guard rejects allele frequency, gene frequency, Hardy, chi-square, drift, gene flow, speciation,
  infection, disease, patient, treatment, medicine, drug, hospital, human, and antibiotic; and a misconception guard
  confirms “need” appears only in the intended incorrect explanation/rationale;
- planted mutations to a row total, chart percentage, rate key, and banned term each cause an appropriate test to fail.

Integration coverage will add catalog/citation checks, the normal engine determinism matrix, an API generation case, the
Biology-1/Biology-2 binding mismatch check, and a golden digest. Biology 2 is not EOCEP-assessed, so no EOCEP template or
constraint work is included.

## Files

Create `backend/app/services/families/trait_distribution_shifts.py` and
`backend/tests/test_trait_distribution_shifts.py`. Modify the shared `registry.py`, the golden digests in
`backend/tests/test_engine.py`, relevant API/coverage tests, and the catalog/coverage documentation if their assertions
enumerate implemented families. Do not modify `natural_selection.py`, `mutation_effects.py`, standards JSON, database
schema, frontend code, or `HANDOFF.md` until the family is built and the merge/deploy process calls for it.

## Out of scope

Allele or gene-frequency calculations; Hardy-Weinberg; chi-square; drift; gene flow; speciation; environmental reversals;
multi-trait cases; real species datasets; health contexts; EOCEP work; and Biology 1 B-LS4-4 templates. The existing
`natural-selection-trend` family remains unchanged and Biology-1-only.

## Open items

None. The implementation plan must select final wording for each case and establish the exact rounding and redraw limits
through a prototype before code is written.
