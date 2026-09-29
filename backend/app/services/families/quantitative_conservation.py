"""C-PS1-7: quantitative evidence that atoms and mass are conserved.

All arithmetic starts as ``Fraction`` values. The scenario serializes only student-facing
numbers, after the exact calculations have been completed, so the stored representation is
also the source of truth used by each answer key.
"""

from fractions import Fraction
from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily

AVOGADRO = 6.022e23
ATOMIC_MASS: dict[str, Fraction] = {
    "H": Fraction(1),
    "O": Fraction(16),
    "N": Fraction(14),
    "Mg": Fraction(24),
    "Al": Fraction(27),
    "C": Fraction(12),
    "Na": Fraction(23),
    "Cl": Fraction(71, 2),
}

# (formula, classroom name, balanced coefficient, atoms per formula unit)
REACTIONS: dict[str, dict[str, Any]] = {
    "water": {
        "equation": "2H₂ + O₂ → 2H₂O",
        "species": (
            ("H₂", "hydrogen", 2, {"H": 2}),
            ("O₂", "oxygen", 1, {"O": 2}),
            ("H₂O", "water", 2, {"H": 2, "O": 1}),
        ),
    },
    "ammonia": {
        "equation": "N₂ + 3H₂ → 2NH₃",
        "species": (
            ("N₂", "nitrogen", 1, {"N": 2}),
            ("H₂", "hydrogen", 3, {"H": 2}),
            ("NH₃", "ammonia", 2, {"N": 1, "H": 3}),
        ),
    },
    "magnesium_oxide": {
        "equation": "2Mg + O₂ → 2MgO",
        "species": (
            ("Mg", "magnesium", 2, {"Mg": 1}),
            ("O₂", "oxygen", 1, {"O": 2}),
            ("MgO", "magnesium oxide", 2, {"Mg": 1, "O": 1}),
        ),
    },
    "aluminum_oxide": {
        "equation": "4Al + 3O₂ → 2Al₂O₃",
        "species": (
            ("Al", "aluminum", 4, {"Al": 1}),
            ("O₂", "oxygen", 3, {"O": 2}),
            ("Al₂O₃", "aluminum oxide", 2, {"Al": 2, "O": 3}),
        ),
    },
    "methane": {
        "equation": "CH₄ + 2O₂ → CO₂ + 2H₂O",
        "species": (
            ("CH₄", "methane", 1, {"C": 1, "H": 4}),
            ("O₂", "oxygen", 2, {"O": 2}),
            ("CO₂", "carbon dioxide", 1, {"C": 1, "O": 2}),
            ("H₂O", "water", 2, {"H": 2, "O": 1}),
        ),
    },
    "sodium_chloride": {
        "equation": "2Na + Cl₂ → 2NaCl",
        "species": (
            ("Na", "sodium", 2, {"Na": 1}),
            ("Cl₂", "chlorine", 1, {"Cl": 2}),
            ("NaCl", "sodium chloride", 2, {"Na": 1, "Cl": 1}),
        ),
    },
}

MISCONCEPTIONS = {
    "read_coefficients": ("coefficient_as_mass", "particle_ratio_literal", "coefficient_as_molar_mass"),
    "mole_mass_conversion": ("multiply_by_molar_mass", "skip_mass_to_moles", "ignore_displayed_molar_mass"),
    "particle_scale": ("omit_avogadro", "double_particle_count", "wrong_exponent"),
    "mass_of_product": ("skip_coefficient_ratio", "coefficient_as_mass", "stop_at_moles"),
    "conservation_check": ("molar_mass_comparison", "total_formula_units", "coefficient_presence"),
}


def molar_mass(atoms: dict[str, int]) -> Fraction:
    """Return an exact formula mass from the reviewed atomic-mass lookup."""
    return sum((ATOMIC_MASS[element] * count for element, count in atoms.items()), Fraction())


def atom_totals(rows: list[dict[str, Any]], split: int) -> dict[str, dict[str, int]]:
    """Independently total each element on the two sides of a balanced equation."""

    def total(side: list[dict[str, Any]]) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in side:
            for element, count in row["atoms"].items():
                result[element] = result.get(element, 0) + row["coefficient"] * count
        return result

    return {"reactants": total(rows[:split]), "products": total(rows[split:])}


def side_mass(rows: list[dict[str, Any]]) -> Fraction:
    """Return the exact coefficient-weighted mass of one equation side."""
    return sum((Fraction(row["coefficient"]) * Fraction(str(row["molar_mass"])) for row in rows), Fraction())


def _atom_text(atoms: dict[str, int]) -> str:
    return ", ".join(f"{element}: {count}" for element, count in sorted(atoms.items()))


def _number(value: Fraction) -> float:
    """JSON-safe student-facing value; all calculations occurred before this edge."""
    return float(value)


