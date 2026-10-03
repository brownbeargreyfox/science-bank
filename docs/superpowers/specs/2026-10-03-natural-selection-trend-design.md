# Natural Selection Trend — B-LS4-4 Family Design

Date: 2026-10-03
Status: Design approved in chat with four refinements (Brandon, 2026-10-03). Written spec awaiting review.
Roadmap: Tier B in `docs/superpowers/plans/2026-09-29-coverage-roadmap.md` (B-LS4-4 flagged as a good candidate).

## Goal

Add `natural-selection-trend`, a deterministic question family for Biology 1 **B-LS4-4** (construct an explanation, based
on evidence, for how natural selection leads to adaptation of populations). Items give a curated, fictional case of a
population with two heritable variants of one trait, a table (and line chart) of how many individuals out of 100 sampled
have each variant over generations, and an environmental change partway through. Classroom-only. Biology 1 only: the
Biology 2 repeat-style standard B-LS4-3 stresses statistics and distributions, and gets its own templates later.

## Scientific scope

The Biology 1 boundary excludes allele frequency calculations. Items therefore speak only of **the fraction (or number
out of 100) of the population with a trait**, which is the wording of the standard's own reasoning bullet. No item
computes, names, or asks about allele or gene frequency, Hardy-Weinberg, genetic drift, gene flow, speciation, or
co-evolution. Every item treats selection as a **population-level change across generations**, never as individuals
changing because they need to.

Resistance cases are fictional and carry no health or treatment claim: a lab culture of a fictional soil bacterium and a
fictional growth-inhibiting compound, never an infection, a patient, a drug, or a person.

## Data: the case bank

Six curated cases. Each has: an organism (plural), a setting, a trait, two named variants, and two **events**, each a pair
of environments and the variant each favours. The two events run in opposite directions so the seed can change which
variant wins (no "second variant always wins" cue).

| Case | Variants | Event 1 | Event 2 | Kind |
|---|---|---|---|---|
| Ground beetles on a burned slope | dark / light shell | soil darkens after a fire: dark favoured | soil lightens as ash washes away: light favoured | abiotic |
| Soil bacteria in a lab culture (fictional) | resistant / not resistant to Compound Zeta | Zeta added to the culture: resistant favoured | Zeta removed: not resistant favoured | abiotic |
| Island finches | thick / thin beak | drought leaves mostly hard seeds: thick favoured | wet years bring soft seeds: thin favoured | abiotic |
| Snowshoe-style hares (fictional "marsh hares") | white / brown winter fur | long snowy winters: white favoured | snow-free winters: brown favoured | abiotic |
| Pond minnows (fictional) | quick / slow to flee | predatory fish added: quick favoured | predators removed: slow favoured | biotic |
| Desert shrubs | deep / shallow roots | dry years: deep favoured | wet years: shallow favoured | abiotic |

Each event gives two relative **survival rates**, one for the favoured variant (drawn from 0.74 to 0.90) and one for the
other (0.35 to 0.55); the rates are **drawn independently for each environment**, so the table is never a mirror image
of itself. Descriptions are plain, brief, and avoid any claim not needed for the item. Biotic and abiotic labels follow
standard usage.

## Scenario

`build_scenario(rng)` draws one case and one of its events (and so which variant is favoured first), then:

- **Generation table.** Variant counts out of exactly **100 sampled individuals** each generation, generations
  `0..G` with `G = L1 + L2`, where `L1` and `L2` are each 3 or 4. The first environment holds for the first `L1`
  transitions, then the environment changes (the intro states: "The environment changed after generation `L1`") and holds
  for `L2` more. Counts follow `p' = p*sa / (p*sa + (1-p)*sb)` per transition, with the count of the first variant rounded
  to an integer and the other set to `100 - count`.
