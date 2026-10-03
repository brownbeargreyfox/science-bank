# DNA to Protein (B-LS1-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the deterministic `dna-protein-synthesis` question family for Biology 1 B-LS1-1: five templates built from a DNA template strand, the standard genetic code, and a displayed partial codon table.

**Architecture:** One new module `families/protein_synthesis.py` holds the genetic code, pure helpers (transcribe, translate, distractor builders and their validity predicates), a `draw_scenario(rng)` function, and the `DnaProteinSynthesis` family class. A scenario holds three independent genes (one per sequence item role, so no item's stem leaks another's key), one shared codon table covering every codon any choice needs, and a four-gene activity table. Templates are added task by task; the registry, the standards-data flag, golden digests, and docs land last.

**Tech Stack:** Python 3.12, the existing question-family engine (`app/services/engine`), pytest. No migration, no frontend change (stimulus tables are generic).

**Spec:** `docs/superpowers/specs/2026-10-02-dna-protein-synthesis-design.md`

## Global Constraints

- Deterministic: randomness only through `Rng`; no `random`, no Python `hash()`; version `1.0.0`. Any later output change bumps the version and the golden digest in the same commit.
- Keys and distractors are computed from values the student sees (strands in the stem, codon table, activity table). No effect-of-change items (B-LS3-2), no initiation/elongation/termination, no real genes or proteins, no specific cell types.
- Student-facing material must not say "a single gene codes for a protein"; use "a gene contains instructions for an amino-acid sequence (a protein)" if the idea is stated.
- Every MC item has exactly four distinct choices, one key, a rationale for each; constructed response has an empty choice list.
- Classroom-only: EOCEP mode stays rejected for B-LS1-1 (no constraints imported). Bound only to `SC / biology-1 / B-LS1-1`.
- Codon table: alphabetical, every codon any choice needs, 2 or 3 extra codons, `AUG` labelled `Methionine (start)`, stop codons labelled `Stop`, and the stimulus tells students to use the displayed table (no memorizing).
- All mRNA strings in choices are labelled `5′-…-3′`; template strands `3′-…-5′` (prime is U+2032).
- Backend commands run from `backend/`; `.venv/bin/ruff check app tests` and `.venv/bin/ruff format app tests` (line length 120) must be clean; engine tests need no database; `test_api.py` needs `TEST_DATABASE_URL` against a throwaway Postgres (port 54332, container `sb-testdb`, never production).

## Review Focus

- A distractor that is actually correct (the coding strand gives the same protein; a palindromic or repeated sequence makes reversed or swapped equal the key): every item has exactly one choice equal to an independently computed key (Tasks 2, 3, 5).
- A codon needed by a choice missing from the displayed table: checked across 200 seeds against the independent genetic code (Tasks 1, 3).
- A key visible in another item's stem or stimulus within the same set (for example the transcribe key mRNA appearing in a translate stem): leak test across all templates in one set (Task 5).
- Asking for only one template: the stimulus contains only what that template needs (no codon table for transcribe or activity items; no activity table for sequence items) (Tasks 2, 4).
- Largest scenarios (five sense codons, maximum table): table stays within 26 rows and every stem stays one sentence-length block (Tasks 1, 5).

## File map

