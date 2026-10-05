# Trait Distribution Shifts — B-LS4-3 Family Design (v1.1.0 redo)

Date: 2026-10-04 (amended 2026-10-05)

Status: Amended 2026-10-05 after the first build (1.0.0) was withdrawn. Design approved in chat (Brandon, 2026-10-05);
written specification awaiting Brandon's review. Supersedes the 2026-10-04 text of this file.

Builds on: the seeded, rejection-sampled population-data patterns in `natural_selection.py`, without importing or
editing that Biology 1 family. The withdrawn code is in git history (`152d389`, `a9c55ba`; reverted by PR 10) and in the
image `science-bank-app:withdrawn-trait-distribution-shifts-a9c55ba`.

## Why this is a redo

Version 1.0.0 was merged and deployed without review, then withdrawn after a fresh-context review. It had two Critical
defects (items with two correct answers) and five Important ones; several came from this spec, not only the code. This
amendment fixes the design. The mapping from each finding to its resolution is the table below; every row has a test.

| Finding | Cause | Resolution in this spec |
|---|---|---|
| C1: `interpret_fitness_rate` had two true choices in about half of items | A "variant with more survivors" distractor that is true when the favoured variant also started larger | Choices are claims with computed truth values; exactly one must be true (see "Claims and the one-true-choice rule"). The raw-count trap is carried by the data, not by a separate choice |
| C2: `represent_distribution` had two true choices in about 23% of items | "Count read as percent" is exactly true when the total is 100; the spec asked for that distractor | Totals are never 100; the same one-true-choice rule catches the remaining coincidences |
| I1: sibling items leaked each other's keys | The analyze item printed percentages that DOK 1 items ask for; the support key named the fitness winner | Analyze states a change in percentage points, not the two percentages; the support item states no rate direction; a full-set leak test |
| I2: a calculation item showed the chart that plots its answer; the chart caption was false | Items in one set share one stimulus, so a set with a chart item also shows the percentages; and the table held counts, not the plotted percentages | `calculate_proportion` asks for a **pooled** percentage over two named samples, a number no table, column or chart shows, so it stays a real calculation in every set; every table shown with a chart gets percentage columns, so the chart's text alternative holds the plotted values |
| I3: 50/80 shown as 62% | Python `round()` is half-to-even | Percentages round half up (`Decimal`); stated on the stimulus |
| I4: the support key was always the longest and said organisms "are heritable" | Hand-written asymmetric choices | Four parallel, concrete three-clause choices naming the trait, variants, condition and starting sizes; the key is never the unique longest or shortest; correct wording ("the trait is passed from parents to offspring") |
| I5: the count-versus-proportion trap was never used | The draw forced a falling raw count but no item used it | The analyze item is built on an adjacent pair of samples where the favoured variant's count falls while its percentage rises |

## Goal

Add `trait-distribution-shifts`, a deterministic, Biology 2-only question family for **B-LS4-3**: “Apply concepts of
statistics and probability to support explanations that organisms with an advantageous heritable trait tend to increase
in proportion to organisms lacking this trait.” The family focuses on numerical distributions and normalized probability
measures, not the Biology 1 B-LS4-4 adaptation-explanation templates already implemented by `natural-selection-trend`.

Items use curated fictional populations with two variants of one explicitly heritable anatomical, behavioral, or
physiological trait. Students analyze changing proportions over time and survival/reproduction rates with unequal sample
sizes, then use those data as evidence for a bounded natural-selection explanation. Biology 2 is classroom-only; EOCEP is
Biology 1 only and stays rejected for this standard.

## SCDE alignment and boundary

The authoritative Biology 2 record (`data/standards/SC/2026-2027/biology-2.json`, code `B-LS4-3`) states:

- **Clarification:** analyze shifts in numerical trait distributions and use them as evidence for explanations.
- **Boundary:** basic statistical and graphical analysis only; no allele-frequency calculations.
- **SEP:** Analyzing and Interpreting Data. **CCC:** Patterns.

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

The module owns its case bank and data functions, following `natural_selection.py`'s deterministic-RNG,
rejection-sampling, student-visible-value and two-variant conventions without importing from it.

