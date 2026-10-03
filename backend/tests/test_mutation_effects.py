"""Independent checks for mutation-effects (B-LS3-2).

Ground truth is typed in tests (the by-amino-acid genetic code is imported from the B-LS1-1 tests, which type it
independently of the module under test); reading, predicates, and edit detection are re-implemented here.
"""

import json
import re

from app.services.engine.core import Rng
from app.services.engine.family import generate_set
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


STRAND = re.compile(r"([35])′-([ACGTU]+)-([35])′")


def _set(seed: str, *keys: str) -> dict:
    return generate_set(me.MutationEffects(), seed, len(keys), template_keys=list(keys))


def _only(out: dict, key: str) -> dict:
    return next(q for g in out["groups"] for q in g["questions"] if q["template_key"] == key)


def _correct(q: dict) -> str:
    return next(c["text"] for c in q["choices"] if c["correct"])


def _strands(q: dict):
    found = STRAND.findall(q["stem"])
    assert [(a, c) for a, _, c in found] == [("3", "5"), ("3", "5")], q["stem"]
    return found[0][1], found[1][1]


def _table(out: dict) -> dict[str, str]:
    tables = out["groups"][0]["stimulus"]["tables"]
    return {r["codon"]: r["amino_acid"] for r in next(t for t in tables if "codon" in t["rows"][0])["rows"]}


# ---- registration --------------------------------------------------------------------------


def test_family_is_registered_and_bound_to_biology_1_only():
    from app.services.families.registry import FAMILIES

    fam = FAMILIES["mutation-effects"]
    assert fam.version == "1.0.0"
    assert [(b.state, b.course_slug, b.code) for b in fam.bindings] == [("SC", "biology-1", "B-LS3-2")]
    assert all(t.standard_code is None for t in fam.templates)


# ---- identify_mutation_type ----------------------------------------------------------------

TYPE_TEXT = {
    "substitution": "A substitution: one nucleotide was replaced by another.",
    "insertion": "An insertion: one nucleotide was added.",
    "deletion": "A deletion: one nucleotide was removed.",
}
NO_MUTATION = "No mutation occurred, because the protein is not changed."


def test_identify_key_follows_the_displayed_strands_and_offers_the_four_texts_once():
    for seed in SEEDS:
        q = _only(_set(seed, "identify_mutation_type"), "identify_mutation_type")
        original, changed = _strands(q)
        kind, _ = _single_edit_positions(original, changed)
        assert _correct(q) == TYPE_TEXT[kind]
        texts = sorted(c["text"] for c in q["choices"])
        assert texts == sorted([*TYPE_TEXT.values(), NO_MUTATION])
        assert any(cause in q["stem"] for cause in me.CAUSES)
        assert "frameshift" in q["explanation"].lower() or kind == "substitution"


def test_identify_stimulus_has_no_table():
    assert _set("only-identify", "identify_mutation_type")["groups"][0]["stimulus"]["tables"] == []


# ---- new_protein_after_change --------------------------------------------------------------


def test_new_protein_key_is_the_changed_protein_read_with_the_displayed_table():
    for seed in SEEDS:
        out = _set(seed, "new_protein_after_change")
        q = _only(out, "new_protein_after_change")
        original, changed = _strands(q)
        table = _table(out)
        mrna_original = "".join(TEMPLATE_PAIR[b] for b in original)
        mrna_changed = "".join(TEMPLATE_PAIR[b] for b in changed)
        before, read_before = _read(mrna_original)
        after, read_after = _read(mrna_changed)
        assert after is not None and after != before
        assert set(read_before) | set(read_after) <= set(table)
        assert _correct(q) == " → ".join(after)
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4 and sum(t == " → ".join(after) for t in texts) == 1
        assert " → ".join(before) in texts  # the unchanged protein is offered as a wrong answer
        misread, read_misread = _read(changed.replace("T", "U"))
        assert misread is not None and set(read_misread) <= set(table)
        assert "Translation starts at the start codon (AUG)" in q["stem"]


