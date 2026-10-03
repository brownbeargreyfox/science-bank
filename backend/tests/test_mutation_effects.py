"""Independent checks for mutation-effects (B-LS3-2).

Ground truth is typed in tests (the by-amino-acid genetic code is imported from the B-LS1-1 tests, which type it
independently of the module under test); reading, predicates, and edit detection are re-implemented here.
"""

import json

from app.services.engine.core import Rng
from app.services.families import mutation_effects as me
from tests.test_protein_synthesis import CODE, TEMPLATE_PAIR

SEEDS = [f"mut-{i}" for i in range(200)]
TAIL_RANGE = (4, 5)


def _scenario(seed: str) -> dict:
    return me.draw_scenario(Rng("scenario", seed))


def _read(mrna: str):
    """Test-side sequence model: AUG start, groups of three, first in-frame Stop; None if no Stop is met."""
    names, used = [], []
    for i in range(0, len(mrna) - len(mrna) % 3, 3):
        codon = mrna[i : i + 3]
        used.append(codon)
        if CODE[codon] == "Stop":
            return names, used
        names.append(CODE[codon])
    return None, used


def _category(original: list[str], changed: list[str]):
    diff = sum(a != b for a, b in zip(original, changed))
    flags = {
        "unchanged": changed == original,
        "one_changed": len(changed) == len(original) and diff == 1,
        "ends_early": len(changed) < len(original) and changed == original[: len(changed)],
        "several_differ": len(changed) >= len(original) and diff >= 2,
    }
    true = [k for k, v in flags.items() if v]
    assert len(true) <= 1, flags
    return true[0] if true else None


def _single_edit_positions(original: str, changed: str):
    """(type, [every 0-based index at which that one edit would give `changed`]), or (None, [])."""
    if len(changed) == len(original):
        diffs = [i for i, (a, b) in enumerate(zip(original, changed)) if a != b]
        return ("substitution", diffs) if len(diffs) == 1 else (None, [])
    if len(changed) == len(original) + 1:
        spots = [i for i in range(len(changed)) if changed[:i] + changed[i + 1 :] == original]
        return ("insertion", spots) if spots else (None, [])
    if len(changed) == len(original) - 1:
        spots = [i for i in range(len(original)) if original[:i] + original[i + 1 :] == changed]
        return ("deletion", spots) if spots else (None, [])
    return None, []


# ---- reader and predicates -----------------------------------------------------------------


def test_read_protein_follows_the_sequence_model():
    assert me.read_protein("AUGCCUUAAGGG") == (["Methionine", "Proline"], ["AUG", "CCU", "UAA"])
    assert me.read_protein("AUGCCUGG") == (None, ["AUG", "CCU"])
    assert me.read_protein("AUGCC") == (None, ["AUG"])


def test_effect_predicates_are_disjoint_and_name_each_case():
    m, p, s, k = "Methionine", "Proline", "Serine", "Lysine"
    assert me.effect_of([m, p, s], [m, p, s]) == "unchanged"
    assert me.effect_of([m, p, s], [m, k, s]) == "one_changed"
    assert me.effect_of([m, p, s], [m, p]) == "ends_early"
    assert me.effect_of([m, p, s], [m, k, k]) == "several_differ"
    assert me.effect_of([m, p, s], [m, k, k, p]) == "several_differ"  # longer is allowed when two or more differ
    assert me.effect_of([m, p, s], [m, p, s, k]) is None  # only longer: no description is true
    assert me.effect_of([m, p, s], [m, k, s, k]) is None  # one difference but longer
    for original in ([m, p, s], [m, p, s, k]):
        for changed in ([m, p, s], [m, k, s], [m, p], [m, k, k], [m, p, s, k], [k, m]):
            assert sum(me.effect_flags(original, changed).values()) <= 1


# ---- edits ---------------------------------------------------------------------------------