Each curated case supplies a plural organism, a focal trait, exactly two named inherited variants, one stable plainly
described condition, a trait type (anatomical, behavioral or physiological), and the variant the condition favours. Every
case's premises must be biologically sound as written (no unexplained links). The six cases:

| Case | Trait (type) | Condition | Favoured variant |
|---|---|---|---|
| ground beetles | shell color (anatomical) | the hillside soil is dark; birds find dark beetles harder to see | dark-shelled |
| finches | beak thickness (anatomical) | most seeds on the island are soft; thin beaks eat them more easily | thin-beaked |
| pond minnows | reaction speed (behavioral) | predatory fish live in the pond; quick minnows escape more often | quick-reacting |
| desert shrubs | root depth (anatomical) | rain falls often but wets only the top layer of soil; shallow roots take it up before it dries | shallow-rooted |
| marsh grass | salt tolerance (physiological) | salt water reaches the marsh soil at high tide | salt-tolerant |
| desert lizards | water conservation (physiological) | rain is rare and the water holes dry up early in the season; lizards that conserve more water lose less on dry days | high-conservation |

Lab, health, treatment, pathogen and human contexts are excluded. Final wording is fixed by the prototype, subject to the
rule above.

**Display order.** Each scenario draws a `swap` flag that sets the order in which the two variants appear in every table,
chart series and choice list, so the favoured variant is not always first and no position cues the key.

### Distribution table and graph

Four samples are drawn. The four totals are distinct values from 80 to 140 in steps of 5, **excluding 100**, in a random
order. The table shows the sample time, the total sampled and the count for each variant; every row sums exactly to its
total. Wherever a chart is shown, the table also has a "percent of sample" column per variant holding the plotted values,
so the chart's text alternative is the table. A set with no chart item shows a counts-only table. Items in one generated
set share one stimulus, so no item may rely on a value being absent from it: `calculate_proportion` asks for a pooled value
that no stimulus ever shows.

**Rounding.** Every displayed or keyed percentage is the exact `count / total * 100` rounded to a whole number **half up**
(`Decimal`, `ROUND_HALF_UP`), and the stimulus says "Percentages are rounded to the nearest whole number; a half rounds up."
The same function produces chart points, keys, rationales and the constructed-response answer.

The underlying proportion follows the relative-fitness update pattern of the existing natural-selection family, with the
favoured variant rising every interval. Counts are rounded after each total is chosen. A draw is rejected unless:

- each variant count is between 2 and `total - 2` in every sample;
- the favoured variant's percentage rises by at least 15 points from the first to the last sample and by at least 3 points
  in every interval; the other variant falls by the complement;
- **a trap window exists:** at least one adjacent pair of samples `(i, i+1)` where the favoured variant's raw count falls
  while its percentage rises by at least 3 points. The window is stored and is the basis of `analyze_distribution_shift`;
- no two percentages used by one item's choices are within 3 points of each other (so no pair of choices is ambiguous).

### Fitness table

A second table gives each variant's `started`, `survived` and `offspring from survivors` for one interval under the same
condition. The larger starting group is 70–90 and the smaller 40–55, both multiples of 5; which variant is larger is drawn
independently of which is favoured. The favoured variant has both a higher survival rate (`survived / started`, at least
0.15 higher) and a higher offspring-per-starter rate (at least 0.20 higher). A `trap` flag records whether the favoured
variant has fewer raw survivors (about half the draws). All counts are nonnegative integers and `survived <= started`.

Every displayed number is stored in the scenario. Every key, rationale, percentage, chart point and constructed answer is
recomputed from stored values only.

## Claims and the one-true-choice rule

Each multiple-choice item is built from four **claims**. A claim is a sentence plus a truth value computed from the stored
scenario (and the displayed numbers), not hand-labelled. The builder requires exactly one claim to be true; otherwise it
raises `GenerationError` and the engine redraws. This is enforced in the generator, not only sampled by tests. Claims that
state a number state the number computed from the stored data, so a numeric distractor that coincides with the key (for
example a count that equals its percentage) makes the item redraw. Every choice has its own rationale that states why that
claim is true or false from the displayed numbers (no choice reuses the key's explanation).

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

- **`represent_distribution`** shows the distribution table (with percent columns) and the line chart, and asks which
  statement accurately represents the distribution at one named time. Claims: the correct percentage for a named variant;
  that variant's raw count read as a percent; the other variant's percentage for the named variant; and "the table does not
  show the total sampled". The raw-count claim is kept only when it is false for the draw (the one-true rule redraws
  otherwise). Chart reading never relies on colour alone.