| File | Responsibility |
|---|---|
| `backend/app/services/families/protein_synthesis.py` (create) | genetic code, helpers, `draw_scenario`, `DnaProteinSynthesis` |
| `backend/tests/test_protein_synthesis.py` (create) | independent checks |
| `backend/app/services/families/registry.py` (modify) | register the family |
| `data/standards/SC/2026-2027/biology-1.json` (modify) | `question_family_candidate: true` on B-LS1-1 |
| `backend/tests/test_engine.py` (modify) | golden digest for the new family |
| `backend/tests/test_api.py` (modify) | generation matrix row, EOCEP denial, Biology 2 mismatch |
| `HANDOFF.md`, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`, `QUESTION_FAMILY_CATALOG.md` (modify) | docs |

---

### Task 1: Genetic code, pure helpers, and scenario

**Files:**
- Create: `backend/app/services/families/protein_synthesis.py`
- Create: `backend/tests/test_protein_synthesis.py`

**Interfaces:**
- Produces (module level, all importable as `from app.services.families import protein_synthesis as ps`):
  - `AMINO_ACIDS: dict[str, str]` one-letter → name; `CODONS: dict[str, str]` 64 RNA codons → one-letter or `"*"`.
  - `START = "AUG"`, `SENSE_CODONS: tuple[str, ...]`, `STOP_CODONS: tuple[str, ...]`.
  - `transcribe(template: str) -> str`, `template_for(mrna: str) -> str`, `codons_of(strand: str) -> list[str]`, `translate(codons: list[str]) -> list[str]` (names, stops excluded and ends the chain), `table_label(codon: str) -> str`, `strand_text(seq: str, left: str, right: str) -> str`.
  - `transcribe_candidates(gene) -> list[tuple[str, str]]` (kind, wrong strand, distinct from the key and each other), `protein_options(gene) -> dict[str, list[str]]` with keys `reversed`, `no_start`, `swapped`, `template_as_mrna`.
  - `transcribe_gene_ok(gene) -> bool`, `translate_gene_ok(gene) -> bool`, `protein_gene_ok(gene) -> bool`.
  - `draw_gene(rng, label) -> dict` with keys `label`, `codons`, `mrna`, `template`, `protein`.
  - `draw_scenario(rng) -> dict` with keys `genes` (`transcribe`, `translate`, `protein`), `codon_table` (list of `{"codon","amino_acid"}` sorted by codon), `activity` (list of `{"gene","p","q"}` for `Gene A`..`Gene D`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_protein_synthesis.py`:

```python
"""Independent checks for dna-protein-synthesis (B-LS1-1).

Ground truth below is typed by amino acid and by base pair, not imported from the module under test.
"""

import json
import re

import pytest

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q`
Expected: FAIL at collection (`ImportError: cannot import name 'protein_synthesis'`).

- [ ] **Step 3: Write the module**

Create `backend/app/services/families/protein_synthesis.py`:

