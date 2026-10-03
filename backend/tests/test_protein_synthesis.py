"""Independent checks for dna-protein-synthesis (B-LS1-1).

Ground truth below is typed by amino acid and by base pair, not imported from the module under test.
"""

import json
import re

from app.services.engine.core import Rng
from app.services.engine.family import generate_set
from app.services.families import protein_synthesis as ps

SEEDS = [f"dps-{i}" for i in range(200)]
BY_AMINO = {
    "Phenylalanine": ["UUU", "UUC"],
    "Leucine": ["UUA", "UUG", "CUU", "CUC", "CUA", "CUG"],
    "Isoleucine": ["AUU", "AUC", "AUA"],
    "Methionine": ["AUG"],
    "Valine": ["GUU", "GUC", "GUA", "GUG"],
    "Serine": ["UCU", "UCC", "UCA", "UCG", "AGU", "AGC"],
    "Proline": ["CCU", "CCC", "CCA", "CCG"],
    "Threonine": ["ACU", "ACC", "ACA", "ACG"],
    "Alanine": ["GCU", "GCC", "GCA", "GCG"],
    "Tyrosine": ["UAU", "UAC"],
    "Stop": ["UAA", "UAG", "UGA"],
    "Histidine": ["CAU", "CAC"],
    "Glutamine": ["CAA", "CAG"],
    "Asparagine": ["AAU", "AAC"],
    "Lysine": ["AAA", "AAG"],
    "Aspartic acid": ["GAU", "GAC"],
    "Glutamic acid": ["GAA", "GAG"],
    "Cysteine": ["UGU", "UGC"],
    "Tryptophan": ["UGG"],
    "Arginine": ["CGU", "CGC", "CGA", "CGG", "AGA", "AGG"],
    "Glycine": ["GGU", "GGC", "GGA", "GGG"],
}
CODE = {codon: name for name, codons in BY_AMINO.items() for codon in codons}
STOPS = set(BY_AMINO["Stop"])
TEMPLATE_OF = {"A": "T", "U": "A", "G": "C", "C": "G"}  # mRNA base -> template base
TEMPLATE_PAIR = {"A": "U", "T": "A", "G": "C", "C": "G"}  # template base -> mRNA base


def _scenario(seed: str) -> dict:
    return ps.draw_scenario(Rng("scenario", seed))


def _triples(strand: str) -> list[str]:
    return [strand[i : i + 3] for i in range(0, len(strand), 3)]


# ---- data and helpers ----------------------------------------------------------------------


def test_genetic_code_matches_the_reviewed_table():
    assert len(CODE) == 64
    assert set(ps.CODONS) == set(CODE)
    for codon, letter in ps.CODONS.items():
        assert ps.AMINO_ACIDS.get(letter, "Stop") == CODE[codon], codon


def test_pairing_and_reading_helpers():
    assert ps.transcribe("TACGGATTC") == "AUGCCUAAG"
    assert ps.template_for("AUGCCUAAG") == "TACGGATTC"
    assert ps.codons_of("AUGCCUAAG") == ["AUG", "CCU", "AAG"]
    assert ps.translate(["AUG", "CCU", "UAA", "GGG"]) == ["Methionine", "Proline"]
    assert ps.table_label("AUG") == "Methionine (start)"
    assert ps.table_label("UAA") == "Stop"
    assert ps.table_label("CCU") == "Proline"
    assert ps.strand_text("AUG", "5", "3") == "5′-AUG-3′"


def test_validity_predicates_reject_ambiguous_proteins():
    good = {"protein": ["Methionine", "Serine", "Proline", "Lysine"]}
    assert ps.translate_gene_ok(good)
    assert not ps.translate_gene_ok({"protein": ["Methionine", "Serine", "Serine", "Lysine"]})  # swapped == key
    palindrome = {"protein": ["Serine", "Proline", "Serine"]}
    assert not ps.translate_gene_ok(palindrome)  # reversed == key


# ---- scenario ------------------------------------------------------------------------------