- **Constraints.** Every displayed row totals exactly 100. Counts stay in `[2, 98]`. Each transition moves the favoured
  variant's count by at least 3. The first-environment favourite starts at 18 to 32 individuals, rises by at least 25 over
  phase 1 to at least 60 (clearly ahead when the change happens), and by the last generation has fallen by at least 20 from
  that peak to at most 45 (clearly behind), so "more common before" and "more common now" are never near 50/50. A draw that breaks any constraint is
  redrawn.
- **Survival experiment** (for `compare_survival`): a second small table, "Survival through one season in the first
  environment", with columns *Variant*, *Started*, *Survived*. Started counts are multiples of 5 from 40 to 85,
  `0 <= survived <= started`, and the two displayed survival rates (survived/started) differ by at least 0.15. The two groups never
  start with the same number (the "cannot be compared" choice says they differ). Half of the
  draws are **trap draws** where the variant with the higher rate has fewer survivors (so counts alone mislead); the other
  half have the higher-rate variant with more survivors.

All displayed numbers are stored in the scenario so every key is computed from exactly what the student sees.

## Templates

| Key | DOK | Type | Observable citation |
|---|---:|---|---|
| `compare_survival` | 1 | multiple_choice | `evidence[1]` — relative survival rates of organisms with different traits in a specific environment |
| `trait_trend` | 2 | multiple_choice | `reasoning[1]` — increasing gene/allele frequency results in an increasing fraction of the population expressing a trait |
| `effect_of_change` | 2 | multiple_choice | `evidence[0]` — changes in a population when some feature of the environment changes |
| `explain_adaptation` | 2 | multiple_choice | `reasoning[2]` — over time this leads to a population adapted to a particular environment |
| `predict_new_change` | 2 | multiple_choice | `reasoning[3]` — if abiotic/biotic factors change, there is potential for a change in gene/allele frequency again |
| `explain_with_data` | 3 | constructed_response | `reasoning[0]` — abiotic and biotic differences in ecosystems contribute to changes through natural selection |

Single-standard family: bound only to `SC / biology-1 / B-LS4-4`; no template declares a standard code.

### Item details

Choices are shuffled by the engine's deterministic `finalize_choices`. Each item has exactly four distinct choices and one
key; rationales cite the displayed numbers.

- **`compare_survival`** (shows the survival table): choices are four statements with different conclusions: "`{A}`
  had the higher survival rate."; "`{B}` had the higher survival rate."; "The two variants had the same survival rate.";
  "The survival rates cannot be compared, because the groups started with different numbers." The key follows survived /
  started for each variant. The rationales show both percentages.
- **`trait_trend`** (generation table and chart): asks how the fraction of the population with a named variant changed from
  generation 0 to the generation of the change. Choices: increased; decreased; stayed about the same; cannot be
  determined from the table. The key follows the displayed counts.
- **`effect_of_change`**: asks which variant became more common after the environment changed, comparing the generation of
  the change with the last generation. Choices: variant A; variant B; neither (the fractions did not change); both. The key
  follows the displayed counts.
- **`explain_adaptation`**: asks which statement best explains why the population changed after the environment changed.
  Choices name no variant, so the item does not give away `effect_of_change`. The key states the full chain: the population
  had **heritable variation** in the trait; in the new environment individuals with one variant **survived and reproduced
  more**; they **passed the trait to their offspring**; so the trait **became more common over the generations**.
  Distractors: individuals **changed their trait because they needed it** to survive; the environment itself made each
  offspring be born with the trait whatever its parents had; one variant is better in every environment, so it always
  increases. The word "need" appears only in that distractor and its rationale.
- **`predict_new_change`**: the stem states that the environment **reverses to its earlier conditions while all other
  conditions stay the same**, and asks for direction only (no percentage and no generation). Choices name no variant and are
  parallel (each hedged with "will tend to" and each giving a "because" reason), so the key is never the shortest, longest,
  or only hedged choice: the variant that *increased* before the change will tend to become more common again (the key;
  "more common before" was dropped because the first-favoured variant often starts as the minority); the variant that is
  now more common will tend to keep increasing; both will tend to stay the same because traits are fixed; every individual
  will tend to end up with the same trait.
