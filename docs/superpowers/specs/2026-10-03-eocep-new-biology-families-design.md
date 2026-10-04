# EOCEP Constraints for the New Biology 1 Families — Design

Date: 2026-10-03 (amended 2026-10-04)

Status: Amended 2026-10-04 after a chat with Brandon that settled five decisions (listed below; the version decision was
settled while writing the plan). Written specification
awaiting Brandon's review. The earlier version of this spec (commit `9f1b2d1`) excluded three B-LS1-1 templates instead of
fixing them, had no content scan, no B-LS3-2 scope note, and no family code change; this amendment replaces it.

## Goal

Enable existing EOCEP Practice mode for the three deployed Biology 1 families that currently reject it:

| Standard | Family | EOCEP selected-response templates |
|---|---|---|
| B-LS1-1 | `dna-protein-synthesis` | `transcribe_mrna`, `translate_mrna`, `dna_to_protein`, `gene_activity_by_cell` |
| B-LS3-2 | `mutation-effects` | `identify_mutation_type`, `new_protein_after_change`, `effect_on_protein`, `inheritance_of_mutation` |
| B-LS4-4 | `natural-selection-trend` | `compare_survival`, `trait_trend`, `effect_of_change`, `explain_adaptation`, `predict_new_change` |

The source is *EOCEP Biology 1 Assessment Specifications 2025–2026*, committed as
`SCDoE Targets/State Assessment Specifications_EOCEP Biology 1_2025-2026.pdf`. Page numbers below are the printed numbers
in the page headers (PDF file page = printed page + 2).

EOCEP Practice remains targeted practice, not a claim that any one family fully represents a standard or the state
assessment.

## Decisions (Brandon, 2026-10-04)

1. **Enforcement is by test (not runtime, not a vocabulary allowlist).** Each standard's "items may not" rules are
   imported as machine-checkable `banned_terms`, and tests scan generated EOCEP output for them.
2. **B-LS3-2 is offered with a visible scope note**: the family covers the mutation part of the standard only; meiosis
   items are not yet available.
3. **The term lists are reference only, and items are not reworded to them.** The source heads each list "Terminology
   That Could Be Used": it names terms items may use, not the only terms allowed. Words such as "egg cell", "sperm cell",
   "inherited" and "variant" are plain-language and not prohibited. Only the "may not" rules are enforced.
4. **B-LS1-1 gets a narrow, family-level "no strand ends" rendering in EOCEP mode.** The EOCEP rules bar `3'/5'` in items
   that measure B-LS1-1, and every sequence template prints strand ends today. Rather than drop those templates or alter
   Classroom items, the family renders without ends when it is told it is in EOCEP mode.
5. **The family version stays 1.0.0** (see Generation). Classroom output is byte-identical for every seed.

## Source-derived constraints

### B-LS1-1 (source pages 3–4)

The JSON entry records the complete page-3 terminology list: `adenine`, `amino acid`, `anticodon`, `chromosome`,
`cytoplasm`, `cytosine`, `deoxyribose`, `differentiation`, `DNA`, `double helix`, `endoplasmic reticulum (SER & RER)`,
`enzyme`, `gene`, `Golgi apparatus`, `guanine`, `mRNA`, `mutation`, `nucleic acid`, `nucleotide`, `nucleus`, `nuclear
membrane`, `peptide bond`, `polypeptide`, `protein synthesis`, `ribose`, `ribosome`, `RNA`, `rRNA`, `start codon`,
`stop codon`, `thymine`, `transcription`, `translation`, `tRNA`, `uracil`, and `vesicle`. Its prohibitions state that an
item may not require:

- identifying specific cell types or proteins unless a description and function are supplied;
- protein structure beyond primary amino-acid sequence;
- post-translational modification;
- recall of which codons produce particular amino acids;
- biochemistry of protein synthesis (for example RNA polymerase);
- a codon wheel; or
- the terms `intron`, `exon`, `3'/5'`, `Okazaki fragment`, `initiation`, `elongation`, or `termination`.

Its requirements record that a codon chart is provided when needed, students apply the DNA/RNA base-pair rule and
translate sequences using that chart, students understand the general protein-synthesis process and ER/Golgi roles,
and may show understanding of differentiation's result in specialized systems of cells.

`excluded_templates` for this standard is empty. All four selected-response templates are enabled; the existing universal
constructed-response exclusion blocks `explain_dna_to_protein`.