def test_scenario_genes_are_valid_json_safe_and_independent():
    for seed in SEEDS:
        s = _scenario(seed)
        json.dumps(s)
        assert set(s["genes"]) == {"transcribe", "translate", "protein"}
        assert len({g["label"] for g in s["genes"].values()}) == 3
        for g in s["genes"].values():
            codons = g["codons"]
            assert codons[0] == "AUG" and codons[-1] in STOPS
            sense = codons[1:-1]
            assert 3 <= len(sense) <= 5
            assert not (STOPS | {"AUG"}) & set(sense)
            assert g["mrna"] == "".join(codons) and 15 <= len(g["mrna"]) <= 21
            assert g["template"] == "".join(TEMPLATE_OF[b] for b in g["mrna"])
            assert g["protein"] == [CODE[c] for c in codons[:-1]]


def test_scenarios_always_support_four_distinct_choices():
    for seed in SEEDS:
        genes = _scenario(seed)["genes"]
        assert len(ps.transcribe_candidates(genes["transcribe"])) >= 3
        assert ps.translate_gene_ok(genes["translate"])
        assert ps.protein_gene_ok(genes["protein"])


def test_codon_table_is_exact_and_self_contained():
    for seed in SEEDS:
        s = _scenario(seed)
        rows = s["codon_table"]
        codons = [r["codon"] for r in rows]
        assert codons == sorted(codons) and len(set(codons)) == len(codons)
        assert 10 <= len(rows) <= 26
        for r in rows:
            name = CODE[r["codon"]]
            expected = "Methionine (start)" if r["codon"] == "AUG" else name
            assert r["amino_acid"] == expected
        g2, g3 = s["genes"]["translate"], s["genes"]["protein"]
        misread = _triples(g3["template"].replace("T", "U"))
        needed = set(g2["codons"]) | set(g3["codons"]) | set(misread)
        assert needed <= set(codons)
        assert len(set(codons) - needed) in (2, 3)
        assert not any(CODE[c] == "Stop" for c in misread)


def test_activity_table_covers_each_category_once():
    for seed in SEEDS:
        rows = _scenario(seed)["activity"]
        assert [r["gene"] for r in rows] == ["Gene A", "Gene B", "Gene C", "Gene D"]
        assert sorted((r["p"], r["q"]) for r in rows) == [(False, False), (False, True), (True, False), (True, True)]


STRAND = re.compile(r"([35])′-([ACGTU]+)-([35])′")


def _set(seed: str, *keys: str) -> dict:
    return generate_set(ps.DnaProteinSynthesis(), seed, len(keys), template_keys=list(keys))


def _only(out: dict, key: str) -> dict:
    return next(q for g in out["groups"] for q in g["questions"] if q["template_key"] == key)


def _correct(q: dict) -> str:
    return next(c["text"] for c in q["choices"] if c["correct"])


def _table(out: dict) -> dict[str, str]:
    tables = out["groups"][0]["stimulus"]["tables"]
    return {r["codon"]: r["amino_acid"] for r in next(t for t in tables if "codon" in t["rows"][0])["rows"]}


# ---- registration and catalog --------------------------------------------------------------


def test_family_is_registered_and_bound_to_biology_1_only():
    from app.services.families.registry import FAMILIES

    fam = FAMILIES["dna-protein-synthesis"]
    assert fam.version == "1.0.0"
    assert [(b.state, b.course_slug, b.code) for b in fam.bindings] == [("SC", "biology-1", "B-LS1-1")]
    assert all(t.standard_code is None for t in fam.templates)


# ---- transcribe_mrna -----------------------------------------------------------------------


def test_transcribe_key_is_the_complement_of_the_displayed_template():
    for seed in SEEDS:
        q = _only(_set(seed, "transcribe_mrna"), "transcribe_mrna")
        left, template, right = STRAND.findall(q["stem"])[0]
        assert (left, right) == ("3", "5")
        expected = "5′-" + "".join(TEMPLATE_PAIR[b] for b in template) + "-3′"
        assert _correct(q) == expected
        texts = [c["text"] for c in q["choices"]]
        assert len(texts) == len(set(texts)) == 4
        assert all(re.fullmatch(r"5′-[ACGTU]+-3′", t) for t in texts)
        assert sum(t == expected for t in texts) == 1


def test_transcribe_stimulus_has_no_codon_or_activity_table():
    out = _set("only-transcribe", "transcribe_mrna")
    assert out["groups"][0]["stimulus"]["tables"] == []


# ---- translate_mrna ------------------------------------------------------------------------


