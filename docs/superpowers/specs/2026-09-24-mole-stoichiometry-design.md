# Quantitative Conservation (Mole Stoichiometry) — C-PS1-7 Design

Date: 2026-09-24
Status: Implemented

## Goal

Add the deterministic classroom-only `quantitative-conservation` question family, displayed to
teachers as **Mole stoichiometry**, for South Carolina Chemistry C-PS1-7. Its purpose is to have
students use mathematical representations as evidence that atoms, and therefore mass, are
conserved in a chemical reaction. Mole and mass conversions are scaffolds toward that claim, not
the endpoint by themselves.

This family does **not** add EOCEP content or alter the Biology-only EOCEP mode.

## Scope and boundaries

- Bind only to `SC / chemistry / C-PS1-7`.
- Use a small, reviewed catalog of simple, already-balanced reactions. Exclude limiting reactants,
  percent yield, gas-law calculations, solution molarity, thermochemistry, equilibrium, and complex
  reactions.
- Derive every displayed molar mass from a fixed atomic-mass lookup and each question key from the
  same exact arithmetic displayed to students. Never invent a molar mass or round before the final
  displayed result.
- Use classroom mode only. The existing `generation_mode` remains unchanged; C-PS1-7 receives no
  EOCEP constraints.

## Scenario model

Each generated scenario owns one conservation problem and selects one curated reaction plus a
compatible measured quantity. Parameters store the balanced coefficients, formulae, species names,
atom counts, molar masses, a measured quantity, total system mass, exact intermediate values, and
unit paths. The scenario progresses coherently from equation → mole relationship → particle scale →
mass relationship → conservation claim.

The first catalog contains only clean, familiar equations with varied coefficient structures:

- `2H₂ + O₂ → 2H₂O`
- `N₂ + 3H₂ → 2NH₃`
- `2Mg + O₂ → 2MgO`
- `4Al + 3O₂ → 2Al₂O₃`
- `CH₄ + 2O₂ → CO₂ + 2H₂O`
- `2Na + Cl₂ → 2NaCl`

Decomposition, double replacement, limiting reactants, percent yield, solution molarity, gas laws,
and more formula-complex reactions are deferred until this family's invariants and classroom use
are proven.

The stimulus presents:

1. the balanced equation;
2. a compact species table with coefficient and molar mass; and
3. one stated measured quantity, in moles or grams.

Quantities are chosen so expected answers are clean at the stated precision. A single scenario can
support several templates without contradictory data.

## Templates

| Key | DOK | Type | Observable citation | Purpose |
|---|---:|---|---|---|
| `read_coefficients` | 1 | MC | representation[2] | Interpret coefficients as relative quantities of particles and moles. |
| `mole_mass_conversion` | 1 | MC | representation[1] | Complete one supporting mass↔mole step used later in the scenario. |
| `particle_scale` | 2 | MC | mathematical_modeling[0] | Bridge symbolic coefficients, moles, and particles/atoms. |
| `mass_of_product` | 2 | MC | mathematical_modeling[2] | Calculate another component's mass, then identify what that result shows about conservation. |
| `conservation_check` | 2 | MC | representation[3] | Select the mathematical evidence supporting conservation of atoms and mass. |
| `explain_conservation` | 3 | CR | analysis[0] | Use the scenario mathematics as evidence for the conservation claim. |

Distractors model common, specific errors: reversing coefficients, applying a coefficient to a molar
mass, skipping the grams↔moles conversion, and treating coefficients as masses. They must remain
numerically distinct from the correct answer.

## Verification

- Existing deterministic, cross-process, citation, output-shape, and golden-snapshot tests cover
  the new registered family.
- New C-PS1-7 invariants run across many seeds: equations are balanced; catalog molar masses match
  the atomic lookup; stated atom totals agree on both sides; calculated total reactant and product
  mass agree at the family-defined displayed precision; every numerical conversion retains a stored
  dimensional-analysis path (for example `g Mg → mol Mg → mol MgO → g MgO`); every keyed value is
  recomputed from stored parameters; MC choices are distinct; and generated text avoids excluded
  advanced topics.
- Every complete generated scenario includes at least one conservation-evidence template
  (`conservation_check` or `explain_conservation`), so template filtering cannot turn the family
  into a calculation-only worksheet without making that narrowing explicit.
- Add API coverage showing C-PS1-7 exposes this family and that a saved generation retains the
  ordinary provenance/ownership behavior already used by every family.

## Follow-on

After classroom use validates the family, it may become one component of a future shared Chemistry
stimulus for the **Stability & Change in Chemical Systems** bundle with `reaction-rate`. Bundle-driven
generation remains separate work.
