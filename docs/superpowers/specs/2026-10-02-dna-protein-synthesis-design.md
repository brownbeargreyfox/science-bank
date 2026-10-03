# DNA to Protein — B-LS1-1 Family Design

Date: 2026-10-02
Status: Design approved in chat with two scope reductions (Brandon, 2026-10-02). Written spec awaiting review.
Roadmap: Tier A, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md` (B-LS1-1 first; B-LS3-2 reuses its codon data).

## Goal

Add `dna-protein-synthesis`, a deterministic question family for Biology 1 **B-LS1-1** (construct an explanation, based
on evidence, for how the structure of DNA determines the structure of proteins). It makes a short gene appear as a
DNA template strand, transcribes it to mRNA, and translates the mRNA into an amino acid sequence with a codon table
the student can see. It is classroom-only. Biology 1 only: Biology 2 lists B-LS1-1 as a repeat standard but expects
more depth (functional RNA, initiation/elongation/termination) and words its observable performances differently, so
it gets its own templates later.

## Scientific scope

Allowed: DNA template strand, complementary base pairing (A–U, T–A, G–C, C–G), mRNA, codons, start codon (AUG,
methionine), stop codon, amino acid sequence, "a single gene codes for a protein", and cells of one organism sharing
the same DNA while using different genes.

Excluded by the Biology 1 assessment boundary: specific cell or tissue types, whole body systems, specific protein
structures and functions, and the biochemistry of protein synthesis (no initiation, elongation or termination steps, no
tRNA or ribosome mechanics beyond "translation happens at the ribosome"). Genes are generic ("Gene R2"), never real
genes or named proteins.

Deliberately deferred to B-LS3-2: any item where a nucleotide changes and the student decides the effect on the
protein (silent, missense, nonsense, frameshift, or the unnamed equivalents). Neither a template nor a rubric point
asks for the effect of a change.

## Data

A small module-level table of the **standard genetic code** (64 codons → amino acid name or `Stop`), real data. No
live computation beyond pairing and lookup. Amino acids use their full names. AUG is shown as "methionine (start)",
and stop codons as "Stop", never as an amino acid.

## Scenario

`build_scenario(rng)` draws:

- a gene label (`Gene R2` style), generic;
- an mRNA coding sequence: `AUG` + `k` sense codons (`k` from 3 to 5) + one stop codon, so the template strand has
  15 to 21 nucleotides; no sense codon is `AUG` or a stop codon;
- the **template strand**, derived by pairing from that mRNA, displayed 3′→5′ left to right, with the mRNA read 5′→3′
  left to right (both labelled in the stimulus);
- the **key protein**: the amino acid names of the start and sense codons, in order (the stop codon ends it);
- a **codon table** (see rules) and, for the cell template, a small gene-activity table.

The scenario stores every displayed value (strand, mRNA, table rows, activity table) so keys are computed from exactly
what students see.

### Codon table rules (exact and self-contained)

- The stimulus states: "Use the codon table shown. You do not need to memorize codons."
- The table lists, in alphabetical codon order (so order never hints at the key), **every codon needed to compute the
  key and every distractor** for the templates in the set, plus 2 or 3 extra codons so the table is not just the answer.
- Each row is `codon | amino acid`; AUG reads "methionine (start)" and stop codons read "Stop".
- A distractor is only built if every codon it uses is in the table; otherwise the draw is rejected and redrawn.
- Distractors must not equal the key, must not equal each other (the engine's duplicate-choice check), and must not be
  valid under another reading: the coding strand (the template's complement written as DNA) gives the **same** protein,
  so it is never used as a distractor.
- All choices state the reading direction (mRNA written 5′→3′) so a reversed string cannot be valid by direction.

## Templates

| Key | DOK | Type | Observable citation |
|---|---:|---|---|
| `transcribe_mrna` | 1 | multiple_choice | `evidence[4]` — through transcription, a DNA sequence is transcribed into a mRNA sequence |
| `translate_mrna` | 1 | multiple_choice | `evidence[5]` — through translation, a mRNA sequence is translated into an amino acid sequence at the ribosome |
| `dna_to_protein` | 2 | multiple_choice | `evidence[2]` — the sequence of genes contains instructions that code for proteins |
| `gene_activity_by_cell` | 2 | multiple_choice | `reasoning[3]` — as a result of differentiation, different genes are activated in different cells that share the same genetic code |
| `explain_dna_to_protein` | 3 | constructed_response | `articulating_explanation[0]` — regions of DNA (limited to genes) determine the structure of proteins |

Single-standard family: bound only to `SC / biology-1 / B-LS1-1`; no template declares a standard code.

### Item details

- **`transcribe_mrna`**: stem shows the template strand; choices are mRNA strings (5′→3′). Key is the pairing. Distractors:
  T kept instead of U; the template copied as if it were mRNA (U substituted); the key reversed; one wrong pair swapped
  (A↔U exchanged for G↔C). Needs no table.
- **`translate_mrna`**: stem shows the mRNA (5′→3′, starting at AUG) and the table; choices are amino acid sequences
  joined with arrows. Key follows the codons in order. Distractors: key in reverse order; the mRNA's codons read with
  each codon's letters reversed; the template strand's letters read as if they were an mRNA (T written as U). Each
  uses only codons added to the table. Rejected if any distractor hits a stop codon before its end.
- **`dna_to_protein`**: stem shows only the template strand and the table; choices are amino acid sequences. Key is the
  two-step result. Distractors: the template read directly as codons; the key reversed; the mRNA codons with their
  letters reversed.
- **`gene_activity_by_cell`**: stimulus says cell types P and Q come from the same organism and contain the same DNA, and
  shows a gene-activity table (four generic genes × P and Q, "active" or "not active"). Stem: which statement is
  supported by the table. Four choices each assert a category (only in P, only in Q, both, neither) for a different
  gene; exactly one matches the table. Explanation links the result to differentiation. No real cell types.
- **`explain_dna_to_protein`**: stem asks the student to use the table to explain how the template strand of the gene
  determines the amino acid sequence of its protein, including the mRNA and the amino acid sequence. Rubric
  (three points, answer field holds the model answer): (1) the template strand is transcribed into a complementary mRNA
  by base pairing; (2) the mRNA is read in groups of three (codons) and each codon specifies an amino acid per the
  table; (3) the order of amino acids is the protein's sequence, so the DNA sequence determines the protein. The model
  answer is computed from the scenario.

## Engine invariants and tests

Follows `QuestionFamily` (see `reaction_outcome.py`): SHA-256 sub-seeds via `Rng`, ambiguous draws raise
`GenerationError` and redraw, MC items have one key with distinct choices and rationales. Version 1.0.0; any later
output change bumps the version and updates the golden tests in the same commit.

`backend/tests/test_protein_synthesis.py`:

- Determinism: same seed gives identical output; different seeds differ; golden snapshot of one fixed seed.
- Independent checker: the test re-derives the mRNA, protein and keys from the displayed strands with its own pairing
  and codon dictionary (not imported from the family) and asserts every key and rationale agrees, across many seeds
  (at least 200 scenarios) and all templates.
- Table exactness: every codon used by any choice appears in the displayed table; the table never marks a stop codon as
  an amino acid; AUG reads as methionine (start).
- Distractor safety: no distractor equals the key; the coding-strand string never appears as a distractor; every
  `transcribe_mrna` choice is labelled 5′→3′; no choice repeats.
- Scope guard: no stem, choice, rationale, or explanation contains the words mutation, frameshift, silent, missense,
  nonsense, or initiation/elongation/termination.
- `gene_activity_by_cell`: exactly one choice is true by an independent reading of the table, over many seeds.
- Bounds: strand lengths 15 to 21 nucleotides, `k` from 3 to 5, no sense codon is AUG or a stop codon.
- Catalog and citations: `sync_families` passes `validate_family_citations` for biology-1; the family appears under
  B-LS1-1 only; Biology 2 B-LS1-1 does not list it; EOCEP mode is rejected for B-LS1-1 (no constraints imported).
- The existing parametrized engine tests (`test_engine.py`, `test_api.py` generation matrix) include the new family.

## Files

Create `backend/app/services/families/protein_synthesis.py` and `backend/tests/test_protein_synthesis.py`. Modify
`backend/app/services/families/registry.py` (register), `backend/tests/test_api.py` (add the family to the generation
parametrization), and docs: `HANDOFF.md` (family table), `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`
(B-LS1-1 built; B-LS3-2 can reuse the codon data), `QUESTION_FAMILY_CATALOG.md` if it lists families. No migration, no
frontend change (tables are generic). Families sync at bootstrap.

## Out of scope

Sequence-change effects (B-LS3-2), EOCEP constraints for B-LS1-1 (a separate small step from the Assessment
Specifications pages), Biology 2 templates, real genes or proteins, diagrams of the ribosome, drag-and-drop or
dropdown question types.

## Open items

None blocking. The gene-activity table size (four genes) and the extra-codon count (2 or 3) are tunable during
implementation without a version bump if reviewed before release.