`banned_terms`: `3'`, `5'` (matching the typographic prime `′` as well as the apostrophe, so `3′`, `5′`, `3'-`, and
`5' end` are all caught), `intron`, `exon`, `Okazaki`, `initiation`, `elongation`, `termination`, `codon wheel`.

### B-LS3-2 (source page 15)

The JSON entry records the complete page-15 terminology list: `allele`, `centromere`, `chromatid`, `chromosome`,
`codon (chart)`, `crossing over`, `daughter cell`, `deletion`, `diploid`, `DNA`, `fertilization`, `frameshift`,
`gamete`, `gene`, `gene mutation`, `genetic code`, `genetic variation`, `haploid`, `homologous chromosome`,
`independent assortment`, `insertion`, `meiosis`, `meiosis I`, `meiosis II`, `monosomy`, `mutagen`, `mutation`,
`nondisjunction`, `offspring`, `parent cell`, `point mutation`, `replication`, `sexual reproduction`, `somatic cell`,
`substitution`, `trait`, and `trisomy`. Its prohibitions are: do not require definition, identification, or sequencing
of named phases in meiosis I or II; and do not use the codon wheel. Its requirements record that a codon chart is
supplied when necessary; viable replication errors bypass DNA proofreading; and students use models of meiosis and
recognize and sequence the events they represent.

No `mutation-effects` selected-response template is excluded. They use a displayed codon **chart**, never a wheel, and
do not name or sequence meiosis phases. The generic constructed-response exclusion blocks `defend_claim_about_change`.
The meiosis-model requirement describes assessment scope this family does not attempt; it neither authorizes nonexistent
meiosis items nor makes EOCEP Practice a complete B-LS3-2 assessment. The entry therefore carries a `scope_note`:
"Covers the mutation part of this standard only; meiosis items are not yet available."

`banned_terms`: `prophase`, `metaphase`, `anaphase`, `telophase`, `codon wheel`.

### B-LS4-4 (source page 19)

The JSON entry records the complete page-19 terminology list: `abiotic`, `adaptation`, `advantageous trait`, `biotic`,
`coevolution`, `convergent evolution`, `distribution`, `diverge`, `ecosystem`, `fitness`, `gene`, `gene frequency`,
`gene pool`, `geographic isolation`, `natural selection`, `phenotypic variation`, `population`, `survival rate`,
`trait`, and `variation`. Its prohibitions are allele-frequency calculation, Hardy-Weinberg knowledge, and Chi-square
knowledge. The source states no additional B-LS4-4 requirement.

No `natural-selection-trend` selected-response template is excluded. It reasons from counts of a sampled population,
never calculates allele frequency, and never mentions Hardy-Weinberg or Chi-square. The generic constructed-response
exclusion blocks `explain_with_data`.

`banned_terms`: `allele frequenc` (stem match), `Hardy-Weinberg`, `Hardy Weinberg`, `chi-square`, `chi square`.

## Data contract

`data/standards/SC/2026-2027/biology-1-eocep.json` gains three constraint objects with the existing five fields
(`source_pages`, `allowed_terminology`, `prohibitions`, `requirements`, `excluded_templates`) plus:

- `banned_terms` (list of strings, above), used by tests only; and
- `scope_note` (string, optional), present for B-LS3-2 only.

The two already-enabled standards (B-LS2-1, B-LS3-3) are not changed. The source file, authority, and course slug stay
unchanged. The importer stores each object whole in `standards.eocep_constraints`, so the new fields need no importer
change; a test confirms they round-trip. Every generation response in EOCEP mode already returns the constraints and
stores them in the generation options, which carries `scope_note` into provenance.

## Generation: EOCEP rendering for B-LS1-1

`services.generation` stops rejecting these three standards (the rejection depends only on imported constraints, so the
JSON entries are what enable them). Biology 2 and standards without constraints are still rejected. Unfiltered EOCEP
requests still use every template that is not constructed response or listed in `excluded_templates`.

The generation mode reaches the families as an optional render setting. The contract, not the mechanism, is fixed here
(the plan chooses the mechanism):

- Seed derivation is unchanged, so one seed produces the same scenarios, items, keys and distractor kinds in both modes.
- Only `dna-protein-synthesis` reads the setting. `mutation-effects`, `natural-selection-trend` and every other family
  ignore it and produce byte-identical output in both modes.
