# Reaction Outcome (C-PS1-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the classroom-only `reaction-outcome` question family for Chemistry C-PS1-2 (explaining the outcome of a simple main-group or combustion reaction from outer electron states).

**Architecture:** One new deterministic `QuestionFamily` in `backend/app/services/families/reaction_outcome.py`. A small curated element/reaction/trend bank stores only periodic-table facts (family, metal/nonmetal, valence electrons, period, electrons lost/gained/shared). Bond type, product-formula ratio, and reactivity answers are all derived from those stored values. It is registered in `registry.py` like every other single-standard family. No migration, API, or frontend change.

**Tech Stack:** Python 3, FastAPI backend, pytest, ruff; existing engine (`Rng`, `TemplateSpec`, `DraftQuestion`, `generate_set`).

**Spec:** `docs/superpowers/specs/2026-09-29-reaction-outcome-design.md`

## Global Constraints

- Family key `reaction-outcome`, version `1.0.0`; binds only `SC / chemistry / C-PS1-2`; no template declares a `standard_code`.
- Scope is main-group elements and combustion. Excluded: transition metals, non-main-group chemistry, quantitative electronegativity or ionization-energy values, any reaction outside the seven-reaction bank.
- Reaction bank exactly: sodium chlorine, potassium bromine, magnesium oxygen, calcium fluorine (ionic); carbon combustion, methane combustion, hydrogen combustion (covalent).
- Six templates, exact keys/DOK/types/citations: `classify_bond_type` (1, MC, `articulating_explanation[1]`), `electron_transfer_count` (1, MC, `evidence[0]`), `predict_product_formula` (2, MC, `evidence[1]`), `compare_reactivity` (2, MC, `evidence[2]`), `reactivity_reasoning` (2, MC, `reasoning[0]`), `explain_reaction_outcome` (3, constructed_response, `reasoning[1]`).
- Do not modify `chemical_systems.py`, `quantitative_conservation.py`, or `reaction_rate.py`.
- Classroom-only: no EOCEP constraints exist for C-PS1-2, so `generation_mode: "eocep"` must stay rejected (422).
- All randomness through `Rng`; every answer derived from the scenario's stored values, never live physical calculation.

## Spec clarifications made by this plan (confirm during review)

1. **Two different trend pairs per scenario.** The spec says `compare_reactivity` and `reactivity_reasoning` draw from the trend table independently of the reaction. If they used the *same* pair, the `reactivity_reasoning` stem ("X is more reactive than Y…") would give away the `compare_reactivity` answer whenever both land in one generated set. The scenario therefore draws two *distinct* pairs (`compare_pair`, `reasoning_pair`); the constructed response reuses `reasoning_pair`.
2. **`question_family_candidate` flag.** `data/standards/SC/2026-2027/chemistry.json` does not mark C-PS1-2 `question_family_candidate: true`, and the existing test `test_template_citations_exist_in_scde_data` requires it for every bound standard. Task 4 adds the flag.
3. **Methane focus.** Bond/formula items for `methane_combustion` ask about the C–O product (CO₂); `hydrogen_combustion` asks about H–O (H₂O).
4. **Hydrogen** follows the duet rule (shares 1 electron), not the octet; the electron-count item guards this explicitly.

## Review Focus

Failure modes the spec implies but a straightforward build would not test; each has an owning test below.

1. A metal–metal pair reaching `bond_type` (outside the bank) must raise `GenerationError`, not silently classify as covalent — Task 1.
2. Hydrogen expecting 7 electrons (octet rule) instead of 1 — Task 2 (`test_hydrogen_uses_the_duet_not_the_octet`).
3. `reactivity_reasoning` (and its stimulus table) leaking the `compare_reactivity` answer in the same set — Task 2 (pair inequality in the scenario test), Task 3 (stem check).
4. Requests for more questions than templates (quantity 14 → three groups) and single-template filters must still produce a valid stimulus with only the needed tables — Task 4.
5. Excluded-content drift (ionization energy, transition metals, numeric electronegativity) appearing in generated text — Task 4.

## File Structure