- **`explain_with_data`**: asks for an explanation using the data, at the level of the population across generations and
  not of individuals changing because they need to. Rubric (4 points; model answer computed from the table): (1) the claim
  and the data (the fraction of the population with the variant rose from X to Y out of 100 over the generations after the
  change); (2) the population already had **heritable variation**: both variants existed and are passed to offspring
  (`evidence[2]`); (3) in the new environment individuals with that variant **survived and reproduced more** (fitness,
  `evidence[3]`); (4) because the trait is inherited, it **became more common over generations**, and individuals did not
  change because they needed to.

## Engine invariants and tests

Version 1.0.0, `QuestionFamily` subclass, `Rng` only, ambiguous draws redraw. `backend/tests/test_natural_selection.py`:

- **Independent checks of the data**: every displayed generation row totals exactly 100 and stays in `[2, 98]`; every survival
  row has an integer `0 <= survived <= started`; the two survival rates differ by at least 0.15; started counts are multiples
  of 5 from 40 to 85; each transition moves the favoured variant at least 3; the phase and reversal constraints hold; the
  favoured-variant assignment is recomputed from the case bank, not from the module's helper.
- **Independent keys**: every MC key is recomputed from the displayed numbers in the stimulus (rates from the survival table;
  direction from the generation table) and agrees; exactly one choice is true.
- **Trap coverage**: across 200 seeds, trap draws (higher rate, fewer survivors) and non-trap draws each occur in at least
  30% of `compare_survival` items.
- **Winner varies**: across 200 seeds, each of the two variants of a case wins after the change in a substantial share.
- **Position variation**: for every MC template, across 200 seeds, the correct answer appears in all four positions and no
  position holds more than 40% of keys (the engine's deterministic shuffle, not a length rule, controls position).
- **Leak test**: within one set, no item's stem or the shared intro contains another item's key text.
- **Direction-only guard**: `predict_new_change` contains no digits, percent signs, or generation numbers in its stem or
  choices, and its stem states that other conditions stay the same.
- **Chain guard**: every `explain_adaptation` key contains the words heritable (or "passed"), survived, reproduced, and
  "more common"; the key never contains "need"; "need" appears only in the needs-based distractor and its rationale; no stem
  or stimulus contains "need".
- **Vocabulary guards**: no text contains allele frequency, gene frequency, genetic drift, gene flow, Hardy, speciation;
  and none contains infection, disease, patient, treatment, medicine, drug, hospital, human, or antibiotic.
- Determinism, golden digest, the existing engine matrix; catalog and citations; the family appears under B-LS4-4 only (not
  Biology 2); EOCEP mode is rejected for B-LS4-4; mutation checks of the guards (planted banned word, planted needs-based
  key, a row that totals 99) each make a test fail.

## Files

Create `backend/app/services/families/natural_selection.py` and `backend/tests/test_natural_selection.py`. Modify
`registry.py`, `data/standards/SC/2026-2027/biology-1.json` (`question_family_candidate: true` on B-LS4-4),
`backend/tests/test_engine.py` (golden), `backend/tests/test_api.py` (generation matrix, EOCEP denial, Biology 2 mismatch,
the with-family list), and docs (`HANDOFF.md`, the coverage roadmap). No migration, no frontend change (the line chart and
tables already render).

Lab-culture wording: the bacteria case says "growth cycle" instead of "season", its intro explains why resistant bacteria
survive less well without Compound Zeta (they compete less well for food), and chart titles and the model answer never name
one variant as the trait.

## Out of scope

Allele or gene frequency calculations, Hardy-Weinberg, drift, gene flow, speciation, co-evolution, sexual selection,
multi-trait cases, real species data, EOCEP constraints for B-LS4-4, and Biology 2 B-LS4-3 templates.

## Open items

None blocking. The exact wording of the six cases is finalized in the implementation plan, using the table above as the
contract.
