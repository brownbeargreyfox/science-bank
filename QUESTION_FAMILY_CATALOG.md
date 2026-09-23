# Question Family Catalog — Build Plan

Companion to `PROJECT_STATUS.md`. That doc covers the whole project; this one is scoped to a
single piece of it: **expanding the deterministic question-family engine** past the 2-3-family
MVP toward full coverage of Biology 1, Biology 2, and Chemistry.

Read `PROJECT_STATUS.md` first if you haven't — in particular section 1 (why this is a
deterministic generator, not an LLM writer) and section 4.3 (what a "question family" is). This
doc assumes that context and doesn't repeat it.

## How this catalog is organized

Every Performance Expectation (PE) in `data/standards/SC/2026-2027/{biology-1,biology-2,
chemistry}.json` eventually needs at least one question family that can generate valid items
against it. Not every PE needs a *quantitative* family — some are better served by a
**scenario family** (a bank of real-world setups + an explanation/argument prompt) than a
**dataset family** (a generated table/graph + computed answer).

This catalog is split into three tiers, ordered by build priority. Within each tier, families
are listed with: the PE(s) they serve, the stimulus type, what varies (the parameter space), the
question shapes to generate, and where the answer key comes from. **Do not invent DOK levels** —
every question shape below should map back to the specific bullet(s) under that PE's
`observable_performances` in the standards JSON; that's SCDE's own language for what
distinguishes a routine-recall response from a strategic-reasoning one, and it's already sitting
in the data.

---

## Tier 1 — MVP (build first, ships the "Generate Question Set" flow end to end)

These are the three families already recommended in `PROJECT_STATUS.md` section 4.3. Pick these
because they're structurally the simplest dataset families (a single 2-variable dataset drives
everything) and they span two courses, proving the engine isn't Biology-1-only.

### 1. `population-growth` — serves B-LS2-1 (Biology 1)
- **Stimulus**: a data table (and/or line graph) of population size vs. time for a species in an
  ecosystem, under a named limiting factor scenario.
- **Parameters**: species name (pick from a small curated list of plausible organisms — deer,
  rabbits, algae, bacteria, a fish species — avoid anything requiring real-world numeric
  accuracy claims), starting population, growth shape (exponential-then-plateau, overshoot-
  dieback, oscillating predator-prey-adjacent), units, number of data points (4-8), a named
  limiting factor (food, predation, disease, space, competition) that explains the shape.
- **Question shapes**:
  - DOK 1/2: read a value off the table/graph; identify the trend direction.
  - DOK 2: identify which limiting factor is most consistent with the data shape.
  - DOK 3: predict the population at an unshown time point given the trend, and justify using
    the concept of carrying capacity; compare two scales (e.g. pond vs. lake) per the PE's
    "different scales" clause.
- **Answer key**: computed directly from the same generator function that drew the dataset —
  never a second independent guess.
- Related PE to reuse this generator for later: **B-LS2-2** (Biology 2) is the same
  carrying-capacity concept at a more advanced/statistical level (see Tier 2) — build
  `population-growth` so its parameter space and renderer can be extended rather than
  duplicated.

### 2. `trait-cross` — serves B-LS3-3 (Biology 1)
- **Stimulus**: a Punnett square or cross scenario for a named trait (curated list: pea plant
  seed color/shape classics, a coat-color example, a made-up but genetically-consistent trait —
  avoid real human traits to sidestep oversimplified single-gene claims about humans).
- **Parameters**: dominance pattern (complete, incomplete, codominant), parental genotypes,
  which cross (monohybrid only for Bio 1 — dihybrid is out of scope per the PE's assessment
  boundary, which excludes Hardy-Weinberg/Chi-square but not dihybrid explicitly; default to
  monohybrid for simplicity and confirm against the PE text before adding dihybrid).
- **Question shapes**:
  - DOK 1/2: complete the Punnett square; state the genotypic/phenotypic ratio.
  - DOK 2: given offspring phenotype data, infer parental genotypes.
  - DOK 3: given an environmental-factor twist (the PE explicitly covers environmental effects
    on trait expression, not just genetics), explain why observed phenotype ratios diverge from
    the predicted genotypic ratio.
- **Answer key**: computed from standard Punnett-square logic (deterministic combinatorics, not
  guessed).