- Create `backend/app/services/families/reaction_outcome.py` — curated bank, pure helpers (`sub`, `bond_type`, `combine`, `formula_text`, `element_row`), and the `ReactionOutcome` family. One responsibility: this family. Mirrors `reaction_rate.py`/`quantitative_conservation.py` layout.
- Create `backend/tests/test_reaction_outcome.py` — family-specific invariants with hand-entered ground truth (independent of module code).
- Modify `backend/app/services/families/registry.py` — import and add to `FAMILIES`.
- Modify `data/standards/SC/2026-2027/chemistry.json` — flag C-PS1-2 `question_family_candidate: true`.
- Modify `backend/tests/test_engine.py` — pin the `GOLDEN` digest.
- Modify `backend/tests/test_api.py` — add the preview-reproducibility case and an EOCEP-denial assertion.
- Modify `HANDOFF.md` — implemented-families table.

Run all commands from `backend/` unless stated. Python is `.venv/bin/python`.

---

### Task 1: Curated bank and pure helpers

**Files:**
- Create: `backend/app/services/families/reaction_outcome.py`
- Create: `backend/tests/test_reaction_outcome.py`

**Interfaces:**
- Produces (module-level, used by Tasks 2–3): `ELEMENTS: dict[str, dict]` (keys `name, family, metal, valence, period, exchange`), `REACTIONS: dict[str, dict]` (keys `equation, blurb, focus`), `TRENDS: tuple[dict, ...]` (keys `less, more, context, statement, reason, reversed`), `_RATIOS`, `sub(n) -> str`, `bond_type(a, b) -> "ionic" | "covalent"` (raises `GenerationError` for metal–metal), `combine(a, b) -> (n_a, n_b)`, `formula_text(a, b, n_a, n_b) -> str`, `element_row(symbol) -> dict`, `_name(symbol) -> str`, `_plural(n, word) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_reaction_outcome.py`:

```python
"""Independent checks for the reaction-outcome family (C-PS1-2).

Ground truth below is hand-entered from the periodic table, not derived from the module under test.
"""

import pytest

from app.services.engine.core import GenerationError
from app.services.families.reaction_outcome import ELEMENTS, REACTIONS, TRENDS, bond_type, combine

SEEDS = [f"ro-{i}" for i in range(150)]
# symbol: (valence electrons, is metal, period, electrons lost/gained/shared to fill the outer level)
FACTS = {
    "H": (1, False, 1, 1),
    "C": (4, False, 2, 4),
    "O": (6, False, 2, 2),
    "F": (7, False, 2, 1),
    "Cl": (7, False, 3, 1),
    "Br": (7, False, 4, 1),
    "Na": (1, True, 3, 1),
    "K": (1, True, 4, 1),
    "Mg": (2, True, 3, 2),
    "Ca": (2, True, 4, 2),
}
EXPECTED = {  # reaction: (bond type, product formula)
    "sodium_chlorine": ("ionic", "NaCl"),
    "potassium_bromine": ("ionic", "KBr"),
    "magnesium_oxygen": ("ionic", "MgO"),
    "calcium_fluorine": ("ionic", "CaF₂"),
    "carbon_combustion": ("covalent", "CO₂"),
    "methane_combustion": ("covalent", "CO₂"),
    "hydrogen_combustion": ("covalent", "H₂O"),
}


def test_element_catalog_matches_reviewed_facts():
    assert set(ELEMENTS) == set(FACTS)
    for symbol, (valence, metal, period, exchange) in FACTS.items():
        e = ELEMENTS[symbol]
        assert (e["valence"], e["metal"], e["period"], e["exchange"]) == (valence, metal, period, exchange)


def test_reaction_bank_covers_spec_and_stays_main_group():
    assert set(REACTIONS) == set(EXPECTED)
    for key, (bond, formula) in EXPECTED.items():
        a, b = REACTIONS[key]["focus"]
        assert bond_type(a, b) == bond
        n_a, n_b = combine(a, b)
        assert formula in REACTIONS[key]["equation"]
        # ionic: electrons lost = electrons gained; covalent: shared electrons match on both sides
        assert n_a * FACTS[a][3] == n_b * FACTS[b][3]
        if bond == "ionic":
            assert FACTS[a][1] and not FACTS[b][1]


def test_trend_pairs_are_same_family_with_correct_direction():
    for t in TRENDS:
        less, more = FACTS[t["less"]], FACTS[t["more"]]
        assert ELEMENTS[t["less"]]["family"] == ELEMENTS[t["more"]]["family"]
        assert less[0] == more[0]  # same valence electrons
        if ELEMENTS[t["more"]]["metal"]:
            assert more[2] > less[2]  # metals: more reactive further down the column
        else:
            assert more[2] < less[2]  # halogens: more reactive further up the column


def test_metal_metal_pair_is_rejected_as_out_of_bank():
    with pytest.raises(GenerationError):
        bond_type("Na", "K")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'app.services.families.reaction_outcome'`.