class QuantitativeConservation(QuestionFamily):
    key = "quantitative-conservation"
    version = "1.0.1"
    title = "Mole stoichiometry: quantitative conservation"
    description = (
        "Use balanced equations, moles, particles, and mass as quantitative evidence that matter is conserved."
    )
    stimulus_kind = "quantitative_conservation"
    bindings = (Binding("SC", "chemistry", "C-PS1-7"),)
    templates = (
        TemplateSpec(
            "read_coefficients", "Relative quantities in an equation", 1, "multiple_choice", "representation", 2
        ),
        TemplateSpec("mole_mass_conversion", "Mass and mole scaffold", 1, "multiple_choice", "representation", 1),
        TemplateSpec("particle_scale", "Moles and particle scale", 2, "multiple_choice", "mathematical_modeling", 0),
        TemplateSpec(
            "mass_of_product", "Mass relationship and conservation", 2, "multiple_choice", "mathematical_modeling", 2
        ),
        TemplateSpec(
            "conservation_check", "Quantitative conservation evidence", 2, "multiple_choice", "representation", 3
        ),
        TemplateSpec(
            "explain_conservation", "Explain conservation with mathematics", 3, "constructed_response", "analysis", 0
        ),
    )

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        reaction = rng.choice(sorted(REACTIONS))
        reaction_data = REACTIONS[reaction]
        rows = [
            {
                "formula": formula,
                "name": name,
                "coefficient": coefficient,
                "atoms": atoms,
                "atoms_per_formula_unit": _atom_text(atoms),
                "molar_mass": _number(molar_mass(atoms)),
            }
            for formula, name, coefficient, atoms in reaction_data["species"]
        ]
        given, asked = rows[0], rows[-1]
        extent = Fraction(rng.choice((1, 2, 3)))
        given_moles = extent * given["coefficient"]
        asked_moles = extent * asked["coefficient"]
        given_mass = given_moles * Fraction(str(given["molar_mass"]))
        asked_mass = asked_moles * Fraction(str(asked["molar_mass"]))
        totals = atom_totals(rows, 2)
        return {
            "reaction": reaction,
            "equation": reaction_data["equation"],
            "species": rows,
            "given": 0,
            "asked": len(rows) - 1,
            "given_moles": _number(given_moles),
            "asked_moles": _number(asked_moles),
            "given_mass": _number(given_mass),
            "asked_mass": _number(asked_mass),
            "dimensional_analysis": [
                f"g {given['formula']}",
                f"mol {given['formula']}",
                f"mol {asked['formula']}",
                f"g {asked['formula']}",
            ],
            "unit_path": f"g {given['formula']} → mol {given['formula']} → mol {asked['formula']} → g {asked['formula']}",
            "atom_totals": totals,
            "side_masses": {"reactants": _number(side_mass(rows[:2])), "products": _number(side_mass(rows[2:]))},
            "misconceptions": MISCONCEPTIONS,
        }

    def render_stimulus(self, p: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        totals = p["atom_totals"]
        return {
            "title": "Mole stoichiometry: evidence for conservation",
            "intro": f"In a closed system, students model {p['equation']}. The representation uses the same quantities as every answer key.",
            "sections": [
                {
                    "heading": "Quantitative representation",
                    "text": f"Calculation path: {p['unit_path']}. Complete-reaction mass: {p['side_masses']['reactants']:g} g reactants and {p['side_masses']['products']:g} g products. Atom totals: reactants {_atom_text(totals['reactants'])}; products {_atom_text(totals['products'])}.",
                    "table_index": 0,
                }
            ],
            "charts": [],
            "tables": [
                {
                    "caption": "Balanced reaction representation",
                    "columns": [
                        {"key": "formula", "label": "Substance"},
                        {"key": "coefficient", "label": "Coefficient (mol ratio)"},
                        {"key": "atoms_per_formula_unit", "label": "Atoms per formula unit"},
                        {"key": "molar_mass", "label": "Molar mass (g/mol)"},
                    ],
                    "rows": p["species"],
                }
            ],
        }

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params)

    @staticmethod
    def _choices(correct: str, wrongs: list[tuple[str, str]]) -> list[DraftChoice]:
        return [
            DraftChoice(correct, True, "Correct: this follows the balanced equation and displayed representation.")
        ] + [
            DraftChoice(text, False, f"{misconception}: this is a common coefficient, unit, or ratio error.")
            for text, misconception in wrongs
        ]

    @staticmethod
    def _rows(p: dict[str, Any]) -> list[dict[str, Any]]:
        return p["species"]

    def _q_read_coefficients(self, p: dict[str, Any]) -> DraftQuestion:
        a, b = self._rows(p)[0], self._rows(p)[-1]
        correct = f"{a['coefficient']} mol {a['formula']} reacts with {b['coefficient']} mol {b['formula']}."
        return DraftQuestion(
            "Which statement correctly interprets the coefficients as relative particle and mole quantities?",
            correct,
            "Coefficients compare formula units and the same relative numbers of moles.",
            self._choices(
                correct,
                [
                    (
                        f"{a['coefficient']} g {a['formula']} reacts with {b['coefficient']} g {b['formula']}.",
                        "coefficient_as_mass",
                    ),
                    (
                        f"One molecule of {a['formula']} always has {b['coefficient']} molecules of {b['formula']}.",
                        "particle_ratio_literal",
                    ),
                    ("The coefficients are the molar masses.", "coefficient_as_molar_mass"),
                ],
            ),
        )

    def _q_mole_mass_conversion(self, p: dict[str, Any]) -> DraftQuestion:
        a = self._rows(p)[0]
        correct = f"{p['given_moles']:g} mol {a['formula']}"
        return DraftQuestion(
            f"{p['given_mass']:g} g of {a['formula']} is used. What amount in moles is this supporting calculation?",
            correct,
            "Divide grams by the displayed molar mass before using the equation's coefficient ratio.",
            self._choices(
                correct,
                [
                    (f"{p['given_mass'] * a['molar_mass']:g} mol {a['formula']}", "multiply_by_molar_mass"),
                    (f"{p['given_mass']:g} mol {a['formula']}", "skip_mass_to_moles"),
                    (f"{p['given_moles'] * 3:g} mol {a['formula']}", "ignore_displayed_molar_mass"),
                ],
            ),
        )

    def _q_particle_scale(self, p: dict[str, Any]) -> DraftQuestion:
        a = self._rows(p)[0]
        particles = p["given_moles"] * AVOGADRO
        correct = f"About {particles:.3g} formula units of {a['formula']}"
        return DraftQuestion(
            f"What does {p['given_moles']:g} mol {a['formula']} represent at the particle scale?",
            correct,
            "One mole represents Avogadro's number of particles/formula units.",
            self._choices(
                correct,
                [
                    (f"About {p['given_moles']:.3g} formula units of {a['formula']}", "omit_avogadro"),
                    (f"About {particles * 2:.3g} formula units of {a['formula']}", "double_particle_count"),
                    (f"About {particles / 10:.3g} formula units of {a['formula']}", "wrong_exponent"),
                ],
            ),
        )

    def _q_mass_of_product(self, p: dict[str, Any]) -> DraftQuestion:
        a, b = self._rows(p)[0], self._rows(p)[-1]
        correct = f"{p['asked_mass']:g} g {b['formula']}"
        return DraftQuestion(
            f"Use {p['unit_path']}. What mass of {b['formula']} is predicted from {p['given_mass']:g} g {a['formula']}?",
            correct,
            "Convert mass to moles, use the coefficient ratio, then convert to mass; this is evidence within a conservation representation.",
            self._choices(
                correct,
                [
                    (f"{p['given_mass']:g} g {b['formula']}", "skip_coefficient_ratio"),
                    (f"{p['given_mass'] * 2:g} g {b['formula']}", "coefficient_as_mass"),
                    (f"{p['asked_moles']:g} g {b['formula']}", "stop_at_moles"),
                ],
            ),
        )

    def _q_conservation_check(self, p: dict[str, Any]) -> DraftQuestion:
        correct = "The equation has the same total number of each kind of atom on both sides, and coefficient-weighted masses agree for the complete reaction."
        return DraftQuestion(
            "Which quantitative observation is evidence that atoms and mass are conserved in this closed-system reaction?",
            correct,
            "Balanced atom counts and equal total mass support the conservation claim.",
            self._choices(
                correct,
                [
                    ("The product has a larger molar mass than one reactant.", "molar_mass_comparison"),
                    (
                        "The equation contains more product formula units than reactant formula units.",
                        "total_formula_units",
                    ),
                    ("The reaction has a coefficient larger than 1.", "coefficient_presence"),
                ],
            ),
        )

    def _q_explain_conservation(self, p: dict[str, Any]) -> DraftQuestion:
        a, b = self._rows(p)[0], self._rows(p)[-1]
        answer = (
            f"{p['given_mass']:g} g {a['formula']} is {p['given_moles']:g} mol. The coefficients convert this to "
            f"{p['asked_moles']:g} mol {b['formula']}, or {p['asked_mass']:g} g. The balanced equation keeps "
            "each element's atom count the same, so the quantitative relationships support conservation of atoms and mass in the closed system."
        )
        return DraftQuestion(
            f"Use the balanced equation and the path {p['unit_path']} to explain how the calculation supports conservation of atoms and mass.",
            answer,
            "A complete response states the conversion path, coefficient ratio, resulting mass, and why balanced atom counts support conservation.",
        )
