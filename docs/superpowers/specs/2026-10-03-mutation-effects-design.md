# Mutation Effects — B-LS3-2 Family Design

Date: 2026-10-03
Status: Design approved in chat with three added rules (Brandon, 2026-10-03). Written spec awaiting review.
Builds on: `2026-10-02-dna-protein-synthesis-design.md` (reuses its genetic code, helpers, and table rules).

## Goal

Add `mutation-effects`, a deterministic question family for Biology 1 **B-LS3-2** (make and defend a claim, based on
evidence, that inheritable genetic variation may result from meiosis, replication errors, and/or mutations caused by
environmental factors). This first B-LS3-2 family covers the **mutation** half at the sequence level: a one-nucleotide
substitution, insertion, or deletion in a gene, what it does to the mRNA and the protein, and whether it can be
inherited. Data-based claim items for meiosis and for mutagen/replication-error datasets are a later, separate
B-LS3-2 family. Classroom-only. Biology 1 only (Biology 2 lists B-LS3-2 as a repeat standard with different bullet
counts; it gets its own templates later).

## Scientific scope and vocabulary

Allowed (all on the SCDE terminology list for B-LS3-2): mutation, gene mutation, point mutation, substitution,
insertion, deletion, frameshift, codon, mutagen, replication, gamete, egg cell, sperm cell, somatic cell, inherited,
offspring. Students are **not asked to name** silent, missense, or nonsense changes (those words are not on the list):
effects are described in plain language.

Excluded by the Biology 1 boundary: the phases of meiosis and the biochemical mechanism of any step. No genes or
proteins are named. Mutagen examples are limited to ultraviolet light and X-rays; no health claims.

## Sequence model (applies to every item)

- A gene is shown as a **DNA template strand** (3′→5′, left to right). The mRNA is read 5′→3′ left to right and is
  derived by base pairing.
- **Translation starts at the displayed start codon (AUG) and proceeds in groups of three until the first in-frame
  Stop.** This sentence is part of every item that translates, and every stem or stimulus shows enough downstream
  sequence for the result to be determinate.
- Each gene is: `AUG` + 3 or 4 sense codons + one stop codon + a **downstream tail** of 4 to 5 further codons (any
  codons, including stops, which are never read in the original). The tail gives indel draws somewhere to read.
- A **determinate** translation is one that meets a first in-frame Stop within the displayed full codons. A draw is
  rejected when any translation the item needs (original, changed, or a distractor) never meets a Stop within the
  displayed codons, or would end in a partial codon. No item ever asks about a partially displayed codon.

## The mutation

One edit to the template strand at a declared 1-based position, inside the sense codons (never the start codon, the
original stop codon, or the tail):

- **substitution**: one nucleotide replaced by a different nucleotide;
- **insertion**: one nucleotide added;
- **deletion**: one nucleotide removed.

Invariant (tested independently): applying the declared edit (`type`, `position`, and the nucleotide involved) to the
displayed original strand gives exactly the displayed changed strand, and the two strands differ by that single edit
only (Hamming distance 1 with equal length for a substitution; length difference 1 for an indel). Indel draws are
rejected when the same changed strand could come from an edit at a different position (a deleted base equal to a
neighbour, an inserted base equal to the base before or after), so "at the stated position" is never ambiguous.

## Effect categories (mutually exclusive by construction)

Let `O` be the original protein and `N` the changed protein (amino acid names, read by the sequence model above). Four
predicates, each defined from `O` and `N` alone:

| Category | Predicate | Allowed mutation |
|---|---|---|
| unchanged | `N == O` | substitution |
| one changed | same length and exactly one position differs | substitution |
| ends early | `N` is a proper prefix of `O` (a new in-frame Stop) | substitution |
| several differ | `len(N) >= len(O)`, `N` is not a prefix of `O`, and at least two positions differ in the overlap | insertion or deletion |

The four predicates are pairwise disjoint (different length relations or different difference counts). A kept scenario
has exactly one true predicate, and it must be the one allowed for its mutation type. Any draw where **no** predicate
is true (for example an insertion that only makes the protein longer with no difference in the overlap) or where an
indel falls into "ends early" is rejected. So a frameshift scenario used for "several amino acids after the change
differ" never also introduces an early stop; early-stop cases come only from substitutions that create a Stop.

## Data