- [ ] **Step 3: Write the bank and helpers**

Create `backend/app/services/families/reaction_outcome.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: `4 passed`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
.venv/bin/ruff format app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
git add app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
git commit -m "feat: add reaction-outcome curated element and reaction bank"
```

---

### Task 2: Family shell, scenario, stimulus, and the first three items

**Files:**
- Modify: `backend/app/services/families/reaction_outcome.py` (append the class)
- Modify: `backend/tests/test_reaction_outcome.py`

**Interfaces:**
- Consumes: everything Task 1 produced.
- Produces: `ReactionOutcome` (a `QuestionFamily`) with `templates` declaring all six keys, `build_scenario(rng) -> dict` (keys `reaction, bond_type, focus{a,b,atoms_a,atoms_b,formula}, elements[], compare_pair{…,rows[]}, reasoning_pair{…,rows[]}`), `render_stimulus(params, template_keys) -> dict`, `build_question(template, params, rng)` dispatching to `_q_<key>`, and implemented `_q_classify_bond_type`, `_q_electron_transfer_count`, `_q_predict_product_formula`. `_q_compare_reactivity`, `_q_reactivity_reasoning`, `_q_explain_reaction_outcome` are added in Task 3.

- [ ] **Step 1: Write the failing tests**

Replace the import block and everything above the first `def test_` in `backend/tests/test_reaction_outcome.py` with the full header below (it adds `json`, `Rng`, `generate_set`, `ReactionOutcome`, and the `fam`/`_params`/`_item` helpers), then append the new tests.

```python
"""Independent checks for the reaction-outcome family (C-PS1-2).

Ground truth below is hand-entered from the periodic table, not derived from the module under test.
"""

import json

import pytest

from app.services.engine.core import GenerationError, Rng
from app.services.engine.family import generate_set
from app.services.families.reaction_outcome import ELEMENTS, REACTIONS, TRENDS, ReactionOutcome, bond_type, combine

SEEDS = [f"ro-{i}" for i in range(150)]
# symbol: (valence electrons, is metal, period, electrons lost/gained/shared to fill the outer level)
FACTS = {
    "H": (1, False, 1, 1),
    "C": (4, False, 2, 4),
    "O": (6, False, 2, 2),
    "F": (7, False, 2, 1),
    "Cl": (7, False, 3, 1),
    "Br": (7, False, 4, 1),
    "Na": (1, True, 3, 1),
    "K": (1, True, 4, 1),
    "Mg": (2, True, 3, 2),
    "Ca": (2, True, 4, 2),
}
EXPECTED = {  # reaction: (bond type, product formula)
    "sodium_chlorine": ("ionic", "NaCl"),
    "potassium_bromine": ("ionic", "KBr"),
    "magnesium_oxygen": ("ionic", "MgO"),
    "calcium_fluorine": ("ionic", "CaF₂"),
    "carbon_combustion": ("covalent", "CO₂"),
    "methane_combustion": ("covalent", "CO₂"),
    "hydrogen_combustion": ("covalent", "H₂O"),
}


fam = ReactionOutcome()


def _params(seed: str) -> dict:
    return fam.build_scenario(Rng("scenario", seed))


def _item(key: str, seed: str):
    p = _params(seed)
    return p, fam.build_question(fam.template(key), p, Rng("item", key, seed))
```

Append:

```python
def test_scenario_is_json_safe_and_matches_expected_outcome():
    seen = set()
    for seed in SEEDS:
        p = _params(seed)
        json.dumps(p)
        bond, formula = EXPECTED[p["reaction"]]
        seen.add(p["reaction"])
        assert (p["bond_type"], p["focus"]["formula"]) == (bond, formula)
        assert [r["symbol"] for r in p["elements"]] == list(REACTIONS[p["reaction"]]["focus"])
        for row in p["elements"]:
            valence, metal, period, _ = FACTS[row["symbol"]]
            assert (row["valence"], row["type"] == "metal", row["period"]) == (valence, metal, period)
        assert p["compare_pair"]["more"] != p["reasoning_pair"]["more"]  # no answer leak between the two items
    assert seen == set(EXPECTED)


def test_stimulus_shows_only_tables_the_chosen_templates_need_and_no_answers():
    p = _params("stim")
    only_bond = fam.render_stimulus(p, ["classify_bond_type"])
    assert len(only_bond["tables"]) == 1 and only_bond["charts"] == []
    everything = fam.render_stimulus(p, [t.key for t in fam.templates])
    assert len(everything["tables"]) == 3
    blob = json.dumps(everything, ensure_ascii=False)
    assert "more reactive" not in blob and p["reasoning_pair"]["statement"] not in blob
    assert {"key": "family", "label": "Family"} in everything["tables"][0]["columns"]


def test_bond_type_item_key_follows_metal_nonmetal_rule():
    for seed in SEEDS:
        p, q = _item("classify_bond_type", seed)
        correct = next(c for c in q.choices if c.correct).text
        a, b = p["focus"]["a"], p["focus"]["b"]
        if EXPECTED[p["reaction"]][0] == "ionic":
            assert correct == f"An ionic bond, because {a} atoms lose electrons and {b} atoms gain them."
        else:
            assert correct.startswith("A covalent bond") and "both nonmetals" in correct


def test_electron_count_item_key_matches_reviewed_facts():
    for seed in SEEDS:
        p, q = _item("electron_transfer_count", seed)
        correct = next(c for c in q.choices if c.correct).text
        symbol = next(s for s in (p["focus"]["a"], p["focus"]["b"]) if ELEMENTS[s]["name"] in q.stem)
        expected = FACTS[symbol][3]
        assert correct == f"{expected} electron" + ("" if expected == 1 else "s")


def test_formula_item_key_and_distractors_are_charge_or_share_balanced_correctly():
    for seed in SEEDS:
        p, q = _item("predict_product_formula", seed)
        assert next(c for c in q.choices if c.correct).text == EXPECTED[p["reaction"]][1]
        assert sum(c.text == EXPECTED[p["reaction"]][1] for c in q.choices) == 1


def test_hydrogen_uses_the_duet_not_the_octet():
    p = fam.build_scenario(Rng("scenario", "h"))
    p = {
        **p,
        "reaction": "hydrogen_combustion",
        "bond_type": "covalent",
        "focus": {"a": "H", "b": "O", "atoms_a": 2, "atoms_b": 1, "formula": "H₂O"},
    }
    for i in range(40):
        q = fam.build_question(fam.template("electron_transfer_count"), p, Rng("item", i))
        correct = next(c for c in q.choices if c.correct).text
        if "hydrogen atom" in q.stem:
            assert correct == "1 electron"
            assert "7 electrons" not in correct
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: collection ERROR — `ImportError: cannot import name 'ReactionOutcome'`.

- [ ] **Step 3: Append the family class**

Append to `backend/app/services/families/reaction_outcome.py` (after `_plural`). The `templates` tuple is complete now; the three remaining `_q_` methods arrive in Task 3.

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: all pass (`10 passed`).

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
.venv/bin/ruff format app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
git add app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
git commit -m "feat: add reaction-outcome scenario, stimulus, and bond/electron/formula items"
```

---

### Task 3: Reactivity items and the constructed response

**Files:**
- Modify: `backend/app/services/families/reaction_outcome.py` (append three methods inside the class)
- Modify: `backend/tests/test_reaction_outcome.py`

**Interfaces:**
- Consumes: `params["compare_pair"]` / `params["reasoning_pair"]` (`less`, `more`, `context`, `statement`, `reason`, `reversed`), `params["focus"]`, `params["bond_type"]`, `_name`, `REACTIONS`, `ELEMENTS`.
- Produces: `_q_compare_reactivity`, `_q_reactivity_reasoning`, `_q_explain_reaction_outcome`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reaction_outcome.py`:

```python
def test_reactivity_items_key_is_the_more_reactive_element_and_stems_do_not_leak():
    for seed in SEEDS:
        p, q = _item("compare_reactivity", seed)
        t = p["compare_pair"]
        more = ELEMENTS[t["more"]]["name"].capitalize()
        assert next(c for c in q.choices if c.correct).text == f"{more} ({t['more']})"
        assert "more reactive than" not in q.stem
        p, q = _item("reactivity_reasoning", seed)
        t = p["reasoning_pair"]
        assert next(c for c in q.choices if c.correct).text == t["reason"]
        assert t["reversed"] in {c.text for c in q.choices}


def test_explain_item_is_constructed_response_with_scoring_guide():
    for seed in SEEDS:
        p, q = _item("explain_reaction_outcome", seed)
        assert q.choices == []
        assert p["focus"]["formula"] in q.stem and p["focus"]["formula"] in q.answer
        assert "Scoring guide" in q.explanation and p["bond_type"] in q.explanation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: FAIL — `AttributeError: 'ReactionOutcome' object has no attribute '_q_compare_reactivity'`.