- In EOCEP mode `dna-protein-synthesis` prints every strand, caption, stem, rationale and explanation without `3'`, `5'`
  or `′` notation, and says direction in words ("read left to right"). The codon table caption reads "Codon table
  (mRNA codons)". Distractor rationales that say "from the 5′ end" are reworded ("from the first codon").
- Each direction-dependent distractor (for example "reversed") is rechecked in the no-ends form; any that becomes
  ambiguous or that cues the key is replaced in EOCEP mode with a form that does not.
- The family version **stays 1.0.0**, and its golden digest in `tests/test_engine.py` does not change. The version feeds
  every sub-seed, so a bump would change every Classroom item for every seed; no existing output changes here (EOCEP
  output for this family has never been produced), so the version-bump rule is met without one. Provenance records the
  generation mode, which distinguishes EOCEP items. (Brandon, 2026-10-04.)
- Variants honour the parent's saved generation mode, so a variant of an EOCEP question is rendered without ends too.

## UI

The mode selector already exists. The Generate page shows a standard's `scope_note` near the mode selector when EOCEP is
selected and the standard has one, in the same plain wording as the rest of the page's EOCEP help text. The plan confirms
whether the page already receives the constraints before a preview; if not, the standard-detail response gains a
read-only `eocep_scope_note` and the generated API types (`frontend/openapi.json`, `frontend/src/api/schema.d.ts`) are
regenerated. No other UI change.

## Tests

Update the importer/idempotency expected EOCEP count from 2 to 5. Replace the three present API assertions that EOCEP
is denied with tests that, for each standard:

- receive 200 and return the persisted source constraints in an EOCEP preview;
- generate only selected-response items when no template is requested, over a multi-item preview;
- reject the constructed-response template with 422; and
- keep Biology 2 and unlisted standards rejected.

New guards:

- **Banned-term scan, per family.** Over many seeds, every template and every question type the mode allows, scan all
  student-facing text (stem, intro, stimulus title, captions, table cells, choices, rationales, explanation) for the
  standard's `banned_terms` (case-insensitive, whole-word where the term is a word). Each scan is proved by planting a
  banned word and watching the test fail, then restoring.
- **B-LS1-1 EOCEP scan is the substantive one**: a positive control proves the scan finds `3′/5′` in the family's
  Classroom output, and it passes on EOCEP output.
- **Codon chart sufficiency for B-LS1-1.** In EOCEP mode every codon the student must read appears in the displayed
  table, since EOCEP students are not expected to recall codons.
- **Classroom byte-identity for `dna-protein-synthesis`.** The existing golden digest of `generate_set(family, "golden", 12)`
  is unchanged and still passes, and the same seed gives the same template keys, answer letters, choice counts and DOK
  levels in Classroom and EOCEP mode (only the strand and caption text differ).
- **Other families unchanged in EOCEP mode**: `mutation-effects` and `natural-selection-trend` give identical questions in
  Classroom and EOCEP mode for the same seed and the permitted templates.
- **Scope note**: the B-LS3-2 EOCEP preview returns it and the saved provenance contains it; B-LS1-1 and B-LS4-4 have
  none.
- **Structural assertions over the three JSON entries**: exact source pages, the expected `banned_terms`, and empty
  exclusion lists, so a typo or a silently permissive entry fails.
- Variant of an EOCEP B-LS1-1 question contains no strand ends.

Before review, check the work against the recurring defect classes in `HANDOFF.md` (answer cues, contradicting
distractors, false premises, unenforced bounds, wording slips, test helpers that copy the module's logic).

## Out of scope

- Rewording items to the EOCEP term lists, or mode-aware vocabulary (decision 3).
- A runtime content check inside the engine, and a vocabulary allowlist.
- New B-LS3-2 meiosis-model templates, its separate mutagen/replication dataset family, or truncating frameshifts.
- ER, Golgi and other new B-LS1-1 item types the EOCEP source allows.
- Migrations, new Biology 1 questions, changes to the two already EOCEP-enabled families, changes to the deferred minor
  issues, re-verifying the source pages already recorded for B-LS2-1 and B-LS3-3, or any claim of full EOCEP equivalence.
- The earlier implementation plan (`2026-10-04-eocep-new-biology-families-plan.md`) and the uncommitted edits to
  `biology-1-eocep.json` and `backend/tests/test_api.py` match the superseded design (they exclude three B-LS1-1
  templates). They are replaced after this spec is approved, through the plan step, not by this document.
