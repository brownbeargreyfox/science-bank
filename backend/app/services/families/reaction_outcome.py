"""C-PS1-2 (Chemistry): explain the outcome of a simple main-group or combustion reaction.

Every reaction comes from a small curated bank (state assessment boundary: main-group elements and
combustion). Each element stores only what students can see or look up on a periodic table — family,
metal/nonmetal, valence electrons, period — plus how many electrons an atom must lose, gain, or share
to reach a full outer energy level. Bond type, product-formula ratio, and reactivity comparisons are all
derived from those stored values; nothing is a live physical calculation and no ionization-energy or
electronegativity numbers appear anywhere.
"""

from math import gcd
from typing import Any

from app.services.engine.core import (
    Binding,
    DraftChoice,
    DraftQuestion,
    GenerationError,
    Rng,
    TemplateSpec,
)
from app.services.engine.family import QuestionFamily

_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")

# name, family, metal?, valence electrons, period, electrons lost (metal) / gained or shared (nonmetal) to
# reach a full outer energy level. Hydrogen fills the first energy level with two electrons, not eight.
ELEMENTS: dict[str, dict[str, Any]] = {
    "H": {"name": "hydrogen", "family": "other nonmetal", "metal": False, "valence": 1, "period": 1, "exchange": 1},
    "C": {"name": "carbon", "family": "other nonmetal", "metal": False, "valence": 4, "period": 2, "exchange": 4},
    "O": {"name": "oxygen", "family": "other nonmetal", "metal": False, "valence": 6, "period": 2, "exchange": 2},
    "F": {"name": "fluorine", "family": "halogen", "metal": False, "valence": 7, "period": 2, "exchange": 1},
    "Cl": {"name": "chlorine", "family": "halogen", "metal": False, "valence": 7, "period": 3, "exchange": 1},
    "Br": {"name": "bromine", "family": "halogen", "metal": False, "valence": 7, "period": 4, "exchange": 1},
    "Na": {"name": "sodium", "family": "alkali metal", "metal": True, "valence": 1, "period": 3, "exchange": 1},
    "K": {"name": "potassium", "family": "alkali metal", "metal": True, "valence": 1, "period": 4, "exchange": 1},
    "Mg": {
        "name": "magnesium",
        "family": "alkaline-earth metal",
        "metal": True,
        "valence": 2,
        "period": 3,
        "exchange": 2,
    },
    "Ca": {
        "name": "calcium",
        "family": "alkaline-earth metal",
        "metal": True,
        "valence": 2,
        "period": 4,
        "exchange": 2,
    },
}

# focus = the two elements whose product the bond/formula items ask about (metal listed first when ionic).
REACTIONS: dict[str, dict[str, Any]] = {
    "sodium_chlorine": {
        "equation": "2Na + Cl₂ → 2NaCl",
        "blurb": "Sodium metal reacts vigorously in chlorine gas, producing a white crystalline solid.",
        "focus": ("Na", "Cl"),
    },
    "potassium_bromine": {
        "equation": "2K + Br₂ → 2KBr",
        "blurb": "Potassium metal reacts violently with liquid bromine, producing a white crystalline solid.",
        "focus": ("K", "Br"),
    },
    "magnesium_oxygen": {
        "equation": "2Mg + O₂ → 2MgO",
        "blurb": "Magnesium ribbon burns in oxygen with a bright white flame, leaving a white powder.",
        "focus": ("Mg", "O"),
    },
    "calcium_fluorine": {
        "equation": "Ca + F₂ → CaF₂",
        "blurb": "Calcium metal reacts with fluorine gas, forming a white solid.",
        "focus": ("Ca", "F"),
    },
    "carbon_combustion": {
        "equation": "C + O₂ → CO₂",
        "blurb": "Carbon (charcoal) burns in oxygen, releasing carbon dioxide gas.",
        "focus": ("C", "O"),
    },
    "methane_combustion": {
        "equation": "CH₄ + 2O₂ → CO₂ + 2H₂O",
        "blurb": "Methane, the main component of natural gas, burns in oxygen, releasing carbon dioxide and water vapor.",
        "focus": ("C", "O"),
    },
    "hydrogen_combustion": {
        "equation": "2H₂ + O₂ → 2H₂O",
        "blurb": "Hydrogen gas burns in oxygen, producing water vapor.",
        "focus": ("H", "O"),
    },
}

