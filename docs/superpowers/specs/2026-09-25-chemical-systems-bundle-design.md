# Stability & Change in Chemical Systems — Shared-Stimulus Design

Date: 2026-09-25  
Status: Proposed implementation

## Goal

Add the first deterministic **bundle generator** for the SCDE Chemistry bundle *Stability &
Change in Chemical Systems*. One generated magnesium-and-hydrochloric-acid investigation supplies
both C-PS1-5 reaction-rate questions and C-PS1-7 quantitative-conservation questions. It is one
shared student-facing stimulus, not two separately generated question sets displayed together.

## Scientific scope

The initial and only shared reaction is:

`Mg(s) + 2HCl(aq) → MgCl₂(aq) + H₂(g)`

It is already in the reviewed reaction-rate catalogue and meets C-PS1-5's two-reactant boundary.
The bundle scenario also stores exact atom counts, molar masses, coefficient-weighted side masses,
and a clean magnesium-to-hydrogen calculation. It excludes equilibrium, limiting reactants,
percent yield, gas-law calculations, solution-molarity calculations, and energy calculations.

The shared stimulus contains:

1. one experimental setup and balanced equation;
2. a concentration trial table and a temperature trial table for rate evidence; and
3. an atom/molar-mass table and dimensional-analysis path for conservation evidence.

No item claims that changing concentration or temperature changes the total mass predicted by the
balanced reaction. Rate and conservation are related through the same reacting system while
remaining distinct evidence paths.

## Alignment contract

The bundle family is bound to both `SC / chemistry / C-PS1-5` and `SC / chemistry / C-PS1-7`.
Each template declares its own bound standard code. Its observable citation is resolved only
against that standard:

| Template group | Standard | Evidence path |
|---|---|---|
| concentration/temperature patterns and collision explanation | C-PS1-5 | rate data and collision theory |
| coefficient/mole-mass calculation and conservation claim | C-PS1-7 | balanced atoms, moles, and mass |

Template-level binding is required. Validating every template against every family binding would
incorrectly accept or reject citations when a family spans standards.

## Generation and persistence contract

Bundle generation is a separate API path from ordinary single-standard generation. It accepts a
bundle ID, family key, seed, and existing filters. The API verifies that the requested family’s
complete bindings occur as non-partial PEs in that exact imported bundle.

`question_family_runs` gains a nullable `bundle_id`. Its existing required `standard_id` remains
the family’s stable anchor (C-PS1-5 for this initial family), preserving prior data and foreign-key
semantics. Every generated `questions` row uses the standard declared by its template, and every
question provenance snapshot records that exact standard and source document. All questions in a
group point to one `stimuli` row.

This preserves immutable question versions, assessment pinning, ownership, auditing, and ordinary
single-standard APIs. A bundle save is still one generation run owned by the saving teacher.

## UI contract

The Bundles page exposes **Generate shared stimulus** only when a supported generator covers a
bundle. Generate receives `bundle` and `family` query parameters, renders a bundle heading and the
two targeted standards, and otherwise retains the existing filter/preview/save controls. Question
cards visibly retain their own target code and observable-performance citation. Regeneration links
include the bundle ID so the exact set can be reproduced.

## Non-goals

- Adding a general-purpose authoring tool for arbitrary bundle combinations.
- Treating SCDE bundles as curriculum sequence or assessment specifications.
- Extending EOCEP mode; bundle generation is classroom-only.
- Rewriting or version-bumping either existing standalone Chemistry family.

