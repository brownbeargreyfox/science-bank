"""Shared C-PS1-5/C-PS1-7 stimulus for Stability & Change in Chemical Systems.

One magnesium + hydrochloric-acid investigation supplies rate evidence and an exact quantitative
conservation representation. The two evidence paths intentionally remain distinct: conditions
change rate, while balanced atoms and coefficient-weighted mass support conservation.
"""

from fractions import Fraction
from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily
from app.services.families import quantitative_conservation as conservation
from app.services.families import reaction_rate as rate

_RATE_TEMPLATES = {
    "rate_concentration_trend": "_q_concentration_trend",
    "rate_explain_temperature": "_q_explain_temperature",
}
_CONSERVATION_TEMPLATE_KEYS = {"mass_relationship", "conservation_claim", "explain_conservation"}


class ChemicalSystemStability(QuestionFamily):
    key = "chemical-system-stability"
    version = "1.0.0"
    title = "Stability & change: one chemical system"
    description = (
        "One magnesium-and-acid investigation links reaction-rate evidence with mathematical evidence that atoms and "
        "mass are conserved. Each item is aligned to C-PS1-5 or C-PS1-7."
    )
    stimulus_kind = "chemical_systems_shared"
    bindings = (Binding("SC", "chemistry", "C-PS1-5"), Binding("SC", "chemistry", "C-PS1-7"))
    templates = (
        TemplateSpec(
            "rate_concentration_trend",
            "Rate pattern: concentration",
            1,
            "multiple_choice",
            "evidence",
            0,
            "C-PS1-5",
        ),
        TemplateSpec(
            "rate_explain_temperature",
            "Rate explanation: temperature",
            2,
            "multiple_choice",
            "articulating_explanation",
            0,
            "C-PS1-5",
        ),
        TemplateSpec(
            "mass_relationship",
            "Mass relationship from the balanced equation",
            2,
            "multiple_choice",
            "mathematical_modeling",
            2,
            "C-PS1-7",
        ),
        TemplateSpec(
            "conservation_claim",
            "Quantitative conservation evidence",
            2,
            "multiple_choice",
            "representation",
            3,
            "C-PS1-7",
        ),
        TemplateSpec(
            "explain_conservation",
            "Explain conservation with mathematics",
            3,
            "constructed_response",
            "analysis",
            0,
            "C-PS1-7",
        ),
    )

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        rx = rate.REACTIONS["magnesium_hcl"]
        ref = rng.uniform(*rx["ref_range"])
        ea = round(rng.uniform(*rx["ea_range"]), -2)
        t_fixed, c_fixed = rx["fixed_temperature"], rx["fixed_concentration"]

        def measure(concentration: float, temperature: float) -> float:
            relative_rate = (concentration / c_fixed) * rate._k_factor(temperature, ea) / rate._k_factor(t_fixed, ea)
            noisy = relative_rate * (1 + rng.uniform(-0.03, 0.03))
            return round(ref * noisy, rx["decimals"])

        for _ in range(20):
            experiment1 = [{"concentration": c, "value": measure(c, t_fixed)} for c in rx["concentrations"]]
            experiment2 = [{"temperature": t, "value": measure(c_fixed, t)} for t in rx["temperatures"]]
            if rate.ReactionRate._monotone(rx, [row["value"] for row in experiment1]) and rate.ReactionRate._monotone(
                rx, [row["value"] for row in experiment2]
            ):
                break
        else:
            raise GenerationError("could not draw monotonic magnesium reaction-rate data")

        species = [
            {"formula": "Mg", "name": "magnesium", "coefficient": 1, "atoms": {"Mg": 1}},
            {"formula": "HCl", "name": "hydrochloric acid", "coefficient": 2, "atoms": {"H": 1, "Cl": 1}},
            {"formula": "MgCl₂", "name": "magnesium chloride", "coefficient": 1, "atoms": {"Mg": 1, "Cl": 2}},
            {"formula": "H₂", "name": "hydrogen", "coefficient": 1, "atoms": {"H": 2}},
        ]
        for row in species:
            row["atoms_per_formula_unit"] = ", ".join(f"{e}: {n}" for e, n in sorted(row["atoms"].items()))
            row["molar_mass"] = float(conservation.molar_mass(row["atoms"]))
        extent = Fraction(rng.choice((1, 2, 3)))
        given, asked = species[0], species[-1]
        given_moles, asked_moles = extent, extent
        given_mass = given_moles * conservation.molar_mass(given["atoms"])
        asked_mass = asked_moles * conservation.molar_mass(asked["atoms"])
        totals = conservation.atom_totals(species, 2)
        side_mass = lambda rows: float(conservation.side_mass(rows))  # noqa: E731
        return {
            "reaction": "magnesium_hcl",
            "model": {"ea_j_per_mol": ea, "reference_measurement": round(ref, 3)},
            "experiment1": experiment1,
            "experiment2": experiment2,
            "species": species,
            "atom_totals": totals,
            "side_masses": {"reactants": side_mass(species[:2]), "products": side_mass(species[2:])},
            "given_moles": float(given_moles),
            "asked_moles": float(asked_moles),
            "given_mass": float(given_mass),
            "asked_mass": float(asked_mass),
            "unit_path": "g Mg → mol Mg → mol H₂ → g H₂",
        }

    def render_stimulus(self, p: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        rx = rate.REACTIONS[p["reaction"]]
        keys = set(template_keys)
        sections: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        if keys - _CONSERVATION_TEMPLATE_KEYS:
            sections.extend(
                [
                    {
                        "heading": "Rate experiment: concentration",
                        "text": (
                            f"The concentration of hydrochloric acid changed while temperature stayed at "
                            f"{rx['fixed_temperature']}°C. Identical 3 cm magnesium strips were used in every trial."
                        ),
                        "table_index": len(tables),
                    },
                    {
                        "heading": "Rate experiment: temperature",
                        "text": (
                            f"Temperature changed while hydrochloric acid stayed at {rx['fixed_concentration']:.2f} mol/L. "
                            "Identical 3 cm magnesium strips were used in every trial."
                        ),
                        "table_index": len(tables) + 1,
                    },
                ]
            )
            tables.extend(
                [
                    {
                        "caption": "Changing hydrochloric-acid concentration",
                        "columns": [
                            {"key": "concentration", "label": "Hydrochloric acid concentration (mol/L)"},
                            {"key": "value", "label": rx["measure_label"]},
                        ],
                        "rows": p["experiment1"],
                    },
                    {
                        "caption": "Changing temperature",
                        "columns": [
                            {"key": "temperature", "label": "Temperature (°C)"},
                            {"key": "value", "label": rx["measure_label"]},
                        ],
                        "rows": p["experiment2"],
                    },
                ]
            )
            charts.extend(
                [
                    rate.ReactionRate._chart(rx, "concentration", "Hydrochloric acid concentration (mol/L)", 0),
                    rate.ReactionRate._chart(rx, "temperature", "Temperature (°C)", 1),
                ]
            )
        if keys & _CONSERVATION_TEMPLATE_KEYS:
            totals = p["atom_totals"]
            sections.append(
                {
                    "heading": "Conservation representation",
                    "text": (
                        f"Calculation path: {p['unit_path']}. For one complete reaction set, reactants total "
                        f"{p['side_masses']['reactants']:g} g and products total {p['side_masses']['products']:g} g. "
                        f"Atom totals — reactants: {totals['reactants']}; products: {totals['products']}."
                    ),
                    "table_index": len(tables),
                }
            )
            tables.append(
                {
                    "caption": "Balanced-reaction quantities",
                    "columns": [
                        {"key": "formula", "label": "Substance"},
                        {"key": "coefficient", "label": "Coefficient (mol ratio)"},
                        {"key": "atoms_per_formula_unit", "label": "Atoms per formula unit"},
                        {"key": "molar_mass", "label": "Molar mass (g/mol)"},
                    ],
                    "rows": p["species"],
                }
            )
        return {
            "title": "Magnesium and hydrochloric acid: rate and conservation",
            "intro": (
                "Students investigate Mg(s) + 2HCl(aq) → MgCl₂(aq) + H₂(g). The same balanced reaction is used "
                "for every rate and conservation question."
            ),
            "sections": sections,
            "tables": tables,
            "charts": charts,
        }

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        if template.key in _RATE_TEMPLATES:
            return getattr(rate.ReactionRate(), _RATE_TEMPLATES[template.key])(params, rng)
        return getattr(self, f"_q_{template.key}")(params)

    @staticmethod
    def _choices(correct: str, wrongs: list[tuple[str, str]]) -> list[DraftChoice]:
        return [DraftChoice(correct, True, "Correct: it follows the displayed balanced representation.")] + [
            DraftChoice(text, False, f"{misconception}: this does not follow the displayed mole and mass relationships.")
            for text, misconception in wrongs
        ]

    def _q_mass_relationship(self, p: dict[str, Any]) -> DraftQuestion:
        correct = f"{p['asked_mass']:g} g H₂"
        return DraftQuestion(
            f"Use {p['unit_path']}. What mass of H₂ is predicted from {p['given_mass']:g} g Mg?",
            correct,
            "Convert Mg mass to moles, use the 1:1 coefficient ratio to H₂, then convert moles of H₂ to mass.",
            self._choices(
                correct,
                [
                    (f"{p['given_mass']:g} g H₂", "skip_mole_mass_conversion"),
                    (f"{p['asked_moles']:g} g H₂", "stop_at_moles"),
                    (f"{p['asked_mass'] * 2:g} g H₂", "coefficient_as_mass"),
                ],
            ),
        )

    def _q_conservation_claim(self, p: dict[str, Any]) -> DraftQuestion:
        correct = "Each element has the same total atom count on both sides, and the coefficient-weighted masses agree."
        return DraftQuestion(
            "Which observation from the mathematical representation supports the claim that atoms and mass are conserved?",
            correct,
            "The balanced atom totals and equal complete-reaction masses are quantitative conservation evidence.",
            self._choices(
                correct,
                [
                    ("The rate increased when the acid concentration increased.", "rate_for_mass"),
                    ("Magnesium chloride has a larger molar mass than magnesium.", "single_species_mass"),
                    ("Hydrochloric acid has a coefficient larger than 1.", "coefficient_presence"),
                ],
            ),
        )

    def _q_explain_conservation(self, p: dict[str, Any]) -> DraftQuestion:
        answer = (
            f"{p['given_mass']:g} g Mg is {p['given_moles']:g} mol Mg. The 1:1 coefficient relationship gives "
            f"{p['asked_moles']:g} mol H₂, or {p['asked_mass']:g} g H₂. The balanced equation has equal atom totals "
            "for Mg, H, and Cl, and its complete reactant and product masses are equal, so the mathematics supports "
            "conservation in the closed-system representation."
        )
        return DraftQuestion(
            f"Use {p['unit_path']} and the atom/mass table to explain how the mathematics supports conservation.",
            answer,
            "A complete response gives the conversion chain and connects equal atom totals and total mass to conservation.",
        )