- [ ] **Step 3: Append the three methods**

Append these methods to the end of the `ReactionOutcome` class (same 4-space indentation, directly after `_q_predict_product_formula`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: `12 passed`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
.venv/bin/ruff format app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
git add app/services/families/reaction_outcome.py tests/test_reaction_outcome.py
git commit -m "feat: add reaction-outcome reactivity items and constructed response"
```

---

### Task 4: Registration, standards flag, golden digest, API coverage, docs

**Files:**
- Modify: `backend/app/services/families/registry.py`
- Modify: `data/standards/SC/2026-2027/chemistry.json` (C-PS1-2 entry, terminology line ~48)
- Modify: `backend/tests/test_reaction_outcome.py`
- Modify: `backend/tests/test_engine.py` (`GOLDEN`)
- Modify: `backend/tests/test_api.py`
- Modify: `HANDOFF.md` (implemented-families table)

**Interfaces:**
- Consumes: `ReactionOutcome` with all six templates (Tasks 2–3).
- Produces: `FAMILIES["reaction-outcome"]`, discoverable through `/api/families` and bound to `SC/chemistry/C-PS1-2`.

- [ ] **Step 1: Write the whole-family tests (they need only the family, not the registry)**

Append to `backend/tests/test_reaction_outcome.py`:

```python
@pytest.mark.parametrize("key", [t.key for t in fam.templates if t.question_type == "multiple_choice"])
def test_multiple_choice_items_have_one_key_and_a_rationale_for_each_choice(key):
    for seed in SEEDS:
        _, q = _item(key, seed)
        assert sum(c.correct for c in q.choices) == 1
        assert len({c.text for c in q.choices}) == len(q.choices) >= 4
        assert all(c.rationale for c in q.choices)


def test_large_quantity_builds_several_valid_groups():
    out = generate_set(fam, "many", 14)
    assert len(out["groups"]) == 3
    assert sum(len(g["questions"]) for g in out["groups"]) == 14
    assert all(q["stem"] and q["answer"] and q["explanation"] for g in out["groups"] for q in g["questions"])


def test_template_filter_yields_only_the_requested_template_and_its_table():
    out = generate_set(fam, "filter", 3, template_keys=["compare_reactivity"])
    assert {q["template_key"] for g in out["groups"] for q in g["questions"]} == {"compare_reactivity"}
    assert len(out["groups"][0]["stimulus"]["tables"]) == 1


def test_generate_set_is_deterministic_and_excludes_out_of_scope_content():
    out = generate_set(fam, "det", len(fam.templates))
    assert json.dumps(out, sort_keys=True) == json.dumps(generate_set(fam, "det", len(fam.templates)), sort_keys=True)
    text = json.dumps(out, ensure_ascii=False).lower()
    assert all(w not in text for w in ("ionization energy", "transition metal", "kj/mol", "electronegativity value"))
```

Run: `.venv/bin/python -m pytest tests/test_reaction_outcome.py -q -p no:cacheprovider`
Expected: `20 passed` (these exercise the finished family directly).

- [ ] **Step 2: Register the family**

In `backend/app/services/families/registry.py` add the import after the `quantitative_conservation` import and the instance last in the `FAMILIES` tuple:

```python
from app.services.families.reaction_outcome import ReactionOutcome
```

```python
        ChemicalSystemStability(),
        ReactionOutcome(),
```

- [ ] **Step 3: Run the engine suite to see the expected failures**

Run: `.venv/bin/python -m pytest tests/test_engine.py -q -p no:cacheprovider 2>&1 | tail -15`
Expected: FAIL — `test_golden_snapshot[reaction-outcome]` (`KeyError: 'reaction-outcome'`) and `test_template_citations_exist_in_scde_data[reaction-outcome]` (`assert None is True`: the standard is not flagged as a family candidate).

- [ ] **Step 4: Flag the standard**

In `data/standards/SC/2026-2027/chemistry.json`, the C-PS1-2 entry ends with its `"terminology": [...]` line followed directly by `},`. Add the flag exactly as the neighboring entries do, so that line ends `…],` and the next line is `"question_family_candidate": true`:

```json
          "terminology": ["alkali metal", "...unchanged..."],
          "question_family_candidate": true
        },