- **`calculate_proportion`** asks for a **pooled** percentage: "What percentage of all the individuals sampled at sample
  times i and j combined were [variant]?" (two distinct named samples; the question says to combine them). The key is
  `(count_i + count_j) / (total_i + total_j) * 100` rounded half up. It is shown nowhere: the generator redraws the pair
  whenever the keyed value equals any percentage displayed for that variant in a percent column. The pair and variant are
  chosen when the scenario is drawn (and stored), so the scenario is redrawn if no hidden pooled value with enough wrong
  answers exists, and `represent_distribution` never repeats the statement that equals the pooled key. Choices: the pooled
  percentage and three wrong answers drawn from the classic errors: the mean of the two samples' percentages, the summed
  counts read as a percent (only when 99 or less, since a percent above 100 would cue the key), either sample's percentage
  alone, and the other variant's pooled percentage. All four values are distinct. It stays within the boundary (basic
  proportion arithmetic; no allele frequency).
- **`analyze_distribution_shift`** shows the table (with percent columns) and the chart for the stored trap window
  `(i, i+1)` and asks which statement about the **favoured variant's share of the sample** is supported. Choices share one
  form, "The share of [variant] in the sample [rose / fell / did not change] by about [d] percentage points from sample time i
  to sample time i+1, and its count went from [x] to [y]" (the count facts are true in every choice): the key (the favoured
  variant rose by the true difference of the two rounded percentages, while its count fell); the raw-count trap (the
  favoured variant "fell" by the same amount); the other variant claimed to have risen by that amount; and no change (0
  points). It states a difference, never one of the two percentages alone.
- **`interpret_fitness_rate`** shows the fitness table only (its stem calls it the survival and offspring table) and asks about **either survival rate or offspring per starter**
  (drawn). Choices: the favoured variant had the higher rate; the other variant had the higher rate (the raw-count trap
  whenever `trap` is set, because that variant then has more survivors); the two rates were the same; and the rates cannot
  be compared because the groups started with different numbers. Exactly one is true in every draw. Each rationale cites the
  displayed numbers and the computed rates.
- **`support_selection_claim`** shows both data sources and asks which explanation is best supported for why the named
  variant's share rose. The choices are **concrete**: each is a full sentence about this scenario that names the focal trait,
  both variants, the stated condition and the displayed starting group sizes (the `started` numbers, which no item keys on),
  in three parallel clauses of similar length ("[heritability clause], [evidence clause], so [conclusion]"). Key: the trait
  is passed from parents to offspring, and under the stated condition the two groups (named, with their starting sizes)
  differed in how well they survived and reproduced, so the rise in the named variant's share is evidence of natural selection.
  Distractors: the need-based misconception (individuals in the group developed the trait because they needed it under the
  condition); evidence that contradicts the tables (the two groups, with their sizes, survived and reproduced equally well); and the heritability contradiction (the trait is not passed from parents to offspring). **No choice states a
  survival or offspring rate, a percentage, a points change, or which variant did better**, so this item does not answer
  `interpret_fitness_rate`, `calculate_proportion` or `analyze_distribution_shift`; the displayed starting sizes may appear
  because no item's key is a starting size. Wording says the trait is passed on, never that organisms "are heritable".
- **`explain_shift_with_data`** shows both data sources and asks for a data-based explanation of the numerical change in the
  named anatomical, behavioral or physiological trait. Its computed four-point model and rubric require: (1) identify the
  trait type and the variant whose proportion changed; (2) cite two percentages from the table or graph; (3) cite the
  relevant normalized survival or offspring evidence; (4) explain that the trait is passed to offspring, so higher survival
  and reproduction can increase its proportion over time. The rubric **explicitly rejects** an account of individual
  organisms changing because they need to.

Wording rules: grammatical agreement in every case ("[Variant label] are …" plural subjects take plural verbs and
pronouns; "is a/an [type] trait" with the correct article); no sentence capitalised mid-clause; no doubled negatives.