```python
"""DNA to protein (B-LS1-1): transcribe a template strand and translate the mRNA with a displayed codon table.

Curated data only: the standard genetic code. Every key is computed from the strands and table the student sees.
Scope follows the Biology 1 boundary: no initiation, elongation or termination steps, no named genes or proteins, and
no effects of sequence changes (those belong to B-LS3-2).
"""

from itertools import product
from typing import Any

from app.services.engine.core import GenerationError, Rng

# Standard genetic code. Codons are enumerated with U, C, A, G in each position; "*" marks a stop codon.
_CODE = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
AMINO_ACIDS = {
    "F": "Phenylalanine",
    "L": "Leucine",
    "S": "Serine",
    "Y": "Tyrosine",
    "C": "Cysteine",
    "W": "Tryptophan",
    "P": "Proline",
    "H": "Histidine",
    "Q": "Glutamine",
    "R": "Arginine",
    "I": "Isoleucine",
    "M": "Methionine",
    "T": "Threonine",
    "N": "Asparagine",
    "K": "Lysine",
    "V": "Valine",
    "A": "Alanine",
    "D": "Aspartic acid",
    "E": "Glutamic acid",
    "G": "Glycine",
}
CODONS: dict[str, str] = {"".join(bases): _CODE[i] for i, bases in enumerate(product("UCAG", repeat=3))}
START = "AUG"
SENSE_CODONS = tuple(sorted(c for c, x in CODONS.items() if x != "*" and c != START))
STOP_CODONS = tuple(sorted(c for c, x in CODONS.items() if x == "*"))

_MRNA_TO_TEMPLATE = {"A": "T", "U": "A", "G": "C", "C": "G"}
_TEMPLATE_TO_MRNA = {"A": "U", "T": "A", "G": "C", "C": "G"}
_TEMPLATE_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}
GENE_LABELS = ("Gene R2", "Gene K7", "Gene M4", "Gene T9", "Gene L3", "Gene H5")
ACTIVITY_GENES = ("Gene A", "Gene B", "Gene C", "Gene D")
MAX_GENE_DRAWS = 200


# ---- pure helpers ------------------------------------------------------------------------------


def transcribe(template: str) -> str:
    return "".join(_TEMPLATE_TO_MRNA[b] for b in template)


def template_for(mrna: str) -> str:
    return "".join(_MRNA_TO_TEMPLATE[b] for b in mrna)


def codons_of(strand: str) -> list[str]:
    return [strand[i : i + 3] for i in range(0, len(strand), 3)]


def translate(codons: list[str]) -> list[str]:
    """Amino acid names in order; a stop codon ends the chain and is not an amino acid."""
    names = []
    for codon in codons:
        letter = CODONS[codon]
        if letter == "*":
            break
        names.append(AMINO_ACIDS[letter])
    return names


def table_label(codon: str) -> str:
    if CODONS[codon] == "*":
        return "Stop"
    if codon == START:
        return "Methionine (start)"
    return AMINO_ACIDS[CODONS[codon]]


def strand_text(seq: str, left: str, right: str) -> str:
    return f"{left}′-{seq}-{right}′"


def transcribe_candidates(gene: dict[str, Any]) -> list[tuple[str, str]]:
    """Wrong mRNA strings a student might choose, each distinct from the key and from each other."""
    key, template = gene["mrna"], gene["template"]
    raw = [
        ("dna_complement", "".join(_TEMPLATE_COMPLEMENT[b] for b in template)),
        ("copied", template.replace("T", "U")),
        ("reversed", key[::-1]),
        ("gc_unchanged", "".join(b if b in "GC" else _TEMPLATE_TO_MRNA[b] for b in template)),
    ]
    seen = {key}
    out = []
    for kind, strand in raw:
        if strand not in seen:
            seen.add(strand)
            out.append((kind, strand))
    return out


def _swapped(protein: list[str]) -> list[str]:
    return [protein[0], protein[2], protein[1], *protein[3:]]


def protein_options(gene: dict[str, Any]) -> dict[str, list[str]]:
    p = gene["protein"]
    options = {"reversed": p[::-1], "no_start": p[1:], "swapped": _swapped(p)}
    if "template" in gene:
        options["template_as_mrna"] = translate(codons_of(gene["template"].replace("T", "U")))
    return options


def _distinct(options: list[list[str]]) -> bool:
    return len({tuple(o) for o in options}) == len(options)


def transcribe_gene_ok(gene: dict[str, Any]) -> bool:
    return len(transcribe_candidates(gene)) >= 3


def translate_gene_ok(gene: dict[str, Any]) -> bool:
    o = protein_options(gene)
    return _distinct([gene["protein"], o["reversed"], o["no_start"], o["swapped"]])


def protein_gene_ok(gene: dict[str, Any]) -> bool:
    misread = codons_of(gene["template"].replace("T", "U"))
    if any(CODONS[c] == "*" for c in misread):
        return False
    o = protein_options(gene)
    return _distinct([gene["protein"], o["template_as_mrna"], o["reversed"], o["no_start"]])


# ---- scenario ----------------------------------------------------------------------------------


def draw_gene(rng: Rng, label: str) -> dict[str, Any]:
    sense = [rng.choice(SENSE_CODONS) for _ in range(rng.randint(3, 5))]
    codons = [START, *sense, rng.choice(STOP_CODONS)]
    mrna = "".join(codons)
    return {
        "label": label,
        "codons": codons,
        "mrna": mrna,
        "template": template_for(mrna),
        "protein": translate(codons),
    }


def draw_scenario(rng: Rng) -> dict[str, Any]:
    labels = rng.sample(list(GENE_LABELS), 3)
    genes: dict[str, dict[str, Any]] = {}
    for role, label, ok in (
        ("transcribe", labels[0], transcribe_gene_ok),
        ("translate", labels[1], translate_gene_ok),
        ("protein", labels[2], protein_gene_ok),
    ):
        for _ in range(MAX_GENE_DRAWS):
            gene = draw_gene(rng, label)
            if ok(gene):
                genes[role] = gene
                break
        else:
            raise GenerationError(f"dna-protein-synthesis: no valid {role} gene after {MAX_GENE_DRAWS} draws")
    misread = codons_of(genes["protein"]["template"].replace("T", "U"))
    needed = set(genes["translate"]["codons"]) | set(genes["protein"]["codons"]) | set(misread)
    extras = rng.sample(sorted(set(SENSE_CODONS) - needed), rng.randint(2, 3))
    categories = rng.shuffled(["p_only", "q_only", "both", "neither"])
    activity = [
        {"gene": gene, "p": cat in ("p_only", "both"), "q": cat in ("q_only", "both")}
        for gene, cat in zip(ACTIVITY_GENES, categories, strict=True)
    ]
    return {
        "genes": genes,
        "codon_table": [{"codon": c, "amino_acid": table_label(c)} for c in sorted(needed | set(extras))],
        "activity": activity,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests`