Reuses `CODONS`, `AMINO_ACIDS`, `translate`-style reading, `transcribe`/`template_for`, `strand_text`, and `table_label`
from `protein_synthesis.py` (imported, not copied). New: a curated inheritance table (below). The codon table follows
the B-LS1-1 rules: alphabetical, every codon any translation in the set reads (original, changed, distractors) plus 2
or 3 extras, `AUG` labelled `Methionine (start)`, stops labelled `Stop`, the stimulus tells students to use the
displayed table and not to memorize codons. Table size is bounded at 36 rows including the 2 or 3 extras, and the bound is enforced (a scenario whose needed codons would exceed 33 is redrawn): a
prototype over 1500 seeds needed at most 31 codons with this gene shape, while genes of 4 to 5 sense codons with a 6 to 8
codon tail needed up to 39 and were rejected as too long to display.

## Scenario

Independent genes per role, so no item's stem leaks another item's key: `classify`, `protein`, `effect`, and `claim`
(each with its own original strand, changed strand, declared mutation, and cause). Roles:

- `classify`: any mutation type, with a cause (a copying error during DNA replication, or exposure to a mutagen: ultraviolet
  light or X-rays).
- `protein`: any type, with `N != O` (so the original protein is never the key).
- `effect`: any type, with its category from the table above (substitution cases are drawn evenly among unchanged, one
  changed, ends early, and indels give several differ).
- `claim`: any type and category; used by the constructed-response item.
- `inheritance`: an organism (a mouse, a fruit fly, a zebrafish; animals only, so the somatic/gamete distinction is clean), a cell kind (body cell or gamete: egg cell or sperm
  cell), and a mutagen.

## Templates

| Key | DOK | Type | Observable citation |
|---|---:|---|---|
| `identify_mutation_type` | 1 | multiple_choice | `evidence[1]` — genetic mutations can occur due to replication errors and environmental factors (mutagen) |
| `new_protein_after_change` | 2 | multiple_choice | `reasoning[0]` — genetic mutations produce genetic variation between cells or organisms |
| `effect_on_protein` | 2 | multiple_choice | `reasoning[0]` — genetic mutations produce genetic variation between cells or organisms |
| `inheritance_of_mutation` | 2 | multiple_choice | `reasoning[1]` — genetic variations produced by mutation and meiosis can be inherited |
| `defend_claim_about_change` | 3 | constructed_response | `reasoning[2]` — defend a claim against counterclaims |

Single-standard family: bound only to `SC / biology-1 / B-LS3-2`; no template declares a standard code.

### Item details

- **`identify_mutation_type`**: stem gives the cause and shows the original and changed template strands. Choices: the
  substitution, the insertion, the deletion (each with a plain description, such as "one nucleotide was replaced by
  another"), and "No mutation occurred, because the protein is not changed." The key follows the displayed strands. The
  fourth choice is a stated misconception: a changed DNA sequence is a mutation whether or not the protein changes.
- **`new_protein_after_change`**: stem shows both strands (original and changed) and the table, and states the
  sequence-model sentence. Choices are amino acid sequences joined with arrows. The key is the changed protein. Distractors:
  the original protein (nothing changed); wrong sequences drawn from: the original protein, the original with the amino acid at the change site left out, the
  original with extra amino acids added at the end (indels), the protein one amino acid too long (a substitution that
  makes a Stop), the changed amino acid in the wrong place, and the key's amino acids rearranged. Three are chosen so that
  every choice starts with methionine and at least one has the key's length (no start or length giveaway); none equals the
  key or another choice. The earlier "changed strand read directly as codons" distractor was dropped: it always began with
  tyrosine, which the stated start-codon rule rules out at a glance.
- **`effect_on_protein`**: stem shows both strands and the table. Four fixed-wording choices, each true only for its
  category: "The protein is unchanged."; "Exactly one amino acid is different."; "The protein ends early, because a new Stop
  codon is read."; "Several amino acids after the change are different." The key is the category the scenario computed;
  the other three are false by the predicates above.
- **`inheritance_of_mutation`**: stem names the organism, the cell kind, and the mutagen exposure. The key is "can be
  passed to offspring" for a gamete that takes part in fertilization, and "will not be passed to offspring, although cells
  that come from the changed body cell carry it" for a body cell. Distractors are parallel in form and length (the key is never the
  longest or the only hedged choice) and none contradicts the stem: the opposite claim; "in every cell, but offspring will not
  inherit it"; "all offspring inherit it whether or not ...". A gamete is exposed to X-rays only, because ultraviolet light
  does not reach the gonads.