```

Verify: `.venv/bin/python -c "import json;d=json.load(open('../data/standards/SC/2026-2027/chemistry.json'));print([s.get('question_family_candidate') for dom in d['domains'] for s in dom['standards'] if s['code']=='C-PS1-2'])"` → `[True]`.

- [ ] **Step 5: Compute and pin the golden digest**

```bash
.venv/bin/python - <<'PY'
import hashlib, json
from app.services.engine.family import generate_set
from app.services.families.registry import FAMILIES
print(hashlib.sha256(json.dumps(generate_set(FAMILIES["reaction-outcome"], "golden", 12), sort_keys=True).encode()).hexdigest())
PY
```

Add the printed digest to `GOLDEN` in `backend/tests/test_engine.py` after the `chemical-system-stability` line. (When this plan was drafted the digest was `ee1df82b94db39de882f05d6606220a458d53d9006f617ee737d5d50b81cc009`; if yours differs, the module differs from the plan — find out why before pinning.)

```python
    "reaction-outcome": "<digest>",
```

- [ ] **Step 6: API coverage**

In `backend/tests/test_api.py`, add to the `test_preview_is_reproducible` parametrize list:

```python
        ("chemistry", "C-PS1-2", "reaction-outcome"),
```

and inside `test_eocep_mode_uses_imported_biology_1_constraints`, after the existing `assert denied.status_code == 422`, add:

```python
    chemistry_2 = next(s for s in standards if s["course_slug"] == "chemistry" and s["code"] == "C-PS1-2")
    denied_2 = client.post(
        "/api/generate/preview",
        json={"standard_id": chemistry_2["id"], "family_key": "reaction-outcome", "quantity": 1, "generation_mode": "eocep"},
    )
    assert denied_2.status_code == 422
```

- [ ] **Step 7: Run everything, including DB-backed tests with zero skips**

```bash
.venv/bin/ruff check app tests
docker run -d --rm --name sb-testdb -p 127.0.0.1:54330:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54330/sb_test .venv/bin/python -m pytest -q -p no:cacheprovider
docker stop sb-testdb
```

Expected: all pass, `0 skipped`. (`sync_families` runs in the DB fixture and will fail loudly if any citation index is out of range.) Note: `ruff check .` at repo level reports two pre-existing import-order issues in `alembic/env.py` and `scripts/dump_openapi.py`; `ruff check app tests` is the project's check and should be clean.

- [ ] **Step 8: Docs**

In `HANDOFF.md`, add a row to the implemented-families table after `quantitative-conservation`:

```markdown
| `reaction-outcome` | Chemistry C-PS1-2 | 1.0.0 | Curated main-group/combustion reactions: bond type, electrons lost/gained/shared, product formula, same-family reactivity trends. Classroom-only. |
```

Also add one line under "Next family work" saying C-PS1-2 now has a standalone family and that the `chemical-system-stability` bundle still serves only C-PS1-5/C-PS1-7 (wiring `reaction-outcome` into that bundle is a separate, unplanned step).

- [ ] **Step 9: Commit**

```bash
git add app/services/families/registry.py ../data/standards/SC/2026-2027/chemistry.json tests ../HANDOFF.md
git commit -m "feat: register reaction-outcome family for C-PS1-2"
```

- [ ] **Step 10: Deploy note (do not run without the user's go-ahead)**

After merge/deploy, `docker compose exec app python -m app.cli bootstrap` (idempotent) registers the family row and re-imports standards so the candidate flag reaches the database. Then confirm `GET /api/families` lists `reaction-outcome`.

---

## Self-Review (done while drafting)

- **Spec coverage:** bank (7 reactions) — T1; element data & trend table — T1; six templates with exact DOK/type/citation — T2/T3; categorical answer derivation (metal/nonmetal, charge/share balance, trend table) — T1/T2/T3; registration — T4; deterministic/golden tests — T4; non-goals respected (no edits to other families, no bundle wiring, no EOCEP).
- **Placeholder scan:** none; every step carries its code or exact command. The golden digest is computed in-step with the drafted value given for cross-checking.
- **Type consistency:** `params` keys (`focus`, `elements`, `compare_pair`, `reasoning_pair`, `bond_type`, `reaction`) are identical across the scenario builder, stimulus, items, and tests. The module and tests in this plan were run together during drafting (20 tests passing, engine suite passing with the family registered); the DB-backed API tests could not be run in the drafting environment (no `TEST_DATABASE_URL`), which is why Task 4 Step 7 requires a zero-skip run.