def test_every_edit_is_a_single_declared_edit_at_an_unambiguous_position():
    for seed in SEEDS:
        for name, role in _scenario(seed)["roles"].items():
            original, changed = role["original"]["template"], role["changed"]["template"]
            edit = role["edit"]
            kind, spots = _single_edit_positions(original, changed)
            assert kind == edit["type"], (seed, name)
            assert len(spots) == 1, (seed, name, "position is ambiguous")
            i = spots[0]
            assert i == edit["index"]
            assert edit["position"] == (i if kind == "insertion" else i + 1)
            lo, hi = 3, 3 * (role["n_sense"] + 1) - 1
            assert lo <= i <= hi, (seed, name, "edit outside the sense codons")
            if kind == "substitution":
                assert (original[i], changed[i]) == (edit["old"], edit["new"])
            elif kind == "deletion":
                assert original[i] == edit["old"]
            else:
                assert changed[i] == edit["new"]
            assert role["original"]["mrna"] == "".join(TEMPLATE_PAIR[b] for b in original)
            assert role["changed"]["mrna"] == "".join(TEMPLATE_PAIR[b] for b in changed)


# ---- scenario ------------------------------------------------------------------------------


def test_scenario_is_json_safe_with_four_independent_roles():
    for seed in SEEDS:
        s = _scenario(seed)
        json.dumps(s)
        assert set(s["roles"]) == {"classify", "protein", "effect", "claim"}
        assert len({r["label"] for r in s["roles"].values()}) == 4
        assert s["cause"] in me.CAUSES
        for r in s["roles"].values():
            mrna = r["original"]["mrna"]
            assert mrna.startswith("AUG") and CODE[mrna[3 * (r["n_sense"] + 1) : 3 * (r["n_sense"] + 2)]] == "Stop"
            assert 3 <= r["n_sense"] <= 4
            tail = len(mrna) // 3 - (r["n_sense"] + 2)
            assert TAIL_RANGE[0] <= tail <= TAIL_RANGE[1]


def test_translated_roles_are_determinate_and_classified_exactly_once():
    seen = set()
    for seed in SEEDS:
        roles = _scenario(seed)["roles"]
        assert roles["classify"]["category"] is None and roles["classify"]["original"]["protein"] is None
        for name in ("protein", "effect", "claim"):
            r = roles[name]
            original, _ = _read(r["original"]["mrna"])
            changed, _ = _read(r["changed"]["mrna"])
            assert original is not None and changed is not None, (seed, name, "no Stop met")
            assert (r["original"]["protein"], r["changed"]["protein"]) == (original, changed)
            category = _category(original, changed)
            assert category == r["category"] and category is not None
            assert (category == "several_differ") == (r["edit"]["type"] != "substitution")
            if name == "effect":
                seen.add(category)
        protein = roles["protein"]
        assert protein["changed"]["protein"] != protein["original"]["protein"]
        options = [tuple(protein["changed"]["protein"])] + [tuple(v) for v in protein["distractors"].values()]
        assert len(set(options)) == 4
    assert seen == set(me.EFFECT_TEXT)  # every category appears in the effect role over the seeds


def test_codon_table_is_exact_and_self_contained():
    for seed in SEEDS:
        s = _scenario(seed)
        rows = s["codon_table"]
        codons = [r["codon"] for r in rows]
        assert codons == sorted(codons) and len(set(codons)) == len(codons)
        assert 12 <= len(rows) <= 36
        for r in rows:
            expected = "Methionine (start)" if r["codon"] == "AUG" else CODE[r["codon"]]
            assert r["amino_acid"] == expected
        needed = set()
        for name in ("protein", "effect", "claim"):
            r = s["roles"][name]
            needed |= set(_read(r["original"]["mrna"])[1]) | set(_read(r["changed"]["mrna"])[1])
        misread = _read(s["roles"]["protein"]["changed"]["template"].replace("T", "U"))
        assert misread[0] is not None
        needed |= set(misread[1])
        assert needed <= set(codons)
        assert len(set(codons) - needed) in (2, 3)


def test_inheritance_scenario_is_curated():
    cells, organisms, mutagens = set(), set(), set()
    for seed in SEEDS:
        i = _scenario(seed)["inheritance"]
        assert set(i) == {"organism", "cell", "gamete", "mutagen"}
        assert i["gamete"] == (i["cell"] in ("an egg cell", "a sperm cell"))
        cells.add(i["cell"])
        organisms.add(i["organism"])
        mutagens.add(i["mutagen"])
    assert cells == {"a body cell (somatic cell)", "an egg cell", "a sperm cell"}
    assert organisms == {"a mouse", "a fruit fly", "a zebrafish"}
    assert mutagens == {"ultraviolet light", "X-rays"}
