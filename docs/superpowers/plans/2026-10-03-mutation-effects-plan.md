# Mutation Effects (B-LS3-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the deterministic `mutation-effects` question family for Biology 1 B-LS3-2: five templates built from an original and a changed DNA template strand, the standard genetic code, and a displayed partial codon table.

**Architecture:** One new module `families/mutation_effects.py` imports the genetic code and helpers from `protein_synthesis.py` and adds: a single-edit drawing function with position-ambiguity rejection, a translation reader that follows the spec's sequence model, four disjoint effect predicates, role-based scenario drawing (four independent genes plus an inheritance scenario), and the `MutationEffects` class. Templates are added task by task; registry, standards flag, golden digest, API tests, and docs land last.

**Tech Stack:** Python 3.12, the existing question-family engine, pytest. No migration, no frontend change.

**Spec:** `docs/superpowers/specs/2026-10-03-mutation-effects-design.md`

## Global Constraints

- Deterministic: randomness only through `Rng`; no `random`, no Python `hash()`; version `1.0.0`. Any later output change bumps the version and the golden digest in the same commit.
- Sequence model: translation starts at the displayed start codon `AUG` and proceeds in groups of three until the first in-frame Stop; every translation an item needs must meet a Stop within the displayed full codons (no partial-codon ambiguity). Genes are `AUG` + 3 or 4 sense codons + one stop + a 4 to 5 codon tail.
- Exactly one edit (substitution, insertion, or deletion) inside the sense codons; indel edits that could be produced at another position are rejected.
- Effect categories are the four disjoint predicates in the spec; indels are only "several differ" (never an early stop); substitutions are "unchanged", "one changed", or "ends early".
- For any insertion or deletion, every rationale, explanation, and model answer says plainly that the shifted codon grouping is a frameshift; substitution items never use the word.
- Student-facing vocabulary: no silent, missense, nonsense, initiation, elongation, termination, prophase, metaphase, anaphase, telophase. Allowed: mutation, substitution, insertion, deletion, frameshift, mutagen, gamete, somatic cell, inherited, offspring.
- Every MC item has exactly four distinct choices, one key, a rationale for each; constructed response has an empty choice list. All mRNA strings are labelled 5′→3′ and template strands 3′→5′ (prime is U+2032).
- Classroom-only; bound only to `SC / biology-1 / B-LS3-2`; EOCEP mode stays rejected.
- Backend commands run from `backend/`. Format only the files you touched (`.venv/bin/ruff format <files>`); running `ruff format app tests` reformats two unrelated files. `.venv/bin/ruff check app tests` must be clean. Engine tests need no database; `test_api.py` needs `TEST_DATABASE_URL` against a throwaway Postgres (port 54332, container `sb-testdb`, never production).
- Unused imports break `ruff check`: add each import where it is first used.

## Review Focus

- A scenario where more than one effect description is true, or none is (an indel that only lengthens the protein, a substitution that creates a Stop and also differs elsewhere): every effect item has exactly one choice matching an independently computed category (Tasks 1, 3).
- An edit that is ambiguous about position (a deleted base equal to a neighbour, an inserted base equal to an adjacent base) or a changed strand that is not a single edit from the original (Task 1).
- A translation that never meets a Stop or ends in a partial codon, or a codon read by an item that is missing from the displayed table (Tasks 1, 2, 3).
- "Frameshift" missing from an indel item's rationales, or appearing in a substitution item (Task 5).
- One item showing another item's key within the same set, or the inheritance item containing a claim that is actually false for the stated cell kind (Tasks 3, 5).

## File map

