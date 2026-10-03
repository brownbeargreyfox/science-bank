"""Independent checks for dna-protein-synthesis (B-LS1-1).

Ground truth below is typed by amino acid and by base pair, not imported from the module under test.
"""

import json

from app.services.engine.core import Rng
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
