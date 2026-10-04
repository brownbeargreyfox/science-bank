"""EOCEP practice scans and classroom guarantees for B-LS1-1, B-LS3-2, and B-LS4-4."""

import hashlib
import json
import re

import pytest

from app.core.config import get_settings
from app.services.engine.family import generate_set
from app.services.families.registry import FAMILIES

SEEDS = [f"eocep-{i}" for i in range(60)]
FAMILY_STANDARD = {
    "dna-protein-synthesis": "B-LS1-1",
    "mutation-effects": "B-LS3-2",
    "natural-selection-trend": "B-LS4-4",
}
SEQUENCE_KEYS = ["transcribe_mrna", "translate_mrna", "dna_to_protein"]
TEMPLATE_PAIR = {"A": "U", "T": "A", "G": "C", "C": "G"}


def _constraints() -> dict:
    path = get_settings().standards_dir / "SC" / "2026-2027" / "biology-1-eocep.json"
    return json.loads(path.read_text())["constraints"]


def _selected_response_keys(family) -> list[str]:
    return [template.key for template in family.templates if template.question_type != "constructed_response"]


def _student_text(out: dict) -> str:
    """Everything student-visible, excluding hidden generation parameters."""
    shown = [{key: value for key, value in group.items() if key != "parameters"} for group in out["groups"]]
    return json.dumps(shown, ensure_ascii=False).replace("′", "'").replace("’", "'")


def _hits(text: str, banned: list[str]) -> list[str]:
    normalised = text.replace("′", "'").replace("’", "'")
    return [term for term in banned if re.search(r"(?<!\w)" + re.escape(term), normalised, re.IGNORECASE)]


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _shape(out: dict) -> list:
    return [
        [
            (
                question["template_key"],
                question["dok"],
                len(question["choices"]),
            )
            for question in group["questions"]
        ]
        for group in out["groups"]
    ]


@pytest.mark.parametrize("code", ["B-LS1-1", "B-LS3-2", "B-LS4-4"])
def test_scan_finds_every_planted_banned_term(code):
    banned = _constraints()[code]["banned_terms"]
    for term in banned:
        assert _hits(f"A stem that says {term} somewhere.", banned) == [term], term
    assert "3'" in _hits("template 3′-TACGGG-5′", _constraints()["B-LS1-1"]["banned_terms"])


def test_scan_does_not_flag_ordinary_numbers():
    banned = _constraints()["B-LS1-1"]["banned_terms"]
    assert (
        _hits(
            "Cell type P had 35 of 45 surviving, 13 or 15 in all; 53% and 35%; the first 3 and last 5 codons.", banned
        )
        == []
    )


def test_classroom_dna_output_contains_strand_ends_as_scan_positive_control():
    banned = _constraints()["B-LS1-1"]["banned_terms"]
    out = generate_set(FAMILIES["dna-protein-synthesis"], "positive-control", 8, template_keys=SEQUENCE_KEYS)
    assert {"3'", "5'"} <= set(_hits(_student_text(out), banned))


@pytest.mark.parametrize("key", list(FAMILY_STANDARD))
def test_eocep_output_has_no_banned_terms(key):
    family = FAMILIES[key]
    banned = _constraints()[FAMILY_STANDARD[key]]["banned_terms"]
    for seed in SEEDS:
        out = generate_set(family, seed, 8, template_keys=_selected_response_keys(family), eocep=True)
        assert _hits(_student_text(out), banned) == [], (key, seed)


@pytest.mark.parametrize("key", ["mutation-effects", "natural-selection-trend", "trait-probability", "reaction-rate"])
def test_families_that_do_not_render_differently_are_identical_in_both_modes(key):
    family = FAMILIES[key]
    assert family.eocep_aware is False
    for seed in SEEDS[:20]:
        assert _digest(generate_set(family, seed, 8)) == _digest(generate_set(family, seed, 8, eocep=True))


def test_only_dna_family_is_eocep_aware():
    assert {key for key, family in FAMILIES.items() if family.eocep_aware} == {"dna-protein-synthesis"}


def test_dna_classroom_output_is_same_whether_or_not_eocep_flag_is_named():
    family = FAMILIES["dna-protein-synthesis"]
    for seed in SEEDS[:20]:
        assert _digest(generate_set(family, seed, 8)) == _digest(generate_set(family, seed, 8, eocep=False))