| File | Responsibility |
|---|---|
| `backend/app/services/families/mutation_effects.py` (create) | helpers, scenario, `MutationEffects` |
| `backend/tests/test_mutation_effects.py` (create) | independent checks |
| `backend/app/services/families/registry.py` (modify) | register |
| `data/standards/SC/2026-2027/biology-1.json` (modify) | `question_family_candidate: true` on B-LS3-2 |
| `backend/tests/test_engine.py`, `backend/tests/test_api.py` (modify) | golden digest, generation matrix, EOCEP denial, Biology 2 mismatch, with-family list |
| `HANDOFF.md`, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`, `QUESTION_FAMILY_CATALOG.md` (modify) | docs |

---

### Task 1: Edits, reader, predicates, and scenario

**Files:**
- Create: `backend/app/services/families/mutation_effects.py`
- Create: `backend/tests/test_mutation_effects.py`

**Interfaces:**
- Consumes from `app.services.families.protein_synthesis`: `AMINO_ACIDS`, `CODONS`, `GENE_LABELS`, `SENSE_CODONS`, `START`, `STOP_CODONS`, `codons_of`, `table_label`, `template_for`, `transcribe`.
- Produces (importable as `from app.services.families import mutation_effects as me`):
  - Constants `EFFECT_TEXT: dict[str, str]` (keys `unchanged`, `one_changed`, `ends_early`, `several_differ`), `CAUSES: tuple[str, ...]`, `MAX_DRAWS = 400`.
  - `read_protein(mrna: str) -> tuple[list[str] | None, list[str]]` (names or `None` when no in-frame Stop is met in the full codons; and the codons read, including the Stop).
  - `effect_flags(original: list[str], changed: list[str]) -> dict[str, bool]`, `effect_of(original, changed) -> str | None`.
  - `make_edit(rng, template, n_sense, kind) -> dict | None` with keys `type`, `index` (0-based edit index), `position` (declared 1-based; for an insertion, the nucleotide after which the new one goes), `old`, `new`, `changed`.
  - `draw_gene(rng) -> dict` (keys `n_sense`, `mrna`, `template`), `draw_role(rng, label, *, category=None, translate=True, distractors=False) -> dict`, `draw_scenario(rng) -> dict`.
  - Role dict keys: `label`, `n_sense`, `original` (`template`, `mrna`, `protein`), `changed` (`template`, `mrna`, `protein`), `edit` (`type`, `index`, `position`, `old`, `new`), `category` (or `None` when not translated), `codons_read` (sorted list), and `distractors` (`original`, `site_left_out`, `misread`) when requested. For `translate=False` the `protein` fields are `None`.
  - Scenario keys: `roles` (`classify`, `protein`, `effect`, `claim`), `cause`, `inheritance` (`organism`, `cell`, `gamete: bool`, `mutagen`), `codon_table`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_mutation_effects.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `.venv/bin/python -m pytest tests/test_mutation_effects.py -q`
Expected: FAIL at collection (`ImportError: cannot import name 'mutation_effects'`).

- [ ] **Step 3: Write the module**

Create `backend/app/services/families/mutation_effects.py`:

```python
"""Mutation effects (B-LS3-2): a one-nucleotide change in a gene and what it does to the protein.

Curated data only: the standard genetic code (shared with protein_synthesis). Every key is computed from the original
and changed template strands and the codon table the student sees. Translation always starts at the displayed AUG and
continues in groups of three to the first in-frame Stop; a draw is rejected when any translation an item needs never
meets a Stop, so no item depends on a partial codon. Scope follows the Biology 1 boundary: no meiosis phases, no
biochemical mechanisms, no named genes or proteins, and no naming of silent, missense, or nonsense changes.
"""

from typing import Any

from app.services.engine.core import GenerationError, Rng
from app.services.families.protein_synthesis import (
    AMINO_ACIDS,
    CODONS,
    GENE_LABELS,
    SENSE_CODONS,
    START,
    STOP_CODONS,
    codons_of,
    table_label,
    template_for,
    transcribe,
)

MAX_DRAWS = 400
ALL_CODONS = tuple(sorted(CODONS))
EDIT_KINDS = ("substitution", "insertion", "deletion")
CATEGORY_KINDS = {
    "unchanged": ("substitution",),
    "one_changed": ("substitution",),
    "ends_early": ("substitution",),
    "several_differ": ("insertion", "deletion"),
}
EFFECT_TEXT = {
    "unchanged": "The protein is unchanged.",
    "one_changed": "Exactly one amino acid is different.",
    "ends_early": "The protein ends early, because a new stop codon is read.",
    "several_differ": "Several amino acids after the change are different.",
}
CAUSES = (
    "a copying error during DNA replication",
    "exposure to ultraviolet light, a mutagen",
    "exposure to X-rays, a mutagen",
)
ORGANISMS = ("a mouse", "a fruit fly", "a zebrafish")
CELLS = ("a body cell (somatic cell)", "an egg cell", "a sperm cell")
MUTAGENS = ("ultraviolet light", "X-rays")


# ---- reading and classifying ---------------------------------------------------------------


def read_protein(mrna: str) -> tuple[list[str] | None, list[str]]:
    """Amino acid names from the start codon to the first in-frame Stop, and the codons read (Stop included).

    Returns `None` for the names when no Stop is met within the full codons shown (a partial last codon is ignored).
    """
    names: list[str] = []
    used: list[str] = []
    for codon in codons_of(mrna[: len(mrna) - len(mrna) % 3]):
        used.append(codon)
        if CODONS[codon] == "*":
            return names, used
        names.append(AMINO_ACIDS[CODONS[codon]])
    return None, used


def effect_flags(original: list[str], changed: list[str]) -> dict[str, bool]:
    """Four predicates over the original and changed proteins. They are pairwise disjoint."""
    differing = sum(a != b for a, b in zip(original, changed))
    return {
        "unchanged": changed == original,
        "one_changed": len(changed) == len(original) and differing == 1,
        "ends_early": len(changed) < len(original) and changed == original[: len(changed)],
        "several_differ": len(changed) >= len(original) and differing >= 2,
    }


def effect_of(original: list[str], changed: list[str]) -> str | None:
    """The one true category, or None when no description is true (such a draw is rejected)."""
    true = [name for name, value in effect_flags(original, changed).items() if value]
    return true[0] if len(true) == 1 else None