- **`defend_claim_about_change`**: stem shows both strands and the table and asks the student to make and defend a claim
  about what the change did to the protein, using the sequences and the table as evidence, and to answer a stated
  counterclaim. The counterclaim is "Every change in the DNA sequence changes the protein" when the effect is
  *unchanged*, and "A change of one nucleotide cannot change the protein" otherwise. Rubric (4 points, model answer
  computed): (1) a claim naming the type of change and its effect on the protein; (2) evidence from the displayed strands
  and codon table, and the derived amino acid sequences; (3) reasoning that the changed DNA changes the mRNA codons, which may change the amino
  acids, producing genetic variation (for an insertion or deletion, that the shifted codon grouping is a frameshift); (4) an answer to the counterclaim using that evidence.

### Teaching frameshift explicitly

For every insertion or deletion, each rationale, explanation, and model answer says plainly that adding or removing one
nucleotide shifts the way the codons are grouped, which is a **frameshift**, and then explains the resulting downstream
amino acid differences from the displayed sequences. The explanation stays at the level of codon grouping; it adds no
mechanistic detail about how the cell reads or repairs DNA.

## Engine invariants and tests

Version 1.0.0, `QuestionFamily` subclass, `Rng` only, ambiguous draws redraw (draw cap 400 per gene role, tested at the
200-seed level so no seed exhausts it). `backend/tests/test_mutation_effects.py`:

- Determinism, golden digest, the existing engine matrix includes the family.
- **Independent checker**: re-derives the original and changed mRNA and proteins from the displayed strands with the
  test's own by-amino-acid genetic code, applies the sequence-model rule, and asserts every key and rationale agrees,
  across at least 200 scenarios.
- **Single-edit invariant** for every role: the declared edit reproduces the changed strand, the strands differ by that
  single edit only, and indel edits are position-unambiguous.
- **Mutual exclusivity**: for every `effect_on_protein` item exactly one of the four predicates (computed independently
  in the test) is true, it matches the key, and indels are always "several differ" with no early stop.
- **Determinacy**: every translation any item needs meets an in-frame Stop within the displayed codons; no partial codon.
- **Table exactness**: every codon any choice or translation reads is displayed and correctly labelled; alphabetical; size
  within bound.
- Distractor safety, leak test (no item shows another item's key within a set), stimulus contains only what the chosen
  templates need, and `identify_mutation_type` always offers the four texts exactly once.
- **Vocabulary guard**: no stem, choice, rationale, explanation, or stimulus contains silent, missense, nonsense,
  initiation, elongation, termination, prophase, metaphase, anaphase, or telophase. The terms substitution, insertion,
  deletion, frameshift, mutagen, gamete, and somatic cell are allowed.
- Mutation checks of the guards (planted banned word, leaked key, dropped determinacy rejection each make a test fail).
- Catalog and citations: the family appears under B-LS3-2 only (not Biology 2); EOCEP mode is rejected for B-LS3-2.

## Files

Create `backend/app/services/families/mutation_effects.py` and `backend/tests/test_mutation_effects.py`. Modify
`registry.py` (register), `data/standards/SC/2026-2027/biology-1.json` (`question_family_candidate: true` on B-LS3-2),
`backend/tests/test_engine.py` (golden), `backend/tests/test_api.py` (generation matrix, EOCEP denial, Biology 2
mismatch, the with-family standards list), `backend/tests/test_coverage_api.py` only if it names B-LS3-2 as having no
family, and docs (`HANDOFF.md`, the coverage roadmap, `QUESTION_FAMILY_CATALOG.md`). No migration, no frontend change.

## Out of scope

Meiosis and mutagen/replication-error dataset items (next B-LS3-2 family), naming silent/missense/nonsense changes,
multi-nucleotide or chromosome-level mutations (nondisjunction, trisomy), EOCEP constraints for B-LS3-2, Biology 2
templates, real genes, proteins, or diseases.

## Open items

None blocking. Prototype figures (1500 seeds): effect role needs about 14 draws on average (167 at worst), protein role
about 11 (92), claim role about 3 (19); the draw cap of 400 leaves a wide margin.