- Related PE to reuse for later: **B-LS3-3 in Biology 2** is the *same PE code* extended into
  Hardy-Weinberg — see Tier 2, this is a direct extension, not a new family.

### 3. `reaction-rate` — serves C-PS1-5 (Chemistry)
- **Stimulus**: a data table of reaction rate (or time-to-completion) vs. temperature, and a
  second version vs. concentration, for a simple two-reactant reaction (named generically,
  e.g. "Reactant A + Reactant B → Product C" — avoid specific real reactions unless the numbers
  are pedagogically accurate, since this PE's boundary limits it to simple two-reactant systems).
- **Parameters**: which variable is held constant vs. varied (temperature or concentration),
  the number of trials, the direction/shape of the rate change (monotonic increase is the
  correct relationship per collision theory — don't generate a dataset that contradicts the
  DCI).
- **Question shapes**:
  - DOK 1/2: read the rate at a given condition; state whether rate increases or decreases with
    the varied condition.
  - DOK 2/3: explain the trend using collision theory (frequency and energy of collisions) — the
    PE's own reasoning chain in `observable_performances` gives the exact chain of logic the
    answer key's explanation should follow.
  - DOK 3: predict the qualitative effect of changing *both* variables simultaneously.
- **Answer key**: the explanation text is templated from the PE's own reasoning bullets, not
  freely generated — swap in the specific variable/direction, don't rewrite the science.

---

## Tier 2 — direct extensions of Tier 1 (build second; mostly reuse Tier 1 generators/renderers)

These reuse the same stimulus renderer and parameter space as a Tier 1 family but add
complexity or a new statistical layer, matching how the *same underlying phenomenon* is taught
at a more advanced level in Biology 2 or connects to a sibling PE.

### 4. `population-growth-advanced` — serves B-LS2-2 (Biology 2)
Extends family #1. Adds: multiple interacting scales (micro/mesocosm/biome per the PE text),
disturbance-magnitude framing (modest vs. extreme change, tied to LS2.C resilience language),
and a "revise your explanation given new data" question shape (the PE's SEP is "support and
*revise* explanations" — the question set should include a second dataset that contradicts the
first prediction and ask the student to revise).

### 5. `hardy-weinberg` — extends `trait-cross` (family #2) for B-LS3-3 (Biology 2)
Same PE code as Tier 1 family #2, but Biology 2 instruction explicitly extends into
Hardy-Weinberg Conditions/Equilibrium (confirmed in `biology-2.json`'s boundary note — Biology 2
is not EOCEP-assessed and goes past the Bio-1 boundary here). New parameters: allele
frequencies (p, q), population size, and a stated Hardy-Weinberg assumption being violated or
held. New question shapes: calculate expected genotype frequencies; identify which
Hardy-Weinberg assumption a given scenario violates.

### 6. `trophic-energy-transfer` — serves B-LS2-4 (Biology 2)
New stimulus shape (energy pyramid / food web diagram with quantities), but same "generate a
dataset, ask for reads/trends/predictions at increasing DOK" pattern as family #1. Parameters:
number of trophic levels (3-5), starting producer biomass/energy value, transfer efficiency
(fix near realistic ~10% per level, don't randomize into implausible ranges). Question shapes
per the PE's own bullets: identify producer vs. consumer levels from biomass; explain why higher
levels have less energy/fewer organisms using conservation + inefficiency language; calculate
energy available at a given level given the level below it.

### 7. `natural-selection-trend` — serves B-LS4-4 (Biology 1) and B-LS4-3 (Biology 2)
Two closely related PEs (adaptation via gene-frequency change, and statistical trait-proportion
shift) sharing one dataset shape: trait-frequency-over-generations data under a stated
selective-pressure scenario (a curated list: pesticide resistance, coloration/camouflage, beak
size, antibiotic resistance — avoid the specific worked examples already used as SCDE's own
*example anchoring phenomena* in the bundles files, e.g. don't reuse "antibiotic resistance"
verbatim since that's listed as an example phenomenon for B-LS4-2/4/5 bundling — pick a distinct
scenario so generated questions don't look copy-pasted from the bundling guide). B-LS4-4's
questions emphasize the *mechanism* (why the frequency shifts); B-LS4-3's questions emphasize
the *statistics* (how much/how fast it shifts, described with basic stats per its boundary,
no allele-frequency calculations).

### 8. `intermolecular-forces` — serves C-PS1-3 (Chemistry)
Stimulus: a small comparison table of 3-4 named substances with bulk properties (melting point,
boiling point, solubility pattern) but *not* named intermolecular force types (the PE's
clarification statement explicitly says emphasis is on relative *strength*, not naming
dipole-dipole/hydrogen-bonding/etc. by type — keep generated questions consistent with that
boundary). Parameters: which substances (curated set spanning ionic, small polar covalent,
nonpolar covalent, network solid), which property is compared. Question shapes: rank substances
by relative particle-attraction strength using the property data; explain a property difference
in terms of "stronger/weaker forces between particles" language only.

### 9. `mole-stoichiometry` — serves C-PS1-7 (Chemistry)
Stimulus: a balanced chemical equation (simple, per the boundary — no complex reactions) plus a
given quantity (mass or moles) of one species. Parameters: which species is given, which is
asked for, molar masses (pull from a small periodic-table-derived lookup, not invented).
Question shapes: convert between mass/moles/particles for the given species; use stoichiometric
ratios to find an unknown quantity of another species; state the underlying claim (atoms/mass
conserved) the calculation demonstrates. Answer key: computed via the same stoichiometric math
the question was generated from — this family is the most purely computational of the set and
should be built with real unit-tested arithmetic, not templated numbers.

### 10. `thermal-equilibrium` — serves C-PS3-4 (Chemistry)
Stimulus: two-object mixing scenario (masses, specific heats via lookup, initial temperatures)
producing a final-equilibrium-temperature dataset. Parameters: which two materials (curated
list with known specific heats — water, a metal, etc.), starting temperature gap. Question
shapes: identify direction of heat flow; calculate/verify the final temperature; explain why
energy distribution becomes more uniform (second law language) rather than describing it as
energy being "lost."

---

## Tier 3 — scenario families (build third; needed for full PE coverage)

Most remaining PEs are argument-construction, model-explanation, or design-evaluation types
(SEPs like "Constructing Explanations," "Engaging in Argument from Evidence," "Developing and
Using Models") rather than data-table types. These don't need a numeric parameter space — they
need a **scenario bank**: a curated set of short, varied real-world setups (stored as structured
data, reviewed once by Nina, then reused/lightly remixed at generation time) paired with a
prompt template keyed to the PE's `observable_performances` bullets.

This is a fundamentally different family *shape* than Tiers 1-2 and deserves its own design pass
before building — don't force these PEs into the dataset-family pattern. Flag for a dedicated
planning session once Tier 1-2 are shipped and the engine's plumbing (stimulus storage, question
storage, versioning, the generation UI flow) is proven out. Candidate first scenario family:
**B-LS1-1** (DNA→protein structure-function explanation) since it's the single most-repeated PE
across the bundling guides (appears as a partial-connection PE in nearly every Biology 1 and
Biology 2 bundle) — building its scenario bank well will pay off across many bundles.

---

## Build sequencing recommendation

1. Ship Tier 1 (3 families) end-to-end through the full generation UI flow first — this is
   `PROJECT_STATUS.md` Phase 4. Getting one family fully working (stimulus generation → question
   templating → answer key → saved to question bank → shows in review queue) validates the whole
   engine architecture before multiplying families.
2. Add Tier 2 families incrementally (#4-10) — each is a bounded, mostly-independent unit of
   work once the engine plumbing exists.
3. Treat Tier 3 as a separate design task, not a continuation of the dataset-family pattern.

## Engineering note for whoever builds this

Every family above names its **curated list** for anything that could otherwise drift into
scientifically wrong territory if left to pure randomization (species names, substances,
materials, scenario framing). Keep those lists as small, explicit, version-controlled data
(e.g. `backend/app/services/question_families/<family>/fixtures.py` or a JSON fixture file per
family) — never let a family's parameter generator invent a substance/species/material name or
a numeric relationship that isn't backed by the fixture list or a real physical-constant lookup.
This is the same principle as section 1 of `PROJECT_STATUS.md` applied one level down: the
*standards* aren't invented by a model, and neither should the *science inside a generated
dataset* be.