Expected: all pass, ruff clean. If `test_codon_table_is_exact_and_self_contained` fails on the row bound, report the failing seed in a ledger ruling and widen the bound only if the spec's "within 26 rows" is still honored.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/families/protein_synthesis.py backend/tests/test_protein_synthesis.py
git commit -m "feat: genetic code, helpers, and scenario for the B-LS1-1 family"
```

---

### Task 2: Family class with transcribe and translate items; registry; standards flag

**Files:**
- Modify: `backend/app/services/families/protein_synthesis.py` (append the class)
- Modify: `backend/app/services/families/registry.py`
- Modify: `data/standards/SC/2026-2027/biology-1.json`
- Modify: `backend/tests/test_protein_synthesis.py` (append)

**Interfaces:**
- Consumes: everything Task 1 produces; `Binding`, `DraftChoice`, `DraftQuestion`, `TemplateSpec` from `app.services.engine.core`; `QuestionFamily` from `app.services.engine.family`.
- Produces: `DnaProteinSynthesis` (key `dna-protein-synthesis`, version `1.0.0`, `stimulus_kind = "dna_protein_synthesis"`) with templates `transcribe_mrna` and `translate_mrna`; private `_BASE_INTRO`; registered in `FAMILIES`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_protein_synthesis.py`:

```python
STRAND = re.compile(r"([35])′-([ACGTU]+)-([35])′")


def _set(seed: str, *keys: str) -> dict:
    return generate_set(ps.DnaProteinSynthesis(), seed, len(keys), template_keys=list(keys))


def _only(out: dict, key: str) -> dict:
    return next(q for g in out["groups"] for q in g["questions"] if q["template_key"] == key)


def _correct(q: dict) -> str:
    return next(c["text"] for c in q["choices"] if c["correct"])


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
        assert all(re.fullmatch(r"5′-[ACGU]+-3′", t) for t in texts)
        assert sum(t == expected for t in texts) == 1


def test_transcribe_stimulus_has_no_codon_or_activity_table():
    out = _set("only-transcribe", "transcribe_mrna")
    assert out["groups"][0]["stimulus"]["tables"] == []
```

And the translate tests:

```python
# ---- translate_mrna ------------------------------------------------------------------------


def _table(out: dict) -> dict[str, str]:
    tables = out["groups"][0]["stimulus"]["tables"]
    return {r["codon"]: r["amino_acid"] for r in next(t for t in tables if "codon" in t["rows"][0])["rows"]}


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q`
Expected: FAIL (`AttributeError: module ... has no attribute 'DnaProteinSynthesis'`).

- [ ] **Step 3: Append the class to the module**

Add these imports at the top of `protein_synthesis.py` (extend the existing import lines):

```python
from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily
```

Append:

```python
_BASE_INTRO = (
    "A gene is a region of DNA that contains instructions for an amino-acid sequence (a protein). A cell copies one "
    "strand of a gene, the template strand, into messenger RNA (mRNA) by transcription. At a ribosome, the mRNA is read "
    "in groups of three nucleotides called codons, and each codon specifies an amino acid. This is translation."
)
_TABLE_RULE = "Use the codon table shown. You do not need to memorize codons."
_SEQUENCE_KEYS = {"translate_mrna", "dna_to_protein", "explain_dna_to_protein"}

_TRANSCRIBE_WHY = {
    "dna_complement": "RNA contains uracil (U) instead of thymine (T), so a template A pairs with U, not T.",
    "copied": "This copies the template strand instead of pairing each base with its complement.",
    "reversed": (
        "The bases are in the wrong order: each mRNA base pairs with the template base directly across from it, in the "
        "same left-to-right position."
    ),
    "gc_unchanged": "G pairs with C and C pairs with G; this strand leaves the G and C bases unchanged.",
}
_PROTEIN_WHY = {
    "reversed": "The amino acids are in reverse order. Codons are read in order from the 5′ end of the mRNA.",
    "no_start": "Translation begins at the start codon, AUG, which specifies methionine. Methionine is the first amino acid.",
    "swapped": "Two amino acids are in the wrong order. Each codon is read in order from the 5′ end of the mRNA.",
    "template_as_mrna": (
        "This reads the DNA template strand directly as if it were mRNA. The template must first be transcribed into its "
        "complementary mRNA."
    ),
}


def sequence_text(names: list[str]) -> str:
    return " → ".join(names)


class DnaProteinSynthesis(QuestionFamily):
    key = "dna-protein-synthesis"
    version = "1.0.0"
    title = "DNA to protein: transcription and translation"
    description = (
        "Use a DNA template strand and a displayed codon table to transcribe an mRNA, translate it into an amino acid "
        "sequence, and explain how the order of nucleotides in a gene determines the protein."
    )
    stimulus_kind = "dna_protein_synthesis"
    bindings = (Binding("SC", "biology-1", "B-LS1-1"),)
    templates = (
        TemplateSpec("transcribe_mrna", "Transcribe a template strand", 1, "multiple_choice", "evidence", 4),
        TemplateSpec("translate_mrna", "Translate an mRNA", 1, "multiple_choice", "evidence", 5),
    )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        keys = set(template_keys)
        intro = [_BASE_INTRO]
        tables = []
        if keys & _SEQUENCE_KEYS:
            intro.append(_TABLE_RULE)
            tables.append(
                {
                    "caption": "Codon table (mRNA codons, read 5′ to 3′)",
                    "columns": [{"key": "codon", "label": "mRNA codon"}, {"key": "amino_acid", "label": "Amino acid"}],
                    "rows": params["codon_table"],
                }
            )
        return {
            "title": "From DNA to protein",
            "intro": " ".join(intro),
            "sections": [],
            "tables": tables,
            "charts": [],
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_transcribe_mrna(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["transcribe"]
        correct = strand_text(g["mrna"], "5", "3")
        wrong = rng.sample(transcribe_candidates(g), 3)
        choices = [
            DraftChoice(
                correct,
                True,
                "Correct: transcription pairs each template base with its complement (A–U, T–A, G–C, C–G).",
            )
        ] + [DraftChoice(strand_text(strand, "5", "3"), False, _TRANSCRIBE_WHY[kind]) for kind, strand in wrong]
        return DraftQuestion(
            stem=(
                f"The DNA template strand of {g['label']} is {strand_text(g['template'], '3', '5')}. Which mRNA, "
                "written 5′ to 3′, is transcribed from this template strand?"
            ),
            answer=correct,
            explanation=(
                f"Each template base pairs with its complement (A–U, T–A, G–C, C–G), so {g['template']} is "
                f"transcribed into {g['mrna']}."
            ),
            choices=choices,
        )

    def _q_translate_mrna(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["translate"]
        options = protein_options(g)
        correct = sequence_text(g["protein"])
        choices = [
            DraftChoice(
                correct,
                True,
                "Correct: the codons are read in order from the start codon, and each specifies the amino acid shown "
                "in the table.",
            )
        ] + [DraftChoice(sequence_text(options[k]), False, _PROTEIN_WHY[k]) for k in ("reversed", "no_start", "swapped")]
        return DraftQuestion(
            stem=(
                f"The mRNA transcribed from {g['label']} is {strand_text(g['mrna'], '5', '3')}. Translation starts at "
                "the start codon (AUG) and ends at a stop codon. Use the codon table to find the amino acid sequence "
                "this mRNA codes for."
            ),
            answer=correct,
            explanation=(
                f"Reading the codons {', '.join(g['codons'])} with the table gives {correct}; the stop codon "
                f"({g['codons'][-1]}) ends the chain."
            ),
            choices=choices,
        )
```

Remove the now-unused duplicate import line if ruff reports one (the earlier `from app.services.engine.core import GenerationError, Rng` becomes the extended import above).

- [ ] **Step 4: Register the family and flag the standard**

In `registry.py` add `from app.services.families.protein_synthesis import DnaProteinSynthesis` (alphabetical with the others) and `DnaProteinSynthesis(),` as the last entry of the `FAMILIES` tuple.

In `data/standards/SC/2026-2027/biology-1.json`, replace exactly:

```
            "The _______ structures are present in _______ and are related to the function _______."
          ]
        },
        {
          "code": "B-LS1-4",
```

with:

```
            "The _______ structures are present in _______ and are related to the function _______."
          ],
          "question_family_candidate": true
        },
        {
          "code": "B-LS1-4",
```

