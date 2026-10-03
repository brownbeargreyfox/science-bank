# EOCEP Constraints for the New Biology 1 Families — Design

Date: 2026-10-03

Status: Design approved in chat (Brandon, 2026-10-03); written specification awaiting review.

## Goal

Enable existing EOCEP Practice mode for the three deployed Biology 1 families that currently reject it:

| Standard | Family | EOCEP selected-response templates |
|---|---|---|
| B-LS1-1 | `dna-protein-synthesis` | `gene_activity_by_cell` only |
| B-LS3-2 | `mutation-effects` | `identify_mutation_type`, `new_protein_after_change`, `effect_on_protein`, `inheritance_of_mutation` |
| B-LS4-4 | `natural-selection-trend` | `compare_survival`, `trait_trend`, `effect_of_change`, `explain_adaptation`, `predict_new_change` |

The source is *EOCEP Biology 1 Assessment Specifications 2025–2026*, committed as
`SCDoE Targets/State Assessment Specifications_EOCEP Biology 1_2025-2026.pdf`. This work imports its item-writer
constraints into `biology-1-eocep.json`, then uses the existing server-side EOCEP template filter. It does not change
question content, family code, the frontend, schema, or a deployed family version.

EOCEP Practice remains targeted practice, not a claim that any one family fully represents a standard or the state
assessment. In particular, `mutation-effects` does not add the separate B-LS3-2 meiosis-model work.

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
and may show understanding of differentiation's result in specialized systems.

The three selected-response sequence templates are declared under
`excluded_templates["dna-protein-synthesis"]`: `transcribe_mrna`, `translate_mrna`, and `dna_to_protein`. Their current
student-facing output uses prohibited `3′/5′` notation. The existing universal constructed-response exclusion blocks
`explain_dna_to_protein`; it need not be repeated in JSON. `gene_activity_by_cell` is the only enabled template: it is
selected response, uses no prohibited notation, does not identify a real cell type or protein, and directly practises
the permitted differentiation result.

An explicit EOCEP request for any blocked template must return 422. An unfiltered EOCEP request must generate only
`gene_activity_by_cell`. Classroom output remains byte-for-byte unchanged.

### B-LS3-2 (source page 15)

The JSON entry records the complete page-15 terminology list: `allele`, `centromere`, `chromatid`, `chromosome`,
`codon (chart)`, `crossing over`, `daughter cell`, `deletion`, `diploid`, `DNA`, `fertilization`, `frameshift`,
`gamete`, `gene`, `gene mutation`, `genetic code`, `genetic variation`, `haploid`, `homologous chromosome`,
`independent assortment`, `insertion`, `meiosis`, `meiosis I`, `meiosis II`, `monosomy`, `mutagen`, `mutation`,
`nondisjunction`, `offspring`, `parent cell`, `point mutation`, `replication`, `sexual reproduction`, `somatic cell`,
`substitution`, `trait`, and `trisomy`. Its prohibitions are: do not require definition, identification, or sequencing
of named phases in meiosis I or II; and do not use the codon wheel. Its requirements record that a codon chart is
supplied when necessary; viable replication errors bypass DNA proofreading; and the assessment may use/ask about meiosis
models and their represented event order.

No `mutation-effects` selected-response template is excluded. They already use a displayed **codon chart**, never a
wheel, and do not name or sequence meiosis phases. The generic constructed-response exclusion blocks
`defend_claim_about_change`. The imported requirement about meiosis models describes assessment scope that this
sequence-mutation family does not attempt; it neither authorizes nonexistent meiosis items nor makes EOCEP Practice a
complete B-LS3-2 assessment.

### B-LS4-4 (source page 19)

The JSON entry records the complete page-19 terminology list: `abiotic`, `adaptation`, `advantageous trait`, `biotic`,
`coevolution`, `convergent evolution`, `distribution`, `diverge`, `ecosystem`, `fitness`, `gene`, `gene frequency`,
`gene pool`, `geographic isolation`, `natural selection`, `phenotypic variation`, `population`, `survival rate`,
`trait`, and `variation`. Its prohibitions are allele-frequency calculation, Hardy-Weinberg knowledge, and Chi-square
knowledge. The source states no additional B-LS4-4 requirement.

No `natural-selection-trend` selected-response template is excluded. It already reasons from counts/fractions of a
sampled population, never calculates allele frequency, and never mentions Hardy-Weinberg or Chi-square. The generic
constructed-response exclusion blocks `explain_with_data`.

## Enforcement and data contract

`data/standards/SC/2026-2027/biology-1-eocep.json` gains exactly these three constraint objects, with the existing
five fields: `source_pages`, `allowed_terminology`, `prohibitions`, `requirements`, and `excluded_templates`. The source
file, authority, and course slug stay unchanged.

The existing importer persists each object to `standards.eocep_constraints`. The existing
`services.generation.eocep_blocked_templates` combines the standard/family-specific exclusions with the universal
constructed-response exclusion. `generate_for_request` already rejects an explicitly requested blocked template and
substitutes the permitted set for an unfiltered EOCEP request; this work verifies those behaviours rather than adding a
parallel filter.

Because all newly enabled template output is existing output and classroom generation is unchanged, this is a
constraints-data change, not a generator-output change. No family version or golden digest changes.

## Tests

Update the importer/idempotency expected EOCEP count from 2 to 5. Replace the three present API assertions that EOCEP
is denied with tests that, for each standard:

- receive 200 and return the persisted source constraints in an EOCEP preview;
- generate only selected-response items when no template is requested;
- produce only the permitted template keys above over a multi-item preview;
- reject the constructed-response template with 422;
- for B-LS1-1, reject each of the three `3′/5′` sequence templates with 422 and prove the remaining activity template
  succeeds; and
- keep a classroom request for every excluded B-LS1-1 template successful, proving EOCEP filtering does not alter
  classroom generation.

Add structural assertions over the three JSON entries: exact source pages, the source-specific prohibitions, and the
expected exclusion lists. These catch a typo or a silently permissive empty object without duplicating the production
filter's logic.

The existing generic EOCEP test continues to prove that `question_types: ["constructed_response"]` is rejected, rather
than silently converted to another type.

## Out of scope

- Rewording B-LS1-1 sequence items to remove `3′/5′` notation. That is a broader family/engine design and would change a
  deployed family, requiring a version bump and new golden digest.
- New B-LS3-2 meiosis-model templates, its separate mutagen/replication dataset family, or truncating frameshifts.
- New Biology 1 questions, migrations, frontend changes, changes to the two already EOCEP-enabled families, or a claim
  of full EOCEP equivalence.