# Same-family pairs used only for relative, qualitative reactivity comparisons.
TRENDS: tuple[dict[str, str], ...] = (
    {
        "less": "Na",
        "more": "K",
        "context": "Sodium (Na) and potassium (K) are both alkali metals in the same column of the periodic table.",
        "statement": "Reactivity of the alkali metals increases moving down the column.",
        "reason": (
            "A potassium atom's outermost electron is in a higher energy level, farther from the nucleus and more "
            "shielded by inner electrons, so it is lost more easily."
        ),
        "reversed": (
            "A potassium atom's outermost electron is in a lower energy level, closer to the nucleus, so it is lost "
            "more easily."
        ),
    },
    {
        "less": "Cl",
        "more": "F",
        "context": "Fluorine (F) and chlorine (Cl) are both halogens in the same column of the periodic table.",
        "statement": "Reactivity of the halogens decreases moving down the column.",
        "reason": (
            "A fluorine atom's outer energy level is closer to the nucleus and less shielded, so the nucleus attracts an "
            "incoming electron more strongly."
        ),
        "reversed": (
            "A fluorine atom's outer energy level is farther from the nucleus and more shielded, so the nucleus "
            "attracts an incoming electron more strongly."
        ),
    },
    {
        "less": "Mg",
        "more": "Ca",
        "context": "Magnesium (Mg) and calcium (Ca) are both alkaline-earth metals in the same column of the periodic table.",
        "statement": "Reactivity of the alkaline-earth metals increases moving down the column.",
        "reason": (
            "A calcium atom's outermost electrons are in a higher energy level, farther from the nucleus and more "
            "shielded by inner electrons, so they are lost more easily."
        ),
        "reversed": (
            "A calcium atom's outermost electrons are in a lower energy level, closer to the nucleus, so they are lost "
            "more easily."
        ),
    },
)

# Ratios offered as formula distractors (all in lowest terms, so none can equal a correct charge balance).
_RATIOS = ((1, 2), (2, 1), (2, 3), (3, 2), (1, 3), (3, 1), (1, 1))


def sub(n: int) -> str:
    return "" if n == 1 else str(n).translate(_SUBSCRIPTS)


def bond_type(a: str, b: str) -> str:
    """Metal + nonmetal transfers electrons (ionic); two nonmetals share them (covalent)."""
    metals = ELEMENTS[a]["metal"] + ELEMENTS[b]["metal"]
    if metals == 1:
        return "ionic"
    if metals == 0:
        return "covalent"
    raise GenerationError(f"metal-metal pair {a}/{b} is outside the curated bank")


def combine(a: str, b: str) -> tuple[int, int]:
    """Atoms of a and b per formula unit/molecule so electrons lost = gained (or shared totals match)."""
    ea, eb = ELEMENTS[a]["exchange"], ELEMENTS[b]["exchange"]
    g = gcd(ea, eb)
    return eb // g, ea // g


def formula_text(a: str, b: str, n_a: int, n_b: int) -> str:
    return f"{a}{sub(n_a)}{b}{sub(n_b)}"


def element_row(symbol: str) -> dict[str, Any]:
    e = ELEMENTS[symbol]
    return {
        "symbol": symbol,
        "name": e["name"].capitalize(),
        "family": e["family"],
        "type": "metal" if e["metal"] else "nonmetal",
        "valence": e["valence"],
        "period": e["period"],
    }


def _name(symbol: str) -> str:
    return ELEMENTS[symbol]["name"].capitalize()


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