(The anchor is unique. Do not rewrite the file with a JSON library: that would reformat every line.)

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py tests/test_engine.py -q -k "protein_synthesis or dna-protein or citations or same_seed or hash or items_well_formed"`
Expected: pass for the new family (golden for it will skip until Task 5 pins it; `test_golden_snapshot[dna-protein-synthesis]` raises `KeyError` now: add `"dna-protein-synthesis": None,` to `GOLDEN` in `test_engine.py` as part of this step so the suite stays green; Task 5 pins the real digest). Then `.venv/bin/ruff check app tests && .venv/bin/ruff format app tests`.

- [ ] **Step 6: Commit**

```bash
git add backend data/standards
git commit -m "feat: transcribe and translate items for the DNA to protein family"
```

---

### Task 3: DNA-to-protein and explanation items

**Files:**
- Modify: `backend/app/services/families/protein_synthesis.py`
- Modify: `backend/tests/test_protein_synthesis.py` (append)

**Interfaces:**
- Consumes: Task 2's class, `protein_options`, `sequence_text`, `_PROTEIN_WHY`.
- Produces: templates `dna_to_protein` (DOK 2, `evidence[2]`) and `explain_dna_to_protein` (DOK 3, constructed response, `articulating_explanation[0]`).

- [ ] **Step 1: Write the failing tests**

Append:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q -k "dna_to_protein or explain_item"`
Expected: FAIL (`KeyError`/template not found for the new keys).

- [ ] **Step 3: Implement**

In the class, extend the `templates` tuple:

```python
        TemplateSpec("dna_to_protein", "From a template strand to a protein", 2, "multiple_choice", "evidence", 2),
        TemplateSpec(
            "explain_dna_to_protein",
            "Explain how DNA determines a protein",
            3,
            "constructed_response",
            "articulating_explanation",
            0,
        ),
```

and append the methods:

```python
    def _q_dna_to_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["protein"]
        options = protein_options(g)
        correct = sequence_text(g["protein"])
        choices = [
            DraftChoice(
                correct,
                True,
                "Correct: the template is transcribed into mRNA, and the mRNA codons are translated with the table.",
            )
        ] + [
            DraftChoice(sequence_text(options[k]), False, _PROTEIN_WHY[k])
            for k in ("template_as_mrna", "reversed", "no_start")
        ]
        return DraftQuestion(
            stem=(
                f"The DNA template strand of {g['label']} is {strand_text(g['template'], '3', '5')}. The gene is "
                "transcribed into mRNA, and the mRNA is translated using the codon table shown. Which amino acid "
                "sequence does this gene produce?"
            ),
            answer=correct,
            explanation=(
                f"Transcription gives the mRNA {g['mrna']}. Its codons ({', '.join(g['codons'])}) specify {correct}; "
                "the stop codon ends the chain."
            ),
            choices=choices,
        )

    def _q_explain_dna_to_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["protein"]
        protein = sequence_text(g["protein"])
        return DraftQuestion(
            stem=(
                f"Use the codon table to explain how the DNA template strand of {g['label']}, "
                f"{strand_text(g['template'], '3', '5')}, determines the amino acid sequence of its protein. In your "
                "explanation, write the mRNA that is transcribed (5′ to 3′) and the amino acid sequence that is "
                "produced."
            ),
            answer=(
                f"Transcription copies the template strand into mRNA by base pairing (A–U, T–A, G–C, C–G), so "
                f"{strand_text(g['template'], '3', '5')} is transcribed into {strand_text(g['mrna'], '5', '3')}. The "
                f"mRNA is read in codons ({', '.join(g['codons'])}), and the table shows the amino acid each codon "
                f"specifies: {protein}; the stop codon ends the chain. The order of amino acids is the protein's "
                "sequence, so the order of nucleotides in the gene determines the protein."
            ),
            explanation=(
                "Scoring guide (3 points): (1) the template strand is transcribed into a complementary mRNA by base "
                "pairing; (2) the mRNA is read in groups of three (codons) and each codon specifies an amino acid "
                "according to the table; (3) the order of amino acids is the protein's sequence, so the DNA sequence "
                "determines the protein."
            ),
        )
```

