# Question Family Coverage Roadmap

Date: 2026-09-29
Status: Proposal for Nina's input. Ordering is a recommendation, not a ranking she has given.

## Where coverage stands

38 standards are imported (Biology 1: 14, Biology 2: 12, Chemistry: 12). Nine families are live:

| Family | Standard(s) |
|---|---|
| `population-carrying-capacity` | Biology 1 B-LS2-1 |
| `trait-probability` | Biology 1 B-LS3-3 |
| `reaction-rate` | Chemistry C-PS1-5 |
| `quantitative-conservation` | Chemistry C-PS1-7 |
| `reaction-outcome` | Chemistry C-PS1-2 |
| `chemical-system-stability` (bundle) | Chemistry C-PS1-5 + C-PS1-7 |
| `dna-protein-synthesis` | Biology 1 B-LS1-1 (built 2026-10-02; Biology 1 only, classroom-only) |
| `mutation-effects` | Biology 1 B-LS3-2 (built 2026-10-03; sequence-level mutation effects only; meiosis and mutagen data items still to do) |
| `natural-selection-trend` | Biology 1 B-LS4-4 (built 2026-10-03; Biology 1 only, classroom-only) |

That is 8 standards with a family. Biology 2 has none. Every question in the bank comes from a family, so
results tracking and variants (see `2026-09-29-results-and-variants-design.md`) only help standards that have
one. This roadmap is the parallel track.

Only B-LS2-1 and B-LS3-3 have EOCEP constraints imported (`biology-1-eocep.json`). A new Biology 1 family that
should support EOCEP practice mode needs its constraints structured from the state specification first.

## How to choose the next family

Priority is the units Nina named in the 2026-09-26 transcript, then reuse of existing generators, then the
remaining standards. Nina named: macromolecules, DNA and RNA, replication, protein synthesis, mutations,
carrying capacity, carbon cycling, human impacts on ecosystems, cell cycle, and anchoring phenomena such as
sickle cell and antibiotic resistance. One phrase near 09:28 in the transcript is unclear and is not treated
as a requirement.

Each new family must follow the existing rules: curated data only, every answer computed from the values the
student sees, each template citing an SCDE observable-performance bullet, DOK from the thinking required.

## Proposed order

### Tier A — Biology 1 units Nina named (recommended first)

| Standard | Topic | Nina's unit | Family shape | Notes |
|---|---|---|---|---|
| B-LS1-1 | DNA structure, protein synthesis | DNA/RNA, protein synthesis | Sequence-based: given a template strand, transcribe and translate; effects on the protein | **Built** as `dna-protein-synthesis` (Biology 1 only; Biology 2's deeper wording needs its own templates). B-LS3-2 can reuse `CODONS`/`translate` from `protein_synthesis.py`. |
| B-LS3-2 | Meiosis, variation, mutation | Mutations | Point-mutation outcome from a sequence (silent, missense, nonsense, frameshift) plus inheritance of variation | **First family built** as `mutation-effects` (sequence-level effects, frameshift taught; reuses the B-LS1-1 codon table). Meiosis and mutagen/replication-error dataset items remain. Shared with Biology 2. |
| B-LS1-6 | Macromolecules, matter and energy | Macromolecules | Classify monomer/polymer/element composition from structural data; dehydration synthesis and hydrolysis accounting | Needs a small curated molecule bank. |
| B-LS2-5 | Carbon cycle | Carbon cycling | Flux/pool data table and process identification | Curated pool-and-flux dataset; ties to the approved carbon-cycle sample item. |
| B-LS2-7 | Biodiversity, human impact | Human impacts on ecosystems | Evaluate a proposed solution against data; qualitative criteria | Design-and-evaluate standard; closer to a scenario family than a data family. |
| B-LS1-4 | Mitosis, cell cycle | Cell cycle | Model completion / sequencing; cell-count data | Approved sample item shows model completion, which needs a new question type. |

### Tier B — remaining Biology 1

B-LS1-5 (photosynthesis), B-LS1-7 (cellular respiration), B-LS4-1 (evidence for evolution), B-LS4-2 (natural
selection), B-LS4-4 (adaptation, flagged as a good candidate: gene-frequency change over generations) **(built as `natural-selection-trend`; Biology 2 B-LS4-3 still needs its own templates)**, B-LS4-5
(extinction and speciation). `natural-selection-trend` from the existing catalog serves both B-LS4-4 and
Biology 2 B-LS4-3.

### Tier C — Biology 2 (reuse first)

| Standard | Reuse |
|---|---|
| B-LS2-2 | Extends `population-carrying-capacity` to scale and resilience |
| B-LS2-4 | Trophic energy transfer (flagged candidate) |
| B-LS3-3 | Hardy-Weinberg on the `trait-probability` engine (flagged candidate) |
| B-LS4-3 | Shares the natural-selection family with B-LS4-4 |
| B-LS1-1, B-LS3-2, B-LS4-1 | Already covered by Biology 1 families once built (repeat PEs); check that the Biology 2 boundary is not narrower |
| B-LS2-3, B-LS2-6, B-LS2-8, B-LS3-1, B-LS4-6 | New scenario-style families; lowest priority |

### Tier D — Chemistry

| Standard | Notes |
|---|---|
| C-PS1-3 | Intermolecular forces (flagged candidate) |
| C-PS3-4 | Thermal equilibrium and calorimetry (flagged candidate) |
| C-PS1-1 | Periodic trends: cheap given the element data already in `reaction_outcome.py` |
| C-PS1-4, C-PS1-6, C-PS1-8, C-PS2-6, C-PS4-4, C-PS4-5 | Model-based or communication standards; scenario families later |

## Dependencies that affect ordering

- **Question types.** Nina approved sample items that use multiple-select, dropdown completion, model
  completion, cladogram and drag-and-drop. The engine only does multiple choice and constructed response.
  Families that lean on those formats (cell cycle, carbon-cycle dropdowns, cladograms) are better after a
  question-types slice.
- **Real data.** Nina asked for true scientific data with sources. Current stimuli are generated. Decide
  whether generated data is labelled as simulated, or a curated real-data bank with citations is built; either
  affects every data-driven family.
- **Canvas export.** Export compatibility depends on the question types above.
- **EOCEP constraints.** Structure the state-specification constraints for each Biology 1 standard before or
  with its family, so EOCEP practice mode stays accurate.
- **Variants.** Families with small parameter spaces yield few distinct variants; size each family's scenario
  bank with that in mind (aim for enough distinct scenarios per template to support several variants).

## Open questions for Nina

1. Which unit is she teaching next, so its family goes first?
2. Is Tier A's order right, or should macromolecules or the cell cycle come before DNA and mutations?
3. For Biology 2, which standards does she actually assess, and is Hardy-Weinberg wanted early?
4. For real data versus simulated data: which does she want when a family needs a dataset?