def test_new_protein_stimulus_states_the_table_rule():
    stim = _set("only-new-protein", "new_protein_after_change")["groups"][0]["stimulus"]
    assert "do not need to memorize" in stim["intro"]
    assert len(stim["tables"]) == 1 and "codon" in stim["tables"][0]["rows"][0]


# ---- effect_on_protein ---------------------------------------------------------------------

TEXT_TO_CATEGORY = {text: category for category, text in me.EFFECT_TEXT.items()}


def test_effect_item_has_exactly_one_true_description_matching_the_independent_category():
    seen = set()
    for seed in SEEDS:
        out = _set(seed, "effect_on_protein")
        q = _only(out, "effect_on_protein")
        original, changed = _strands(q)
        table = _table(out)
        before, read_before = _read("".join(TEMPLATE_PAIR[b] for b in original))
        after, read_after = _read("".join(TEMPLATE_PAIR[b] for b in changed))
        assert set(read_before) | set(read_after) <= set(table)
        category = _category(before, after)
        kind, _ = _single_edit_positions(original, changed)
        assert category is not None and (category == "several_differ") == (kind != "substitution")
        assert sorted(c["text"] for c in q["choices"]) == sorted(me.EFFECT_TEXT.values())
        assert _correct(q) == me.EFFECT_TEXT[category]
        seen.add(category)
        # every other description is false by the independent predicates
        for c in q["choices"]:
            assert c["correct"] == (TEXT_TO_CATEGORY[c["text"]] == category)
    assert seen == set(me.EFFECT_TEXT)


def test_indel_effect_items_never_end_early():
    for seed in SEEDS:
        q = _only(_set(seed, "effect_on_protein"), "effect_on_protein")
        original, changed = _strands(q)
        kind, _ = _single_edit_positions(original, changed)
        if kind != "substitution":
            assert _correct(q) == me.EFFECT_TEXT["several_differ"]


# ---- inheritance_of_mutation ---------------------------------------------------------------

GAMETE_KEY = "The mutation can be inherited by offspring if the changed {cell_word} takes part in fertilization."
BODY_KEY = "The mutation will not be passed to offspring, but cells that come from the changed body cell will carry it."


def test_inheritance_key_follows_the_cell_kind():
    seen = set()
    for seed in SEEDS:
        q = _only(_set(seed, "inheritance_of_mutation"), "inheritance_of_mutation")
        stem = q["stem"]
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4
        if "body cell" in stem:
            assert _correct(q) == BODY_KEY
            seen.add("body")
        else:
            word = "egg cell" if "egg cell" in stem else "sperm cell"
            assert _correct(q) == GAMETE_KEY.format(cell_word=word)
            seen.add(word)
        assert any(m in stem for m in me.MUTAGENS) and any(o in stem.lower() for o in me.ORGANISMS)
        assert all(c["rationale"] for c in q["choices"])
    assert seen == {"body", "egg cell", "sperm cell"}


# ---- defend_claim_about_change -------------------------------------------------------------

COUNTERCLAIMS = {
    "unchanged": "Every change in the DNA sequence changes the protein.",
    "other": "A change of one nucleotide cannot change the protein.",
}


def test_claim_item_is_constructed_response_with_a_computed_model_answer_and_the_right_counterclaim():
    for seed in SEEDS[:80]:
        out = _set(seed, "defend_claim_about_change")
        q = _only(out, "defend_claim_about_change")
        assert q["question_type"] == "constructed_response" and q["choices"] == [] and q["dok"] == 3
        original, changed = _strands(q)
        mrna_original = "".join(TEMPLATE_PAIR[b] for b in original)
        mrna_changed = "".join(TEMPLATE_PAIR[b] for b in changed)
        before, _ = _read(mrna_original)
        after, _ = _read(mrna_changed)
        category = _category(before, after)
        kind, _ = _single_edit_positions(original, changed)
        assert f"5′-{mrna_original}-3′" in q["answer"] and f"5′-{mrna_changed}-3′" in q["answer"]
        assert " → ".join(before) in q["answer"] and " → ".join(after) in q["answer"]
        assert f"this {kind}" in q["answer"]
        counter = COUNTERCLAIMS["unchanged" if category == "unchanged" else "other"]
        assert counter in q["stem"]
        assert "the displayed strands and codon table, and the derived amino acid sequences" in q["stem"]
        assert q["explanation"].count("(1)") == 1 and "(4)" in q["explanation"]
        assert ("frameshift" in q["answer"].lower()) == (kind != "substitution")