- [ ] **Step 4: Run tests and format**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q && .venv/bin/ruff check app tests && .venv/bin/ruff format app tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: DNA-to-protein and explanation items for the B-LS1-1 family"
```

---

### Task 4: Gene activity by cell type

**Files:**
- Modify: `backend/app/services/families/protein_synthesis.py`
- Modify: `backend/tests/test_protein_synthesis.py` (append)

**Interfaces:**
- Produces: template `gene_activity_by_cell` (DOK 2, `reasoning[3]`); module constants `CATEGORY_TEXT`; stimulus renders the activity table only when this template is selected.

- [ ] **Step 1: Write the failing tests**

Append:

```python
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
```

Note: these tests read `table["rows"]` cells `p` and `q` as the strings `"Active"` and `"Not active"`, so the stimulus rows must hold those strings (the scenario stores booleans).

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q -k activity`
Expected: FAIL (template not found).

- [ ] **Step 3: Implement**

Add near the other module constants:

```python
CATEGORY_TEXT = {
    "p_only": "active in cell type P only",
    "q_only": "active in cell type Q only",
    "both": "active in both cell types",
    "neither": "not active in either cell type",
}


def activity_category(row: dict[str, Any]) -> str:
    return {(True, False): "p_only", (False, True): "q_only", (True, True): "both", (False, False): "neither"}[
        (row["p"], row["q"])
    ]
```

Extend `templates`:

```python
        TemplateSpec(
            "gene_activity_by_cell", "Genes in two cell types", 2, "multiple_choice", "reasoning", 3
        ),
```

In `render_stimulus`, before the `return`, add:

```python
        if "gene_activity_by_cell" in keys:
            intro.append(
                "Cell types P and Q come from the same organism and contain the same DNA. A gene is active in a cell "
                "when the cell uses it to make a protein."
            )
            tables.append(
                {
                    "caption": "Gene activity in two cell types",
                    "columns": [
                        {"key": "gene", "label": "Gene"},
                        {"key": "p", "label": "Cell type P"},
                        {"key": "q", "label": "Cell type Q"},
                    ],
                    "rows": [
                        {
                            "gene": r["gene"],
                            "p": "Active" if r["p"] else "Not active",
                            "q": "Active" if r["q"] else "Not active",
                        }
                        for r in params["activity"]
                    ],
                }
            )
```

Because `intro` is joined after the loop, make sure these `intro.append` calls happen before `" ".join(intro)` (the existing `return` already joins at the end; place the new block above it).

Append the method:

```python
    def _q_gene_activity_by_cell(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        rows = params["activity"]
        actual = {r["gene"]: activity_category(r) for r in rows}
        key_gene = rng.choice([r["gene"] for r in rows])
        choices = []
        for r in rows:
            gene = r["gene"]
            if gene == key_gene:
                text = f"{gene} is {CATEGORY_TEXT[actual[gene]]}."
                choices.append(DraftChoice(text, True, f"Correct: the table shows {gene} is {CATEGORY_TEXT[actual[gene]]}."))
            else:
                wrong = rng.choice([c for c in CATEGORY_TEXT if c != actual[gene]])
                choices.append(
                    DraftChoice(
                        f"{gene} is {CATEGORY_TEXT[wrong]}.",
                        False,
                        f"The table shows {gene} is {CATEGORY_TEXT[actual[gene]]}, not {CATEGORY_TEXT[wrong]}.",
                    )
                )
        correct = next(c.text for c in choices if c.correct)
        return DraftQuestion(
            stem=(
                "The table shows which genes are active in two cell types, P and Q, from the same organism. Which "
                "statement is supported by the table?"
            ),
            answer=correct,
            explanation=(
                "Both cell types contain all four genes because they share the same DNA. They differ in which genes "
                f"are active, so they can make different proteins. {correct}"
            ),
            choices=choices,
        )
```

- [ ] **Step 4: Run tests and format**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q && .venv/bin/ruff check app tests && .venv/bin/ruff format app tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: gene activity by cell type item for the B-LS1-1 family"
```

---

### Task 5: Integration tests, golden digest, docs, and full suite

**Files:**
- Modify: `backend/tests/test_protein_synthesis.py` (append)
- Modify: `backend/tests/test_engine.py` (golden digest)
- Modify: `backend/tests/test_api.py`
- Modify: `HANDOFF.md`, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`, `QUESTION_FAMILY_CATALOG.md`

- [ ] **Step 1: Write the failing family-wide tests**

Append to `test_protein_synthesis.py`:

```python
# ---- family-wide guards --------------------------------------------------------------------

BANNED = ("mutation", "mutate", "frameshift", "silent", "missense", "nonsense", "initiation", "elongation", "termination")
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
            if key != "translate_mrna":
                assert translate_key not in visible, (seed, key)
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
```

