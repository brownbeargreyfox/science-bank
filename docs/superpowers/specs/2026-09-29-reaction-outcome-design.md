# Reaction Outcome Explanation — C-PS1-2 Family Design

Date: 2026-09-29
Status: Proposed implementation

## Goal

Add `reaction-outcome`, a new standalone deterministic question family for C-PS1-2 (construct and
revise an explanation for the outcome of a simple chemical reaction based on outermost electron
states, periodic-table trends, and patterns of chemical properties). It is the second family to
serve the *Stability & Change in Chemical Systems* bundle, alongside the existing
`chemical-system-stability` bundle generator (C-PS1-5/C-PS1-7) — but it does not touch that
generator's Mg+HCl stimulus. Its own varied reaction bank gives C-PS1-2 the parameter space a
single fixed reaction could not: explanations must generalize across several main-group reaction
types, not just restate one investigation.

## Scientific scope

C-PS1-2's clarification statement names sodium/chlorine, carbon/oxygen, carbon/hydrogen, and
biochemical reactions as examples; its state assessment boundary limits coverage to **main-group
elements and combustion reactions**. The curated reaction bank:

| Reaction | Equation | Bond type | Family pairing |
|---|---|---|---|
| sodium chlorine | 2Na + Cl₂ → 2NaCl | ionic | alkali metal + halogen |
| potassium bromine | 2K + Br₂ → 2KBr | ionic | alkali metal + halogen |
| magnesium oxygen | 2Mg + O₂ → 2MgO | ionic | alkaline-earth metal + oxygen family |
| calcium fluorine | Ca + F₂ → CaF₂ | ionic | alkaline-earth metal + halogen |
| carbon combustion | C + O₂ → CO₂ | covalent | combustion |
| methane combustion | CH₄ + 2O₂ → CO₂ + 2H₂O | covalent | combustion |
| hydrogen combustion | 2H₂ + O₂ → 2H₂O | covalent | combustion |

Each element entry stores valence-electron count, ion charge/tendency (loses, gains, or shares
electrons), and periodic family (alkali metal, alkaline-earth metal, halogen, other nonmetal) —
enough to derive bond type and product-formula ratio without any live physical calculation. A
separate, small **trend-comparison table** pairs elements from the same family across periods
(Na/K, F/Cl, Mg/Ca) with a stored trend statement, used only for reactivity-comparison questions.
This keeps reactivity claims to the relative, qualitative trends the state boundary permits — no
quantitative ionization-energy values.

Excluded: transition metals, non-main-group chemistry, quantitative electronegativity or
ionization-energy values, and any reaction outside the curated bank.

## Alignment contract

Single-standard family, bound only to `SC / chemistry / C-PS1-2`. No template declares a standard
code (the existing single-binding shorthand in `binding_for_template` applies, as in
`quantitative-conservation` and `reaction-rate`).

## Templates

| Key | DOK | Type | Observable citation |
|---|---:|---|---|
| `classify_bond_type` | 1 | multiple_choice | `articulating_explanation[1]` — bond type/number determined by valence electron states and electronegativity |
| `electron_transfer_count` | 1 | multiple_choice | `evidence[0]` — identification of products/reactants including valence electron arrangement |
| `predict_product_formula` | 2 | multiple_choice | `evidence[1]` — conservation of atom/ion counts before and after reaction |
| `compare_reactivity` | 2 | multiple_choice | `evidence[2]` — patterns of reactivity (e.g. alkali metal reactivity) via the periodic table |
| `reactivity_reasoning` | 2 | multiple_choice | `reasoning[0]` — valence electrons and electronegativity predict number/type of bonds |
| `explain_reaction_outcome` | 3 | constructed_response | `reasoning[1]` — revise/expand explanation given new evidence or context |

Answer keys are entirely categorical, derived from the scenario's own stored element data, never a
live physical calculation:

- **Bond type** — metal-vs-nonmetal classification already stored on each reactant.
- **Product formula ratio** — charge-balance arithmetic on stored ion charges (e.g. Mg²⁺ + O²⁻ →
  1:1; Ca²⁺ + F⁻ → 1:2).
- **Reactivity comparison** — a lookup into the trend-comparison table, with its stored trend
  statement as the rationale.

`compare_reactivity` and `reactivity_reasoning` draw their pair from the trend-comparison table
independently of which specific reaction the scenario drew, so a scenario always carries both a
reaction (for bond/formula templates) and a trend pair (for reactivity templates).

## File and registration

New `backend/app/services/families/reaction_outcome.py` implementing `QuestionFamily`, added to
the `FAMILIES` tuple in `backend/app/services/families/registry.py`. No changes to
`chemical_systems.py`, `quantitative_conservation.py`, or `reaction_rate.py`.

## Testing

Deterministic/golden tests in `backend/tests/test_engine.py`, following the existing per-family
pattern: a fixed seed produces an exact scenario dict and exact question text for each template,
so the tests fail on any silent numeric or wording drift. `sync_families`/
`validate_family_citations` already generically validate every family's observable citations
against the standards JSON; no changes needed there. `docker compose exec app python -m app.cli
bootstrap` (idempotent) registers the family in the database on next deploy.

## Non-goals

- Touching the existing Mg+HCl `chemical-system-stability` bundle generator or its stimulus.
- Adding transition-metal or non-main-group reaction chemistry.
- A bundle-level shared-stimulus API path; this is an ordinary single-standard family generated
  the same way `population-carrying-capacity` or `trait-probability` are.
- Extending EOCEP mode; C-PS1-2 has no EOCEP constraints imported and this family is
  classroom-only.