def _all_distinct(options: list[list[str]]) -> bool:
    return len({tuple(o) for o in options}) == len(options)


# ---- edits and genes -----------------------------------------------------------------------


def make_edit(rng: Rng, template: str, n_sense: int, kind: str) -> dict[str, Any] | None:
    """One edit inside the sense codons, or None when an indel's position would be ambiguous."""
    index = rng.randint(3, 3 * (n_sense + 1) - 1)
    if kind == "substitution":
        new = rng.choice([b for b in "ACGT" if b != template[index]])
        changed = template[:index] + new + template[index + 1 :]
        return {"type": kind, "index": index, "position": index + 1, "old": template[index], "new": new, "changed": changed}
    if kind == "deletion":
        if template[index] in (template[index - 1], template[index + 1]):
            return None
        changed = template[:index] + template[index + 1 :]
        return {"type": kind, "index": index, "position": index + 1, "old": template[index], "new": None, "changed": changed}
    new = rng.choice("ACGT")
    if new in (template[index - 1], template[index]):
        return None
    changed = template[:index] + new + template[index:]
    return {"type": kind, "index": index, "position": index, "old": None, "new": new, "changed": changed}


def draw_gene(rng: Rng) -> dict[str, Any]:
    n_sense = rng.randint(3, 4)
    sense = [rng.choice(SENSE_CODONS) for _ in range(n_sense)]
    coding = [START, *sense, rng.choice(STOP_CODONS)]
    tail = [rng.choice(ALL_CODONS) for _ in range(rng.randint(4, 5))]
    mrna = "".join(coding + tail)
    return {"n_sense": n_sense, "mrna": mrna, "template": template_for(mrna)}


def draw_role(
    rng: Rng, label: str, *, category: str | None = None, translate: bool = True, distractors: bool = False
) -> dict[str, Any]:
    kinds = CATEGORY_KINDS[category] if category else EDIT_KINDS
    for _ in range(MAX_DRAWS):
        gene = draw_gene(rng)
        edit = make_edit(rng, gene["template"], gene["n_sense"], rng.choice(kinds))
        if edit is None:
            continue
        changed_template = edit.pop("changed")
        role: dict[str, Any] = {
            "label": label,
            "n_sense": gene["n_sense"],
            "original": {"template": gene["template"], "mrna": gene["mrna"], "protein": None},
            "changed": {"template": changed_template, "mrna": transcribe(changed_template), "protein": None},
            "edit": edit,
            "category": None,
            "codons_read": [],
        }
        if not translate:
            return role
        original, read_original = read_protein(role["original"]["mrna"])
        changed, read_changed = read_protein(role["changed"]["mrna"])
        if original is None or changed is None:
            continue
        found = effect_of(original, changed)
        if found is None or (found == "several_differ") != (edit["type"] != "substitution"):
            continue
        if category is not None and found != category:
            continue
        used = set(read_original) | set(read_changed)
        if distractors:
            misread, read_misread = read_protein(changed_template.replace("T", "U"))
            if misread is None:
                continue
            site = edit["index"] // 3
            options = {"original": original, "site_left_out": original[:site] + original[site + 1 :], "misread": misread}
            if not _all_distinct([changed, *options.values()]):
                continue
            role["distractors"] = options
            used |= set(read_misread)
        role["original"]["protein"], role["changed"]["protein"] = original, changed
        role["category"] = found
        role["codons_read"] = sorted(used)
        return role
    raise GenerationError(f"mutation-effects: no valid {label} scenario after {MAX_DRAWS} draws")