- [ ] **Step 2: Run to verify behavior**

Run: `.venv/bin/python -m pytest tests/test_protein_synthesis.py -q`
Expected: the new tests pass if Tasks 1 to 4 are right. If `test_no_item_leaks...` fails, a stem or the base intro shows a key: fix the item text (never weaken the test), and record a ruling.

- [ ] **Step 3: Pin the golden digest**

In `backend/tests/test_engine.py` the entry `"dna-protein-synthesis": None,` (added in Task 2) makes the golden test skip and print the digest. Run `.venv/bin/python -m pytest tests/test_engine.py -q -k "golden and dna-protein" -rs`, copy the printed digest, replace `None` with it, rerun and confirm it passes.

- [ ] **Step 4: API tests (needs a throwaway Postgres)**

Start `docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine` (check `docker ps` first; it may already be running).

In `test_api.py`:

1. Add `("biology-1", "B-LS1-1", "dna-protein-synthesis"),` to the `test_preview_is_reproducible` parametrization.
2. In the EOCEP test that already denies `reaction-outcome` (search for `denied_2`), add after it:

```python
    bio_1_dna = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS1-1")
    denied_3 = client.post(
        "/api/generate/preview",
        json={
            "standard_id": bio_1_dna["id"],
            "family_key": "dna-protein-synthesis",
            "quantity": 1,
            "generation_mode": "eocep",
        },
    )
    assert denied_3.status_code == 422
```

3. In `test_family_must_match_exact_standard`, add before the last two lines:

```python
    _, body = _generate(client, "biology-2", "B-LS1-1", "dna-protein-synthesis")
    assert client.post("/api/generate/preview", json=body).status_code == 422
```

Run: `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest tests/test_api.py -q`
Expected: pass.

- [ ] **Step 5: Docs**

- `HANDOFF.md`: add a row to the "Implemented families" table after `reaction-outcome`:
  `| \`dna-protein-synthesis\` | Biology 1 B-LS1-1 | 1.0.0 | Template strand to mRNA, mRNA to amino acids with a displayed partial codon table, gene activity across two cell types, and a DOK 3 explanation. Classroom-only; no mutation-effect items (B-LS3-2). |` and update "Last updated".
- `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`: change the family count/line ("Six families are live" to "Seven"), add the family to the table, and note in the Tier A B-LS1-1 row that it is built and B-LS3-2 reuses `CODONS`/`translate` from `protein_synthesis.py`.
- `QUESTION_FAMILY_CATALOG.md`: after the B-LS1-1 paragraph (search "single most-repeated PE") add one sentence: "Built as `dna-protein-synthesis` (2026-10-02), Biology 1 only; see the design spec."

- [ ] **Step 6: Full suite and cleanup**

Run: `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q` (about 2.5 minutes; use a background run and wait) and `.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests`.
Expected: zero failures and zero skipped DB tests. Stop the test Postgres container you started.

- [ ] **Step 7: Commit**

```bash
git add -A backend HANDOFF.md QUESTION_FAMILY_CATALOG.md docs/superpowers/plans/2026-09-29-coverage-roadmap.md
git commit -m "test: family-wide guards, golden digest, and docs for the B-LS1-1 family"
```

---

## Self-review

- **Spec coverage:** five templates and citations (Tasks 2 to 4); scenario bounds, k 3 to 5, AUG start, one stop (Task 1); table rules incl. alphabetical, labels, rule sentence, extras, all needed codons (Tasks 1, 2, 3, 5); independent checker (Tasks 2 to 5); distractor safety and coding-strand note (Task 3); direction labels (Tasks 2, 3); scope guard words (Task 5); classroom-only, Biology 1 only, EOCEP denial and Biology 2 mismatch (Task 5); golden digest (Task 5); docs (Task 5); no migration, no frontend.
- **Placeholders:** none.
- **Type consistency:** scenario keys (`genes`, `codon_table`, `activity`) match every consumer; `protein_options` keys (`reversed`, `no_start`, `swapped`, `template_as_mrna`) match `_PROTEIN_WHY`; activity rows hold booleans in the scenario and strings in the stimulus, and the tests read the stimulus; the family is registered by class name `DnaProteinSynthesis`.
