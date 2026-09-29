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


def test_trend_pairs_are_same_family_with_correct_direction():
    for t in TRENDS:
        less, more = FACTS[t["less"]], FACTS[t["more"]]
        assert ELEMENTS[t["less"]]["family"] == ELEMENTS[t["more"]]["family"]
        assert less[0] == more[0]  # same valence electrons
        if ELEMENTS[t["more"]]["metal"]:
            assert more[2] > less[2]  # metals: more reactive further down the column
        else:
            assert more[2] < less[2]  # halogens: more reactive further up the column


@pytest.mark.parametrize("key", [t.key for t in fam.templates if t.question_type == "multiple_choice"])
def test_multiple_choice_items_have_one_key_and_a_rationale_for_each_choice(key):
    for seed in SEEDS:
        _, q = _item(key, seed)
        assert sum(c.correct for c in q.choices) == 1
        assert len({c.text for c in q.choices}) == len(q.choices) >= 4
        assert all(c.rationale for c in q.choices)


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


def test_stimulus_shows_only_tables_the_chosen_templates_need_and_no_answers():
    p = _params("stim")
    only_bond = fam.render_stimulus(p, ["classify_bond_type"])
    assert len(only_bond["tables"]) == 1 and only_bond["charts"] == []
    everything = fam.render_stimulus(p, [t.key for t in fam.templates])
    assert len(everything["tables"]) == 3
    blob = json.dumps(everything, ensure_ascii=False)
    assert "more reactive" not in blob and p["reasoning_pair"]["statement"] not in blob
    assert {"key": "family", "label": "Family"} in everything["tables"][0]["columns"]


def test_explain_item_is_constructed_response_with_scoring_guide():
    for seed in SEEDS:
        p, q = _item("explain_reaction_outcome", seed)
        assert q.choices == []
        assert p["focus"]["formula"] in q.stem and p["focus"]["formula"] in q.answer
        assert "Scoring guide" in q.explanation and p["bond_type"] in q.explanation


def test_generate_set_is_deterministic_and_excludes_out_of_scope_content():
    out = generate_set(fam, "det", len(fam.templates))
    assert json.dumps(out, sort_keys=True) == json.dumps(generate_set(fam, "det", len(fam.templates)), sort_keys=True)
    text = json.dumps(out, ensure_ascii=False).lower()
    assert all(w not in text for w in ("ionization energy", "transition metal", "kj/mol", "electronegativity value"))


def test_metal_metal_pair_is_rejected_as_out_of_bank():
    with pytest.raises(GenerationError):
        bond_type("Na", "K")


def test_large_quantity_builds_several_valid_groups():
    out = generate_set(fam, "many", 14)
    assert len(out["groups"]) == 3
    assert sum(len(g["questions"]) for g in out["groups"]) == 14
    assert all(q["stem"] and q["answer"] and q["explanation"] for g in out["groups"] for q in g["questions"])


def test_template_filter_yields_only_the_requested_template_and_its_table():
    out = generate_set(fam, "filter", 3, template_keys=["compare_reactivity"])
    assert {q["template_key"] for g in out["groups"] for q in g["questions"]} == {"compare_reactivity"}
    assert len(out["groups"][0]["stimulus"]["tables"]) == 1


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