class ReactionOutcome(QuestionFamily):
    key = "reaction-outcome"
    version = "1.0.0"
    title = "Reaction outcomes: electrons and the periodic table"
    description = (
        "Explain and predict the outcome of a simple main-group or combustion reaction from outer electron states: "
        "bond type, electrons lost, gained or shared, product formula, and same-family reactivity trends."
    )
    stimulus_kind = "reaction_outcome"
    bindings = (Binding("SC", "chemistry", "C-PS1-2"),)
    templates = (
        TemplateSpec(
            "classify_bond_type", "Ionic or covalent bond", 1, "multiple_choice", "articulating_explanation", 1
        ),
        TemplateSpec(
            "electron_transfer_count", "Electrons lost, gained, or shared", 1, "multiple_choice", "evidence", 0
        ),
        TemplateSpec("predict_product_formula", "Predict the product formula", 2, "multiple_choice", "evidence", 1),
        TemplateSpec("compare_reactivity", "Compare reactivity in a family", 2, "multiple_choice", "evidence", 2),
        TemplateSpec("reactivity_reasoning", "Explain a reactivity trend", 2, "multiple_choice", "reasoning", 0),
        TemplateSpec(
            "explain_reaction_outcome",
            "Explain and revise a reaction explanation",
            3,
            "constructed_response",
            "reasoning",
            1,
        ),
    )

    # ---- scenario ---------------------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        key = rng.choice(sorted(REACTIONS))
        a, b = REACTIONS[key]["focus"]
        n_a, n_b = combine(a, b)
        compare_i, reasoning_i = rng.sample(list(range(len(TRENDS))), 2)
        return {
            "reaction": key,
            "bond_type": bond_type(a, b),
            "focus": {"a": a, "b": b, "atoms_a": n_a, "atoms_b": n_b, "formula": formula_text(a, b, n_a, n_b)},
            "elements": [element_row(a), element_row(b)],
            "compare_pair": self._trend_params(compare_i),
            "reasoning_pair": self._trend_params(reasoning_i),
        }

    @staticmethod
    def _trend_params(index: int) -> dict[str, Any]:
        trend = TRENDS[index]
        rows = sorted((element_row(trend["less"]), element_row(trend["more"])), key=lambda r: r["period"])
        return {**trend, "rows": rows}

    # ---- stimulus ---------------------------------------------------------------------------

    _ELEMENT_COLUMNS = (
        {"key": "symbol", "label": "Symbol"},
        {"key": "name", "label": "Element"},
        {"key": "family", "label": "Family"},
        {"key": "type", "label": "Type"},
        {"key": "valence", "label": "Valence electrons"},
        {"key": "period", "label": "Period"},
    )

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        rx = REACTIONS[params["reaction"]]
        keys = set(template_keys)
        tables = []
        if keys & {
            "classify_bond_type",
            "electron_transfer_count",
            "predict_product_formula",
            "explain_reaction_outcome",
        }:
            tables.append(
                {
                    "caption": "Elements combining in the reaction",
                    "columns": list(self._ELEMENT_COLUMNS),
                    "rows": params["elements"],
                }
            )
        if "compare_reactivity" in keys:
            tables.append(
                {
                    "caption": "Two elements from the same family (comparison)",
                    "columns": list(self._ELEMENT_COLUMNS),
                    "rows": params["compare_pair"]["rows"],
                }
            )
        if keys & {"reactivity_reasoning", "explain_reaction_outcome"}:
            tables.append(
                {
                    "caption": "Two elements from the same family (reactivity pattern)",
                    "columns": list(self._ELEMENT_COLUMNS),
                    "rows": params["reasoning_pair"]["rows"],
                }
            )
        return {
            "title": "Outcomes of simple chemical reactions",
            "intro": f"{rx['blurb']} Balanced equation: {rx['equation']}",
            "sections": [],
            "tables": tables,
            "charts": [],
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_classify_bond_type(self, params, rng: Rng) -> DraftQuestion:
        f = params["focus"]
        a, b = f["a"], f["b"]
        A, B = _name(a), _name(b)
        equation = REACTIONS[params["reaction"]]["equation"]
        stem = (
            f"In the reaction {equation}, {A.lower()} atoms and {B.lower()} atoms combine to form {f['formula']}. "
            "Which statement correctly identifies the type of bonding and explains why?"
        )
        if params["bond_type"] == "ionic":
            correct = f"An ionic bond, because {a} atoms lose electrons and {b} atoms gain them."
            choices = [
                DraftChoice(
                    correct,
                    True,
                    f"Correct: {A} is a metal that loses its valence electrons and {B} is a nonmetal that gains them.",
                ),
                DraftChoice(
                    f"A covalent bond, because {a} atoms and {b} atoms share electrons equally.",
                    False,
                    "A metal atom has too few valence electrons to share; metals lose electrons to nonmetals instead.",
                ),
                DraftChoice(
                    f"An ionic bond, because {b} atoms lose electrons and {a} atoms gain them.",
                    False,
                    f"The direction is reversed: {A} is the metal, and metals lose electrons.",
                ),
                DraftChoice(
                    "No bond forms, because both elements are already neutral atoms.",
                    False,
                    "The equation shows a new substance forming, so bonds do form as electrons are rearranged.",
                ),
            ]
            explanation = (
                f"{A} is a metal with {ELEMENTS[a]['valence']} valence electron(s) and {B} is a nonmetal with "
                f"{ELEMENTS[b]['valence']}. Electrons transfer from the metal to the nonmetal, forming ions held together "
                "by an ionic bond."
            )
        else:
            correct = (
                f"A covalent bond, because {a} atoms and {b} atoms are both nonmetals that share electrons to fill "
                "their outer energy levels."
            )
            choices = [
                DraftChoice(correct, True, "Correct: two nonmetals each need electrons, so they share them."),
                DraftChoice(
                    f"An ionic bond, because {a} atoms lose electrons and {b} atoms gain them.",
                    False,
                    f"{A} is a nonmetal and does not lose its valence electrons to become a positive ion.",
                ),
                DraftChoice(
                    f"An ionic bond, because {b} atoms lose electrons and {a} atoms gain them.",
                    False,
                    f"{B} is a nonmetal and does not lose its valence electrons to become a positive ion.",
                ),
                DraftChoice(
                    "A metallic bond, because the electrons move freely between the atoms.",
                    False,
                    "Metallic bonding occurs between metal atoms; both of these elements are nonmetals.",
                ),
            ]
            explanation = (
                f"{A} and {B} are both nonmetals with {ELEMENTS[a]['valence']} and {ELEMENTS[b]['valence']} valence "
                "electrons. Neither loses electrons easily, so they share electrons in covalent bonds."
            )
        return DraftQuestion(stem=stem, answer=correct, explanation=explanation, choices=choices)

    def _q_electron_transfer_count(self, params, rng: Rng) -> DraftQuestion:
        f = params["focus"]
        symbol = rng.choice([f["a"], f["b"]])
        e = ELEMENTS[symbol]
        name = _name(symbol)
        n, v = e["exchange"], e["valence"]
        if e["metal"]:
            verb = "lose"
            question = f"how many electrons does each {name.lower()} atom lose to reach a stable arrangement?"
            why_correct = (
                f"Correct: a metal atom with {v} valence electron(s) loses all {n} to expose a full inner level."
            )
        elif params["bond_type"] == "ionic":
            verb = "gain"
            question = f"how many electrons does each {name.lower()} atom gain to fill its outer energy level?"
            why_correct = f"Correct: {name} needs {n} more electron(s) to fill its outer energy level."
        else:
            verb = "share"
            question = f"how many electrons must each {name.lower()} atom share with other atoms to fill its outer energy level?"
            why_correct = f"Correct: {name} needs {n} more electron(s), so it shares {n}."
        stem = f"A {name.lower()} atom has {_plural(v, 'valence electron')}. In forming {f['formula']}, {question}"

        def why(m: int) -> str:
            if m == v:
                return f"{m} is the number of valence electrons the atom already has, not the number it must {verb}."
            if m == 8 - v:
                return (
                    "Metal atoms do not build up toward a full set of eight; they lose their outermost electrons."
                    if e["metal"]
                    else f"{name} fills its first energy level with two electrons, so eight is not the target."
                )
            return f"{m} does not match the electrons {name.lower()} must {verb} to reach a full outer energy level."

        pool = []
        for m in (v, 8 - v, n + 1, n - 1, n + 2):
            if 1 <= m <= 8 and m != n and m not in pool:
                pool.append(m)
        correct = _plural(n, "electron")
        choices = [DraftChoice(correct, True, why_correct)] + [
            DraftChoice(_plural(m, "electron"), False, why(m)) for m in pool[:3]
        ]
        return DraftQuestion(
            stem=stem,
            answer=correct,
            explanation=f"{name} has {v} valence electrons and must {verb} {n} to reach a stable arrangement.",
            choices=choices,
        )

    def _q_predict_product_formula(self, params, rng: Rng) -> DraftQuestion:
        f = params["focus"]
        a, b, m, n = f["a"], f["b"], f["atoms_a"], f["atoms_b"]
        ea, eb = ELEMENTS[a]["exchange"], ELEMENTS[b]["exchange"]
        A, B = _name(a), _name(b)
        ionic = params["bond_type"] == "ionic"
        if ionic:
            stem = (
                f"{A} atoms lose electrons and {B.lower()} atoms gain electrons until every atom has a stable arrangement. "
                f"Using the number of electrons each atom loses or gains, which formula shows the compound formed "
                f"from {a} and {b}?"
            )
            balance = (
                f"Each {a} atom loses {ea} and each {b} atom gains {eb}, so {m} {a} and {n} {b} give "
                f"{m * ea} electrons lost = {n * eb} gained."
            )
        else:
            stem = (
                f"{A} atoms and {B.lower()} atoms share electrons so that every atom has a full outer energy level. Using the "
                f"number of electrons each atom must share, which formula shows the molecule formed from {a} and {b}?"
            )
            balance = (
                f"Each {a} atom shares {ea} and each {b} atom shares {eb}, so {m} {a} and {n} {b} give "
                f"{m * ea} = {n * eb} shared electrons."
            )
        correct = formula_text(a, b, m, n)
        pool = [r for r in _RATIOS if r != (m, n) and (ionic or r != (1, 1))]
        choices = [DraftChoice(correct, True, f"Correct: {balance}")]
        for p, q in pool[:3]:
            verb = "lost" if ionic else "shared by"
            other = "gained" if ionic else "shared by"
            choices.append(
                DraftChoice(
                    formula_text(a, b, p, q),
                    False,
                    (
                        f"{p * ea} electrons {verb} {a} do not equal {q * eb} electrons {other} {b}, "
                        "so the electron counts do not match."
                    ),
                )
            )
        return DraftQuestion(stem=stem, answer=correct, explanation=balance, choices=choices)

    def _q_compare_reactivity(self, params, rng: Rng) -> DraftQuestion:
        t = params["compare_pair"]
        more, less = t["more"], t["less"]
        correct = f"{_name(more)} ({more})"
        return DraftQuestion(
            stem=(
                f"{t['context']} Using the pattern of outer electron states down the column, which of the two elements "
                "is more reactive?"
            ),
            answer=correct,
            explanation=f"{t['statement']} {t['reason']}",
            choices=[
                DraftChoice(correct, True, f"Correct: {t['statement']}"),
                DraftChoice(
                    f"{_name(less)} ({less})",
                    False,
                    f"This reverses the trend. {t['statement']}",
                ),
                DraftChoice(
                    "They are equally reactive, because they have the same number of valence electrons.",
                    False,
                    "Elements in a family have the same number of valence electrons, but their outer electrons are in "
                    "different energy levels, which changes how readily they react.",
                ),
                DraftChoice(
                    "Their reactivity cannot be compared using the periodic table.",
                    False,
                    "Position in the periodic table is exactly what predicts the reactivity pattern within a family.",
                ),
            ],
        )

    def _q_reactivity_reasoning(self, params, rng: Rng) -> DraftQuestion:
        t = params["reasoning_pair"]
        more, less = t["more"], t["less"]
        return DraftQuestion(
            stem=(
                f"{t['context']} Experiments show that {_name(more).lower()} is more reactive than {_name(less).lower()}. "
                "Which statement best explains this difference in terms of outer electron states?"
            ),
            answer=t["reason"],
            explanation=f"{t['statement']} {t['reason']}",
            choices=[
                DraftChoice(
                    t["reason"],
                    True,
                    "Correct: the position of the outer energy level relative to the nucleus explains the trend.",
                ),
                DraftChoice(
                    t["reversed"],
                    False,
                    "This reverses the relationship between distance from the nucleus and how strongly outer electrons are held.",
                ),
                DraftChoice(
                    f"{_name(more)} atoms have more valence electrons than {_name(less).lower()} atoms.",
                    False,
                    "Elements in the same column have the same number of valence electrons.",
                ),
                DraftChoice(
                    f"{_name(more)} atoms have a greater mass, and heavier atoms always react more readily.",
                    False,
                    "Reactivity follows from outer electron states, not from mass alone.",
                ),
            ],
        )

    def _q_explain_reaction_outcome(self, params, rng: Rng) -> DraftQuestion:
        f = params["focus"]
        a, b = f["a"], f["b"]
        A, B = _name(a), _name(b)
        t = params["reasoning_pair"]
        more, less = t["more"], t["less"]
        equation = REACTIONS[params["reaction"]]["equation"]
        ionic = params["bond_type"] == "ionic"
        if ionic:
            outcome = (
                f"{A} is a metal with {ELEMENTS[a]['valence']} valence electron(s), so each atom loses "
                f"{ELEMENTS[a]['exchange']} to form a positive ion; {B.lower()} is a nonmetal with {ELEMENTS[b]['valence']} "
                f"valence electrons, so each atom gains {ELEMENTS[b]['exchange']} to form a negative ion. The "
                f"oppositely charged ions attract in an ionic bond, and balancing the electrons lost and gained gives "
                f"{f['formula']}."
            )
        else:
            outcome = (
                f"{A} has {ELEMENTS[a]['valence']} valence electron(s) and {B} has {ELEMENTS[b]['valence']}. Both are "
                f"nonmetals, so neither loses electrons easily; they share {ELEMENTS[a]['exchange']} and "
                f"{ELEMENTS[b]['exchange']} electrons respectively in covalent bonds, and matching the shared electrons "
                f"gives {f['formula']}."
            )
        return DraftQuestion(
            stem=(
                f"A student explains the reaction {equation} by describing the outer electrons of {a} and {b}. "
                f"(a) Write an explanation of the outcome that uses the valence electrons of each element, the type of "
                f"bond, and the formula {f['formula']}. (b) New evidence: {t['context']} {_name(more)} is more reactive "
                f"than {_name(less).lower()}. Revise or extend your explanation to account for this pattern in "
                "terms of outer electron states."
            ),
            answer=f"{outcome} Revision: {t['statement']} {t['reason']}",
            explanation=(
                "Scoring guide (4 points): (1) states the valence electrons of both elements; (2) identifies the "
                f"bond type ({params['bond_type']}) and whether electrons are transferred or shared; (3) connects the "
                f"electron counts to the formula {f['formula']}; (4) revises the explanation with the same-family "
                "trend, linking the outer energy level's distance from the nucleus to reactivity."
            ),
        )