def test_translate_key_follows_the_displayed_mrna_and_table():
    for seed in SEEDS:
        out = _set(seed, "translate_mrna")
        q = _only(out, "translate_mrna")
        left, mrna, right = STRAND.findall(q["stem"])[0]
        assert (left, right) == ("5", "3") and mrna.startswith("AUG")
        table = _table(out)
        names = []
        for codon in _triples(mrna):
            assert codon in table, f"{codon} missing from the displayed table"
            if table[codon] == "Stop":
                break
            names.append(CODE[codon])
        assert _correct(q) == " → ".join(names)
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4
        assert sum(t == " → ".join(names) for t in texts) == 1


def test_translate_stimulus_states_the_table_rule_and_has_no_activity_table():
    out = _set("only-translate", "translate_mrna")
    stim = out["groups"][0]["stimulus"]
    assert "do not need to memorize" in stim["intro"]
    assert len(stim["tables"]) == 1 and "codon" in stim["tables"][0]["rows"][0]


# ---- dna_to_protein and explain_dna_to_protein ---------------------------------------------


def test_dna_to_protein_key_is_the_two_step_result_and_table_is_complete():
    for seed in SEEDS:
        out = _set(seed, "dna_to_protein")
        q = _only(out, "dna_to_protein")
        left, template, right = STRAND.findall(q["stem"])[0]
        assert (left, right) == ("3", "5")
        mrna = "".join(TEMPLATE_PAIR[b] for b in template)
        table = _table(out)
        names = []
        for codon in _triples(mrna):
            assert codon in table
            if table[codon] == "Stop":
                break
            names.append(CODE[codon])
        expected = " → ".join(names)
        assert _correct(q) == expected
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4 and sum(t == expected for t in texts) == 1
        # the template read directly as codons is offered, and every codon it uses is in the table
        misread = _triples(template.replace("T", "U"))
        assert set(misread) <= set(table) and "Stop" not in {table[c] for c in misread}
        assert " → ".join(CODE[c] for c in misread) in texts


def test_explain_item_is_constructed_response_with_a_computed_model_answer():
    for seed in SEEDS[:60]:
        out = _set(seed, "explain_dna_to_protein")
        q = _only(out, "explain_dna_to_protein")
        assert q["question_type"] == "constructed_response" and q["choices"] == [] and q["dok"] == 3
        left, template, right = STRAND.findall(q["stem"])[0]
        mrna = "".join(TEMPLATE_PAIR[b] for b in template)
        table = _table(out)
        names = []
        for codon in _triples(mrna):
            if table[codon] == "Stop":
                break
            names.append(CODE[codon])
        assert f"5′-{mrna}-3′" in q["answer"] and " → ".join(names) in q["answer"]
        assert q["explanation"].count("(1)") == 1 and "(3)" in q["explanation"]
        assert "do not need to memorize" in out["groups"][0]["stimulus"]["intro"]


# ---- gene_activity_by_cell -----------------------------------------------------------------

PHRASE = {
    "active in cell type P only": (True, False),
    "active in cell type Q only": (False, True),
    "active in both cell types": (True, True),
    "not active in either cell type": (False, False),
}


def test_activity_item_has_exactly_one_supported_statement():
    for seed in SEEDS:
        out = _set(seed, "gene_activity_by_cell")
        q = _only(out, "gene_activity_by_cell")
        stim = out["groups"][0]["stimulus"]
        table = next(t for t in stim["tables"] if "gene" in t["rows"][0])
        truth = {r["gene"]: (r["p"] == "Active", r["q"] == "Active") for r in table["rows"]}
        supported = []
        for c in q["choices"]:
            m = re.fullmatch(r"(Gene [A-D]) is (.+)\.", c["text"])
            assert m and m.group(2) in PHRASE, c["text"]
            if PHRASE[m.group(2)] == truth[m.group(1)]:
                supported.append(c["text"])
            assert c["correct"] == (PHRASE[m.group(2)] == truth[m.group(1)])
        assert len(supported) == 1 and supported[0] == _correct(q)
        assert len({c["text"].split(" is ")[0] for c in q["choices"]}) == 4  # one claim per gene
        assert "same DNA" in stim["intro"]


def test_activity_stimulus_has_no_codon_table():
    out = _set("only-activity", "gene_activity_by_cell")
    tables = out["groups"][0]["stimulus"]["tables"]
    assert len(tables) == 1 and "gene" in tables[0]["rows"][0]