def draw_scenario(rng: Rng) -> dict[str, Any]:
    labels = rng.sample(list(GENE_LABELS), 4)
    roles = {
        "classify": draw_role(rng, labels[0], translate=False),
        "protein": draw_role(rng, labels[1], distractors=True),
        "effect": draw_role(rng, labels[2], category=rng.choice(list(EFFECT_TEXT))),
        "claim": draw_role(rng, labels[3]),
    }
    needed: set[str] = set()
    for name in ("protein", "effect", "claim"):
        needed |= set(roles[name]["codons_read"])
    extras = rng.sample(sorted(set(SENSE_CODONS) - needed), rng.randint(2, 3))
    cell = rng.choice(CELLS)
    return {
        "roles": roles,
        "cause": rng.choice(CAUSES),
        "inheritance": {
            "organism": rng.choice(ORGANISMS),
            "cell": cell,
            "gamete": cell != CELLS[0],
            "mutagen": rng.choice(MUTAGENS),
        },
        "codon_table": [{"codon": c, "amino_acid": table_label(c)} for c in sorted(needed | set(extras))],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q && .venv/bin/ruff format app/services/families/mutation_effects.py tests/test_mutation_effects.py && .venv/bin/ruff check app tests`
Expected: all pass, ruff clean. If `test_translated_roles_are_determinate...` fails on the `seen` assertion, report the missing category in a ledger ruling (it means the effect role never produced it in 200 seeds) and fix the drawing rather than weakening the test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/families/mutation_effects.py backend/tests/test_mutation_effects.py
git commit -m "feat: edits, reader, effect predicates, and scenario for the B-LS3-2 family"
```

---

### Task 2: Family class with identify and new-protein items; registry; standards flag

**Files:**
- Modify: `backend/app/services/families/mutation_effects.py` (append the class)
- Modify: `backend/app/services/families/registry.py`
- Modify: `data/standards/SC/2026-2027/biology-1.json`
- Modify: `backend/tests/test_engine.py` (golden placeholder)
- Modify: `backend/tests/test_mutation_effects.py` (append)

**Interfaces:**
- Consumes: Task 1 outputs; `Binding`, `DraftChoice`, `DraftQuestion`, `TemplateSpec` from `app.services.engine.core`; `QuestionFamily` from `app.services.engine.family`; `sequence_text`, `strand_text` from `protein_synthesis`.
- Produces: `MutationEffects` (key `mutation-effects`, version `1.0.0`, `stimulus_kind = "mutation_effects"`) with templates `identify_mutation_type` and `new_protein_after_change`; helpers `_frameshift(text, edit)`, `_edit_sentence(edit)`, `_strands_sentence(role)`; constants `SEQUENCE_MODEL`, `FRAMESHIFT_NOTE`, `_TABLE_KEYS`.

- [ ] **Step 1: Write the failing tests**

Append to `test_mutation_effects.py` (add `import re` and `from app.services.engine.family import generate_set` to the imports at the top, and `from tests.test_protein_synthesis import STRAND, _triples` is not needed):

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q`
Expected: the new tests FAIL (`AttributeError: ... MutationEffects`).

- [ ] **Step 3: Append the class**

Extend the imports in `mutation_effects.py`:

```python
from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily
```

(replacing the earlier `from app.services.engine.core import GenerationError, Rng`), and add `sequence_text` and `strand_text` to the `protein_synthesis` import list. Append:

```python
# ---- family --------------------------------------------------------------------------------

SEQUENCE_MODEL = "Translation starts at the start codon (AUG) and continues in groups of three nucleotides until the first stop codon."
FRAMESHIFT_NOTE = (
    "Adding or removing one nucleotide shifts the way the codons are grouped. This is a frameshift: the codons after "
    "the change are read in a different grouping, so the amino acids after the change are different."
)
_BASE_INTRO = (
    "A mutation is a change in the DNA sequence of a gene. The gene's template strand is transcribed into mRNA, and the "
    "mRNA codons specify the amino acids of a protein."
)
_TABLE_RULE = "Use the codon table shown. You do not need to memorize codons."
_TABLE_KEYS = {"new_protein_after_change", "effect_on_protein", "defend_claim_about_change"}


def _is_indel(edit: dict[str, Any]) -> bool:
    return edit["type"] != "substitution"


def _frameshift(text: str, edit: dict[str, Any]) -> str:
    return f"{text} {FRAMESHIFT_NOTE}" if _is_indel(edit) else text


def _edit_sentence(edit: dict[str, Any]) -> str:
    if edit["type"] == "substitution":
        return f"nucleotide {edit['position']} was changed from {edit['old']} to {edit['new']}"
    if edit["type"] == "deletion":
        return f"nucleotide {edit['position']} ({edit['old']}) was removed"
    return f"the nucleotide {edit['new']} was added between nucleotide {edit['position']} and nucleotide {edit['position'] + 1}"


def _strands_sentence(role: dict[str, Any]) -> str:
    return (
        f"Original template strand: {strand_text(role['original']['template'], '3', '5')}. "
        f"Changed template strand: {strand_text(role['changed']['template'], '3', '5')}."
    )


class MutationEffects(QuestionFamily):
    key = "mutation-effects"
    version = "1.0.0"
    title = "Mutations: effects on a protein"
    description = (
        "Compare an original and a changed DNA template strand: identify the substitution, insertion, or deletion, find "
        "the protein made from the changed gene with a displayed codon table, describe its effect, decide whether a "
        "mutation can be inherited, and defend a claim about what the change did."
    )
    stimulus_kind = "mutation_effects"
    bindings = (Binding("SC", "biology-1", "B-LS3-2"),)
    templates = (
        TemplateSpec("identify_mutation_type", "Identify the kind of mutation", 1, "multiple_choice", "evidence", 1),
        TemplateSpec(
            "new_protein_after_change", "Protein made from the changed gene", 2, "multiple_choice", "reasoning", 0
        ),
    )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        keys = set(template_keys)
        intro = [_BASE_INTRO]
        tables = []
        if keys & _TABLE_KEYS:
            intro += [SEQUENCE_MODEL, _TABLE_RULE]
            tables.append(
                {
                    "caption": "Codon table (mRNA codons, read 5′ to 3′)",
                    "columns": [{"key": "codon", "label": "mRNA codon"}, {"key": "amino_acid", "label": "Amino acid"}],
                    "rows": params["codon_table"],
                }
            )
        return {
            "title": "Mutations and proteins",
            "intro": " ".join(intro),
            "sections": [],
            "tables": tables,
            "charts": [],
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_identify_mutation_type(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["classify"]
        edit = role["edit"]
        texts = {
            "substitution": "A substitution: one nucleotide was replaced by another.",
            "insertion": "An insertion: one nucleotide was added.",
            "deletion": "A deletion: one nucleotide was removed.",
        }
        why_not = {
            ("substitution", "insertion"): "The strands have the same number of nucleotides, so none was added.",
            ("substitution", "deletion"): "The strands have the same number of nucleotides, so none was removed.",
            ("insertion", "substitution"): "The strands are different lengths, so a nucleotide was added, not just replaced.",
            ("insertion", "deletion"): "The changed strand is longer, so a nucleotide was added, not removed.",
            ("deletion", "substitution"): "The strands are different lengths, so a nucleotide was removed, not just replaced.",
            ("deletion", "insertion"): "The changed strand is shorter, so a nucleotide was removed, not added.",
        }
        choices = []
        for kind, text in texts.items():
            if kind == edit["type"]:
                why = f"Correct: comparing the strands, {_edit_sentence(edit)}."
            else:
                why = why_not[(edit["type"], kind)]
            choices.append(DraftChoice(text, kind == edit["type"], _frameshift(why, edit)))
        choices.append(
            DraftChoice(
                "No mutation occurred, because the protein is not changed.",
                False,
                _frameshift(
                    "The DNA sequence changed, so a mutation occurred. A mutation is a change in the DNA sequence, "
                    "whether or not the protein changes.",
                    edit,
                ),
            )
        )
        correct = texts[edit["type"]]
        return DraftQuestion(
            stem=(
                f"The DNA of a cell was changed by {params['cause']}. The template strands of {role['label']} before "
                f"and after the change are shown. {_strands_sentence(role)} Which statement describes the change?"
            ),
            answer=correct,
            explanation=_frameshift(f"Comparing the strands, {_edit_sentence(edit)}, so this is a {edit['type']}.", edit),
            choices=choices,
        )

    def _q_new_protein_after_change(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["protein"]
        edit = role["edit"]
        original, changed = role["original"]["protein"], role["changed"]["protein"]
        options = role["distractors"]
        correct = sequence_text(changed)
        why = {
            "original": "This is the protein made from the original strand. The changed strand is read codon by codon, and it makes a different protein.",
            "site_left_out": "This leaves out the amino acid at the change instead of reading the changed strand codon by codon.",
            "misread": "This reads the DNA template strand directly as if it were mRNA. The template must first be transcribed into its complementary mRNA.",
        }
        choices = [
            DraftChoice(
                correct,
                True,
                _frameshift(
                    "Correct: the changed strand is transcribed into mRNA, and the mRNA is read from the start codon to "
                    "the first stop codon using the table.",
                    edit,
                ),
            )
        ] + [DraftChoice(sequence_text(options[k]), False, _frameshift(why[k], edit)) for k in ("original", "site_left_out", "misread")]
        return DraftQuestion(
            stem=(
                f"A mutation changed the DNA template strand of {role['label']}. {_strands_sentence(role)} "
                f"{SEQUENCE_MODEL} Use the codon table to find the amino acid sequence made from the changed gene."
            ),
            answer=correct,
            explanation=_frameshift(
                f"The original protein is {sequence_text(original)}. The changed strand is transcribed into "
                f"{role['changed']['mrna']} and read to the first stop codon, which gives {correct}.",
                edit,
            ),
            choices=choices,
        )
```

`_edit_sentence` and `_strands_sentence` are used by these two methods, and `ruff` is clean after `ruff format`.

- [ ] **Step 4: Register the family, flag the standard, add the golden placeholder**

In `registry.py` add `from app.services.families.mutation_effects import MutationEffects` (alphabetical with the others) and `MutationEffects(),` as the last entry of the `FAMILIES` tuple.

In `data/standards/SC/2026-2027/biology-1.json`, replace exactly:

```
"substitution", "trait", "trisomy"]
        },
        {
          "code": "B-LS3-3",
```

with:

```
"substitution", "trait", "trisomy"],
          "question_family_candidate": true
        },
        {
          "code": "B-LS3-3",
```

(Check that the anchor is unique before replacing; do not rewrite the file with a JSON library.)

In `backend/tests/test_engine.py`, add `"mutation-effects": None,` after the `"dna-protein-synthesis"` entry in `GOLDEN`.

- [ ] **Step 5: Run the tests and format**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py tests/test_engine.py -q -k "mutation or citations or same_seed or hash or items_well_formed" ; .venv/bin/ruff format app/services/families/mutation_effects.py app/services/families/registry.py tests/test_mutation_effects.py tests/test_engine.py ; .venv/bin/ruff check app tests`
Expected: pass (the golden test for the new family skips until Task 5). If `test_items_well_formed_across_seeds[mutation-effects]` fails now because only two of five templates exist, confirm the failure is only the `sorted(keys) == sorted(t.key for t in fam.templates)` style checks and not an item defect; it uses the family's own template list so it should pass.

- [ ] **Step 6: Commit**

```bash
git add backend data
git commit -m "feat: identify and new-protein items for the mutation effects family"
```

---

### Task 3: Effect on protein and inheritance items

**Files:**
- Modify: `backend/app/services/families/mutation_effects.py`
- Modify: `backend/tests/test_mutation_effects.py` (append)

**Interfaces:**
- Consumes: Task 2's class and helpers; `EFFECT_TEXT`.
- Produces: templates `effect_on_protein` (DOK 2, `reasoning[0]`) and `inheritance_of_mutation` (DOK 2, `reasoning[1]`); `_TABLE_KEYS` already contains `effect_on_protein`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
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
BODY_KEY = (
    "The mutation will not be passed to offspring, but cells that come from the changed body cell will carry it."
)


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q -k "effect_item or indel_effect or inheritance"`
Expected: FAIL (template not found).

- [ ] **Step 3: Implement**

Extend `templates` in the class:

```python
        TemplateSpec("effect_on_protein", "Effect of a mutation on a protein", 2, "multiple_choice", "reasoning", 0),
        TemplateSpec("inheritance_of_mutation", "Can a mutation be inherited?", 2, "multiple_choice", "reasoning", 1),
```

Append the methods:

```python
    def _q_effect_on_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["effect"]
        edit, category = role["edit"], role["category"]
        original, changed = role["original"]["protein"], role["changed"]["protein"]
        before, after = sequence_text(original), sequence_text(changed)
        right = {
            "unchanged": f"Correct: both strands give {before}. The changed codon still specifies the same amino acid.",
            "one_changed": f"Correct: the original protein is {before} and the changed protein is {after}. Only one amino acid differs.",
            "ends_early": (
                f"Correct: the changed protein is {after}. A new stop codon is read, so the protein ends after "
                f"{len(changed)} amino acids instead of {len(original)}."
            ),
            "several_differ": (
                f"Correct: the original protein is {before} and the changed protein is {after}. Several amino acids "
                "after the change are different."
            ),
        }
        choices = []
        for name, text in EFFECT_TEXT.items():
            if name == category:
                why = right[name]
            else:
                why = (
                    f"Not supported: the original protein is {before} and the changed protein is {after}, which does "
                    "not match this statement."
                )
            choices.append(DraftChoice(text, name == category, _frameshift(why, edit)))
        return DraftQuestion(
            stem=(
                f"A mutation changed the DNA template strand of {role['label']}. {_strands_sentence(role)} "
                f"{SEQUENCE_MODEL} Use the codon table to compare the original and changed proteins. Which statement "
                "describes how the change affects the protein?"
            ),
            answer=EFFECT_TEXT[category],
            explanation=_frameshift(
                f"The original protein is {before}. The changed protein is {after}. {EFFECT_TEXT[category]}", edit
            ),
            choices=choices,
        )

    def _q_inheritance_of_mutation(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        info = params["inheritance"]
        organism, cell, mutagen = info["organism"], info["cell"], info["mutagen"]
        if info["gamete"]:
            word = cell.split(" ", 1)[1]
            correct = f"The mutation can be inherited by offspring if the changed {word} takes part in fertilization."
            right = (
                "Correct: a mutation in a gamete is in the genetic material that offspring receive when that gamete "
                "takes part in fertilization."
            )
            opposite = "The mutation will not be passed to offspring, because only body cells can carry mutations."
            opposite_why = "Gametes carry genetic material to offspring, so a mutation in a gamete can be inherited."
        else:
            correct = "The mutation will not be passed to offspring, but cells that come from the changed body cell will carry it."
            right = (
                "Correct: a mutation in a body cell stays in the cells that come from it. It is not in the gametes, so "
                "offspring do not receive it."
            )
            opposite = "The mutation will be passed to all offspring, because every mutation is inherited."
            opposite_why = "Only mutations in gametes can be passed to offspring. A body cell mutation is not in the gametes."
        choices = [
            DraftChoice(correct, True, right),
            DraftChoice(opposite, False, opposite_why),
            DraftChoice(
                f"The mutation will appear in every cell of {organism} and in all of its offspring.",
                False,
                "A mutation starts in one cell and is only in the cells that come from it, so it is not in every cell.",
            ),
            DraftChoice(
                f"{mutagen[0].upper()}{mutagen[1:]} cannot cause a mutation; only copying errors during replication change DNA.",
                False,
                "A mutagen, such as ultraviolet light or X-rays, is an environmental factor that can change DNA.",
            ),
        ]
        return DraftQuestion(
            stem=(
                f"{organism[0].upper()}{organism[1:]} is exposed to {mutagen}, a mutagen. The exposure causes a "
                f"mutation in the DNA of {cell}. Which statement is supported?"
            ),
            answer=correct,
            explanation=right,
            choices=choices,
        )
```

- [ ] **Step 4: Run tests and format**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q && .venv/bin/ruff format app/services/families/mutation_effects.py tests/test_mutation_effects.py && .venv/bin/ruff check app tests`
Expected: all pass. The inheritance test checks `"body cell" in stem` to separate cell kinds: the stem contains the cell phrase, and "a body cell (somatic cell)" contains "body cell".

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: effect and inheritance items for the mutation effects family"
```

---

### Task 4: Defend a claim about the change

**Files:**
- Modify: `backend/app/services/families/mutation_effects.py`
- Modify: `backend/tests/test_mutation_effects.py` (append)

**Interfaces:**
- Produces: template `defend_claim_about_change` (DOK 3, constructed response, `reasoning[2]`); `_TABLE_KEYS` already contains it.

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q -k claim`
Expected: FAIL (template not found).

- [ ] **Step 3: Implement**

Extend `templates`:

```python
        TemplateSpec(
            "defend_claim_about_change",
            "Make and defend a claim about a mutation",
            3,
            "constructed_response",
            "reasoning",
            2,
        ),
```

Append the method:

```python
    def _q_defend_claim_about_change(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["claim"]
        edit, category = role["edit"], role["category"]
        original, changed = role["original"]["protein"], role["changed"]["protein"]
        effect = {
            "unchanged": "does not change the protein",
            "one_changed": "changes one amino acid in the protein",
            "ends_early": "makes the protein end early",
            "several_differ": "changes several amino acids after the change",
        }[category]
        counterclaim = (
            "Every change in the DNA sequence changes the protein."
            if category == "unchanged"
            else "A change of one nucleotide cannot change the protein."
        )
        rebuttal = (
            "The counterclaim is wrong: although the DNA sequence changed, the changed codon still specifies the same "
            "amino acid in the table, so this change did not alter the protein."
            if category == "unchanged"
            else "The counterclaim is wrong: the evidence shows that changing one nucleotide produced a different protein."
        )
        answer = (
            f"Claim: this {edit['type']} ({_edit_sentence(edit)}) {effect}. "
            f"Evidence: the original template strand {strand_text(role['original']['template'], '3', '5')} is "
            f"transcribed into the mRNA {strand_text(role['original']['mrna'], '5', '3')}, which the table translates as "
            f"{sequence_text(original)}. The changed template strand {strand_text(role['changed']['template'], '3', '5')} "
            f"is transcribed into {strand_text(role['changed']['mrna'], '5', '3')}, which the table translates as "
            f"{sequence_text(changed)}. "
            "Reasoning: a change in the DNA sequence changes the mRNA codons, and the codons set the amino acid sequence, "
            "so a mutation can produce a protein that differs between cells or organisms. "
            f"{rebuttal}"
        )
        return DraftQuestion(
            stem=(
                f"A mutation changed the DNA template strand of {role['label']}. {_strands_sentence(role)} "
                f"{SEQUENCE_MODEL} Make a claim about what the change did to the protein, and defend it with evidence "
                "from the displayed strands and codon table, and the derived amino acid sequences. A classmate says: "
                f"\"{counterclaim}\" Explain how your evidence answers this counterclaim."
            ),
            answer=_frameshift(answer, edit),
            explanation=_frameshift(
                "Scoring guide (4 points): (1) a claim that names the type of change and its effect on the protein; "
                "(2) evidence from the displayed strands and codon table, and the derived amino acid sequences; "
                "(3) reasoning that the changed DNA changes the mRNA codons, which can change the amino acids and so "
                "produce genetic variation; (4) an answer to the counterclaim that uses the evidence.",
                edit,
            ),
        )
```

- [ ] **Step 4: Run tests and format**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q && .venv/bin/ruff format app/services/families/mutation_effects.py tests/test_mutation_effects.py && .venv/bin/ruff check app tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: defend-a-claim item for the mutation effects family"
```

---

### Task 5: Family-wide guards, golden digest, API tests, docs, full suite

**Files:**
- Modify: `backend/tests/test_mutation_effects.py`, `backend/tests/test_engine.py`, `backend/tests/test_api.py`
- Modify: `HANDOFF.md`, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`, `QUESTION_FAMILY_CATALOG.md`

- [ ] **Step 1: Write the family-wide guard tests**

Append to `test_mutation_effects.py`:

```python
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
        strand_items = ("identify_mutation_type", "new_protein_after_change", "effect_on_protein", "defend_claim_about_change")
        originals = [_strands(qs[k])[0] for k in strand_items]
        assert len(set(originals)) == 4


def test_a_full_set_has_one_codon_table_within_bounds_and_single_template_sets_only_what_they_need():
    for seed in SEEDS:
        tables = _full(seed)["groups"][0]["stimulus"]["tables"]
        assert len(tables) == 1 and 12 <= len(tables[0]["rows"]) <= 36
    assert _set("one", "identify_mutation_type")["groups"][0]["stimulus"]["tables"] == []
    assert _set("one", "inheritance_of_mutation")["groups"][0]["stimulus"]["tables"] == []
```

- [ ] **Step 2: Run to verify behavior, then prove the guards bite**

Run: `.venv/bin/python -m pytest tests/test_mutation_effects.py -q`
Expected: pass. Because these guards pass on first run, prove they can fail: (a) temporarily append the word `silent` to `_BASE_INTRO` and confirm `test_vocabulary_guard` fails; (b) temporarily make `_frameshift` return `text` unchanged and confirm `test_frameshift_is_taught...` fails; (c) temporarily set `MAX_DRAWS` irrelevant mutation: change `read_protein` to return `names` instead of `None` at the end and confirm `test_translated_roles_are_determinate...` or `test_read_protein_follows_the_sequence_model` fails. Restore each change (`git checkout backend/app/services/families/mutation_effects.py` after committing nothing in between) and record the three outcomes in the ledger.

- [ ] **Step 3: Pin the golden digest**

Run `.venv/bin/python -m pytest tests/test_engine.py -q -k "golden and mutation" -rs`, copy the printed digest, replace `None` in `"mutation-effects": None,` with it (as a quoted string), and rerun until it passes.

- [ ] **Step 4: API tests (throwaway Postgres)**

Start `docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine` (check `docker ps` first). In `test_api.py`:

1. Add `("biology-1", "B-LS3-2", "mutation-effects"),` to the `test_preview_is_reproducible` parametrization.
2. After the `denied_3` block in the EOCEP test, add:

```python
    bio_1_mut = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS3-2")
    denied_4 = client.post(
        "/api/generate/preview",
        json={
            "standard_id": bio_1_mut["id"],
            "family_key": "mutation-effects",
            "quantity": 1,
            "generation_mode": "eocep",
        },
    )
    assert denied_4.status_code == 422
```

3. In `test_family_must_match_exact_standard`, add before the `doks=[4]` lines:

```python
    _, body = _generate(client, "biology-2", "B-LS3-2", "mutation-effects")
    assert client.post("/api/generate/preview", json=body).status_code == 422
```

4. In `test_standards_browse_and_detail`, insert `("biology-1", "B-LS3-2"),` between `("biology-1", "B-LS2-1"),` and `("biology-1", "B-LS3-3"),` in the expected `with_family` list.

Run: `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest tests/test_api.py tests/test_coverage_api.py -q`
Expected: pass.

- [ ] **Step 5: Docs**

- `HANDOFF.md`: add a row to the "Implemented families" table after `dna-protein-synthesis`: `| \`mutation-effects\` | Biology 1 B-LS3-2 | 1.0.0 (built on branch \`feat/mutation-effects\`, not yet merged or deployed) | One-nucleotide substitution, insertion, or deletion in a gene: identify it, find the protein from the changed gene with a displayed codon table, describe the effect (frameshift taught explicitly for indels), decide whether it can be inherited, and defend a claim. Classroom-only; meiosis and mutagen-dataset items are a later B-LS3-2 family. |` and update "Last updated".
- `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`: "Seven families are live" becomes "Eight"; add `| \`mutation-effects\` | Biology 1 B-LS3-2 (built 2026-10-03; sequence-level mutation effects only; meiosis and mutagen data items still to do) |` to the table; "That is 6 standards with a family" becomes 7; in the Tier A B-LS3-2 row append "**First family built** as `mutation-effects`; meiosis and mutagen/replication-error dataset items remain."
- `QUESTION_FAMILY_CATALOG.md`: no change unless it names B-LS3-2 as unbuilt (search for it; if so, append one sentence pointing to the spec).

- [ ] **Step 6: Full suite and cleanup**

Run (background, about 2.5 minutes): `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q` and `.venv/bin/ruff check app tests`.
Expected: zero failures, zero skipped. Stop the test Postgres container you started.

- [ ] **Step 7: Commit**

```bash
git add -A backend HANDOFF.md QUESTION_FAMILY_CATALOG.md docs/superpowers/plans/2026-09-29-coverage-roadmap.md
git commit -m "test: family-wide guards, golden digest, and docs for the B-LS3-2 family"
```

---

## Self-review

- **Spec coverage:** sequence model and determinacy (Tasks 1, 2, 3, 5); gene shape, edit invariant, position unambiguity, sense-codon-only edits (Task 1); four disjoint predicates and the indel-only rule (Task 1, 3); five templates with citations (Tasks 2 to 4); explicit frameshift teaching (Tasks 2 to 5); evidence wording in the claim item and rubric (Task 4); table rules and bound (Tasks 1, 5); vocabulary guard, leak test, mutation checks, golden, EOCEP and Biology 2 rejection, docs (Task 5); no migration or frontend.
- **Placeholders:** none.
- **Type consistency:** role keys (`original`, `changed`, `edit`, `category`, `codons_read`, `distractors`) match their consumers; the scenario key `cause` and `inheritance` are read by the identify and inheritance items; `EFFECT_TEXT` keys equal the predicate names and `CATEGORY_KINDS` keys; the family class name `MutationEffects` is the registered name.