def test_dna_eocep_keeps_scenarios_keys_and_choice_counts():
    family = FAMILIES["dna-protein-synthesis"]
    for seed in SEEDS:
        classroom = generate_set(family, seed, 8, template_keys=_selected_response_keys(family))
        eocep = generate_set(family, seed, 8, template_keys=_selected_response_keys(family), eocep=True)
        assert _shape(classroom) == _shape(eocep), seed
        assert [group["parameters"]["genes"] for group in classroom["groups"]] == [
            group["parameters"]["genes"] for group in eocep["groups"]
        ]
        assert _digest(classroom) != _digest(eocep)


def test_dna_eocep_codon_table_covers_every_codon_student_must_read():
    family = FAMILIES["dna-protein-synthesis"]
    seen = {"translate_mrna": 0, "dna_to_protein": 0}
    for seed in SEEDS:
        out = generate_set(family, seed, 8, template_keys=SEQUENCE_KEYS, eocep=True)
        for group in out["groups"]:
            table = next(table for table in group["stimulus"]["tables"] if table["caption"].startswith("Codon table"))
            assert table["caption"] == "Codon table (mRNA codons)"
            shown = {row["codon"] for row in table["rows"]}
            for question in group["questions"]:
                if question["template_key"] == "translate_mrna":
                    mrna = re.search(r"is ([ACGU]+), read from left to right", question["stem"]).group(1)
                elif question["template_key"] == "dna_to_protein":
                    template = re.search(r"is ([ACGT]+), read from left to right", question["stem"]).group(1)
                    mrna = "".join(TEMPLATE_PAIR[base] for base in template)
                else:
                    continue
                seen[question["template_key"]] += 1
                needed = {mrna[index : index + 3] for index in range(0, len(mrna), 3)}
                assert needed <= shown, (seed, question["template_key"], needed - shown)
    assert all(seen.values()), seen


def test_dna_eocep_transcribe_key_pairs_the_strand_shown():
    family = FAMILIES["dna-protein-synthesis"]
    checked = 0
    for seed in SEEDS:
        out = generate_set(family, seed, 4, template_keys=["transcribe_mrna"], eocep=True)
        for question in (question for group in out["groups"] for question in group["questions"]):
            template = re.search(r"is ([ACGT]+), read from left to right", question["stem"]).group(1)
            expected = "".join(TEMPLATE_PAIR[base] for base in template)
            assert [choice["text"] for choice in question["choices"] if choice["correct"]] == [expected], seed
            assert sum(choice["text"] == expected for choice in question["choices"]) == 1
            checked += 1
    assert checked == len(SEEDS) * 4


def test_dna_eocep_transcribe_never_offers_the_reverse_complement_as_a_wrong_answer():
    family = FAMILIES["dna-protein-synthesis"]
    for seed in SEEDS:
        out = generate_set(family, seed, 4, template_keys=["transcribe_mrna"], eocep=True)
        for question in (question for group in out["groups"] for question in group["questions"]):
            correct = next(choice["text"] for choice in question["choices"] if choice["correct"])
            assert all(choice["correct"] or choice["text"] != correct[::-1] for choice in question["choices"]), seed


def test_dna_eocep_states_direction_in_words_and_not_primes():
    out = generate_set(FAMILIES["dna-protein-synthesis"], "words", 12, template_keys=SEQUENCE_KEYS, eocep=True)
    text = _student_text(out)
    assert "left to right" in text
    assert "'" not in text
    for group in out["groups"]:
        for question in group["questions"]:
            if question["template_key"] == "transcribe_mrna":
                assert re.fullmatch(r"[ACGU]+", next(c["text"] for c in question["choices"] if c["correct"]))


def test_dna_eocep_reversed_distractors_are_explained_without_ends():
    rationales = set()
    for seed in SEEDS:
        out = generate_set(
            FAMILIES["dna-protein-synthesis"], seed, 8, template_keys=["translate_mrna", "dna_to_protein"], eocep=True
        )
        for group in out["groups"]:
            for question in group["questions"]:
                rationales |= {
                    choice["rationale"] for choice in question["choices"] if "reverse" in choice["rationale"]
                }
    assert rationales == {
        "The amino acids are in reverse order. "
        "Codons are read in order from the first codon, at the left end of the mRNA."
    }