# ---- family-wide guards --------------------------------------------------------------------

BANNED = (
    "silent",
    "missense",
    "nonsense",
    "initiation",
    "elongation",
    "termination",
    "prophase",
    "metaphase",
    "anaphase",
    "telophase",
)
ALL_KEYS = [t.key for t in me.MutationEffects.templates]


def _full(seed: str) -> dict:
    return generate_set(me.MutationEffects(), seed, len(ALL_KEYS))


def _items(out: dict):
    for g in out["groups"]:
        yield from g["questions"]


def _all_text(out: dict) -> list[str]:
    texts = []
    for g in out["groups"]:
        texts += [g["stimulus"]["title"], g["stimulus"]["intro"]]
        for q in g["questions"]:
            texts += [q["stem"], q["answer"], q["explanation"]]
            texts += [c["text"] + " " + c["rationale"] for c in q["choices"]]
    return texts


def test_templates_and_doks():
    assert {t.key: t.dok for t in me.MutationEffects.templates} == {
        "identify_mutation_type": 1,
        "new_protein_after_change": 2,
        "effect_on_protein": 2,
        "inheritance_of_mutation": 2,
        "defend_claim_about_change": 3,
    }


def test_vocabulary_guard():
    for seed in SEEDS:
        blob = " ".join(_all_text(_full(seed))).lower()
        for word in BANNED:
            assert word not in blob, (seed, word)


def test_frameshift_is_taught_for_every_indel_item_and_never_for_a_substitution_item():
    for seed in SEEDS:
        for q in _items(_full(seed)):
            if q["template_key"] == "inheritance_of_mutation":
                continue
            original, changed = _strands(q)
            kind, _ = _single_edit_positions(original, changed)
            parts = [q["explanation"]] + [c["rationale"] for c in q["choices"]]
            if q["question_type"] == "constructed_response":
                parts.append(q["answer"])  # a multiple-choice answer is only the key's text
            for text in parts:
                assert ("frameshift" in text.lower()) == (kind != "substitution"), (seed, q["template_key"], text[:80])


def test_no_item_leaks_another_items_key_in_the_same_set():
    for seed in SEEDS:
        out = _full(seed)
        group = out["groups"][0]
        qs = {q["template_key"]: q for q in group["questions"]}
        protein_key = _correct(qs["new_protein_after_change"])
        for key, q in qs.items():
            visible = q["stem"] + " " + group["stimulus"]["intro"]
            if key != "new_protein_after_change":
                assert protein_key not in visible, (seed, key)
        # the four strand items use four different genes
        strand_items = (
            "identify_mutation_type",
            "new_protein_after_change",
            "effect_on_protein",
            "defend_claim_about_change",
        )
        originals = [_strands(qs[k])[0] for k in strand_items]
        assert len(set(originals)) == 4


def test_a_full_set_has_one_codon_table_within_bounds_and_single_template_sets_only_what_they_need():
    for seed in SEEDS:
        tables = _full(seed)["groups"][0]["stimulus"]["tables"]
        assert len(tables) == 1 and 12 <= len(tables[0]["rows"]) <= 36
    assert _set("one", "identify_mutation_type")["groups"][0]["stimulus"]["tables"] == []
    assert _set("one", "inheritance_of_mutation")["groups"][0]["stimulus"]["tables"] == []