# ---- family-wide guards --------------------------------------------------------------------

BANNED = (
    "mutation",
    "mutate",
    "frameshift",
    "silent",
    "missense",
    "nonsense",
    "initiation",
    "elongation",
    "termination",
)
ALL_KEYS = [t.key for t in ps.DnaProteinSynthesis.templates]


def _full(seed: str) -> dict:
    return generate_set(ps.DnaProteinSynthesis(), seed, len(ALL_KEYS))


def _all_text(out: dict) -> list[str]:
    texts = []
    for g in out["groups"]:
        texts += [g["stimulus"]["title"], g["stimulus"]["intro"]]
        for q in g["questions"]:
            texts += [q["stem"], q["answer"], q["explanation"]]
            texts += [c["text"] + " " + c["rationale"] for c in q["choices"]]
    return texts


def test_templates_and_doks():
    doks = {t.key: t.dok for t in ps.DnaProteinSynthesis.templates}
    assert doks == {
        "transcribe_mrna": 1,
        "translate_mrna": 1,
        "dna_to_protein": 2,
        "gene_activity_by_cell": 2,
        "explain_dna_to_protein": 3,
    }


def test_no_mutation_or_biochemistry_vocabulary_anywhere():
    for seed in SEEDS:
        blob = " ".join(_all_text(_full(seed))).lower()
        for word in BANNED:
            assert word not in blob, (seed, word)
        assert "a single gene codes for a protein" not in blob


def test_no_item_leaks_another_items_key_in_the_same_set():
    for seed in SEEDS:
        out = _full(seed)
        group = out["groups"][0]
        qs = {q["template_key"]: q for q in group["questions"]}
        transcribe_key = _correct(qs["transcribe_mrna"])
        translate_key = _correct(qs["translate_mrna"])
        protein_key = _correct(qs["dna_to_protein"])
        for key, q in qs.items():
            visible = q["stem"] + " " + group["stimulus"]["intro"]
            if key != "transcribe_mrna":
                assert transcribe_key not in visible, (seed, key)
            assert protein_key not in visible, (seed, key)
            assert translate_key not in visible, (seed, key)
        # the three sequence items use three different genes
        strands = [STRAND.findall(qs[k]["stem"])[0][1] for k in ("transcribe_mrna", "translate_mrna", "dna_to_protein")]
        assert len(set(strands)) == 3


def test_a_full_set_shares_one_table_that_covers_every_sequence_item():
    for seed in SEEDS:
        out = _full(seed)
        tables = out["groups"][0]["stimulus"]["tables"]
        assert len(tables) == 2  # codon table and activity table
        codon_rows = next(t for t in tables if "codon" in t["rows"][0])["rows"]
        assert 10 <= len(codon_rows) <= 26


def test_single_template_requests_include_only_what_they_need():
    assert _set("one", "transcribe_mrna")["groups"][0]["stimulus"]["tables"] == []
    only_activity = _set("one", "gene_activity_by_cell")["groups"][0]["stimulus"]["tables"]
    assert [list(t["rows"][0]) for t in only_activity] == [["gene", "p", "q"]]


# ---- review fixes --------------------------------------------------------------------------


def test_the_key_is_never_the_only_choice_that_starts_like_a_protein_or_an_mrna():
    for seed in SEEDS:
        transcribe = _only(_set(seed, "transcribe_mrna"), "transcribe_mrna")
        assert sum(c["text"].startswith("5′-AUG") for c in transcribe["choices"]) >= 2, seed
        for key in ("translate_mrna", "dna_to_protein"):
            q = _only(_set(seed, key), key)
            assert sum(c["text"].startswith("Methionine") for c in q["choices"]) >= 2, (seed, key)


def test_rationales_read_cleanly():
    for seed in SEEDS:
        for text in _all_text(_full(seed)):
            assert "not not" not in text, (seed, text)


def test_transcription_is_not_described_as_copying_the_template():
    for seed in SEEDS[:40]:
        out = _full(seed)
        explain = _only(out, "explain_dna_to_protein")
        assert "copies" not in out["groups"][0]["stimulus"]["intro"].lower()
        assert "copies" not in explain["answer"].lower()