All multiple-choice items have four distinct, parallel choices, one key, and the engine's deterministic shuffle.

## Engine invariants and tests

Version **1.1.0** (1.0.0 was live), subclassing `QuestionFamily`, `Rng` only, redrawing ambiguous scenarios. Tests in
`backend/tests/test_trait_distribution_shifts.py` recompute truth from the **displayed** tables and the choice text with
their own typed ground truth and `Decimal` half-up rounding; they never import the module's claim logic, `CASES` or `_pct`.
Over at least 200 seeds, at quantity 40 and as default six-item sets:

- every table row totals exactly to its displayed total; totals are four distinct values in 80–140 (step 5), never 100;
  percent columns and chart points equal independently recomputed values; a set with no chart item has a counts-only table;
  every chart's table holds its plotted values;
- **the pooled key of `calculate_proportion` is never displayed**: it equals no percent-column value for that variant, no
  chart point, and appears in no other item's stem or choices; it is recomputed from the displayed counts of the two named
  samples with half-up rounding; the four choice values are distinct; the mean-of-percentages distractor differs from the key;
- **exactly one choice is true** for every multiple-choice template, evaluated against the displayed data by parsing each
  choice; this is the test that would have caught C1 and C2;
- percentages that fall exactly on .5 round up (typed cases, e.g. 50/80 is 63%) and never appear as 62;
- the trap window exists and the analyze item uses it; both raw-count trap states occur for fitness (neither under 35%);
- **no leak in full sets**: no item's keyed value (a percentage for a named variant at a named time, a points change, a
  fitness winner) appears in another item's stem or choices; the support item states no percentage, rate, points change or
  winner, and every support choice names the trait, both variants, the condition and the starting sizes (concreteness test);
- the key is never the unique longest or the unique shortest choice (text items), and choice lengths in the support item are
  within 20% of each other;
- the favoured variant's display position, the case, the trait type and the key position all vary (no key position above
  40%); cases are sound as written;
- the constructed model answer cites the displayed trait type, two percentages and the rate values, and the rubric rejects a
  need-based account;
- vocabulary and scope guard rejects allele frequency, gene frequency, Hardy, chi-square, drift, gene flow, speciation,
  infection, disease, patient, treatment, medicine, drug, hospital, human and antibiotic; "need" appears only in the intended
  misconception; wording-agreement checks for every case and both display orders;
- no seed in a wide range raises `GenerationError` (the 422 a teacher would see);
- planted mutations each make an appropriate test fail: a distractor that is true, a total of 100, a half-to-even
  `round()`, a leaked key, a pooled key that equals a displayed percentage, a banned term, a dropped percent column, and a changed
  row total. Each guard that passes on first run is proved this way.

Integration coverage adds catalog/citation checks, the normal engine determinism matrix, an API generation case and the
rejection of a Biology 1 B-LS4-4 request for this family, a Biology 2 EOCEP rejection test specific to this standard, and a
golden digest at 1.1.0.

## Files

Create `backend/app/services/families/trait_distribution_shifts.py` and `backend/tests/test_trait_distribution_shifts.py`.
Modify the shared `registry.py`, the golden digests in `backend/tests/test_engine.py`, the API and coverage tests that
enumerate implemented families, and the coverage roadmap counts. Do not modify `natural_selection.py`,
`mutation_effects.py`, standards JSON, database schema or frontend code. `HANDOFF.md` is updated at deploy.

## Release

Built on `feat/bls4-3-redo` from `main`; a fresh-context review of the whole branch; then Brandon's explicit yes to merge
and, separately, to deploy. Nothing reaches `main` or production without that. After deploy the registry sync updates the
existing `question_families` row for `trait-distribution-shifts` from 1.0.0 to 1.1.0. No migration.

## Out of scope

Allele or gene-frequency calculations; Hardy-Weinberg; chi-square; drift; gene flow; speciation; environmental reversals;
multi-trait cases; real species datasets; health contexts; EOCEP work; Biology 1 B-LS4-4 templates; frontend changes. The
existing `natural-selection-trend` family remains unchanged and Biology-1-only.

## Open items

The plan fixes final wording for each case and each choice, and the exact redraw limits, by running a prototype in a
sandbox copy before the code is written into the plan.
