# EOCEP Constraints for the New Biology 1 Families Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn on EOCEP Practice for `dna-protein-synthesis` (B-LS1-1), `mutation-effects` (B-LS3-2) and `natural-selection-trend` (B-LS4-4) by importing the EOCEP Biology 1 item-writer constraints, rendering B-LS1-1 items without 3′/5′ notation in EOCEP mode, and proving by scan tests that no EOCEP item uses a term the source forbids.

**Architecture:** The three standards' constraints go into `biology-1-eocep.json`; the existing importer stores them and the existing generation guard already allows EOCEP once constraints exist. A new `eocep` argument to `generate_set` is passed to a family only if the family sets `eocep_aware = True`; only `dna-protein-synthesis` does, and it then prints strands without ends. Every other family's output is byte-identical in both modes. A new `eocep_scope_note` on `StandardSummary` (and in saved `options`) carries the B-LS3-2 "mutation part only" note to the Generate page.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest on Postgres; React 19, TanStack Query, openapi-typescript.

**Spec:** `docs/superpowers/specs/2026-10-03-eocep-new-biology-families-design.md` (amended 2026-10-04; commits `3c34b7e`, `00fd1dc`, `56e223e`). Read it first. This plan replaces the earlier plan of the same name, which implemented the superseded "exclude three B-LS1-1 templates" design.

## Global Constraints

- Brandon approves each spec, plan, merge, deploy and push himself. This plan stops after the branch is built, tested and reviewed. **Do not merge, deploy or push.**
- The official PDF is the only source: `SCDoE Targets/State Assessment Specifications_EOCEP Biology 1_2025-2026.pdf`; printed pages 3–4 (B-LS1-1), 15 (B-LS3-2), 19 (B-LS4-4). The PDF file page is the printed page plus 2.
- Enforcement is by test only (no runtime content check, no vocabulary allowlist). The `allowed_terminology` lists are reference data: the source heads them "Terminology That Could Be Used", so unlisted plain-language words are not violations. No item is reworded to match them.
- B-LS3-2 is offered in EOCEP mode with the scope note "Covers the mutation part of this standard only; meiosis items are not yet available."
- `dna-protein-synthesis` stays at version **1.0.0**. The version feeds every sub-seed, so a bump would change every Classroom item. The golden digest in `tests/test_engine.py` does not change and must keep passing.
- Classroom output is byte-identical for every family and seed. Families other than `dna-protein-synthesis` are byte-identical in both modes.
- No LLM-authored questions; keys are computed from what the student sees; tests recompute keys from typed ground truth.
- EOCEP stays Biology 1 only and selected-response only. Biology 2 and standards without constraints are still rejected with 422.
- Run `ruff format` only on files you touched. Keep `ruff check app tests` clean. Full backend suite: zero failures, zero skips (400 tests before this work, 427 after).
- Test against the throwaway Postgres on port 54332 (container `sb-testdb`); never touch production data or containers. Stop the container when done.
- Wording is product: no mastery or verdict language; "practice", never "equivalent to the state test".

## Review Focus

Failure modes the spec implies but a task's happy-path tests could miss, most likely first:

1. **A banned term hides outside the scanned text** (a table cell, caption, rationale, chart or section). Mitigation: the scan serialises the whole group except `parameters`, and Task 2 proves it with a positive control (Classroom DNA output must trip it) and planted-word mutations in all three families.
2. **No-ends items become ambiguous or cue the key.** With no 3′/5′, the "reversed" distractors rest on "read left to right". Task 2 pins that every EOCEP transcribe key equals the pairing of the strand actually shown and appears exactly once, and that the reversed-protein rationale says "first codon, at the left end". A teacher should still read a few EOCEP B-LS1-1 items.
3. **EOCEP item needs a codon the table does not show.** EOCEP students are not expected to recall codons. Task 2 recomputes the needed codons from the displayed strand and checks each is in the displayed table.
4. **Classroom output changes.** The golden digest test, the identical-digest tests (flag named or not, other families both modes) and the same-scenario test cover it.
5. **The scope note is missing where it matters** (saved provenance, Generate page, non-B-LS3-2 standards). Task 3 pins the standard summary, the preview, the saved `options`, and that no other standard has a note; Task 4 shows it only when EOCEP is selected.

---

## File map

| File | Responsibility |
|---|---|
| `data/standards/SC/2026-2027/biology-1-eocep.json` | The three new constraint entries (with `banned_terms`, `scope_note`). |
| `backend/app/services/engine/family.py` | `QuestionFamily.eocep_aware`; `generate_set(..., eocep=False)`. |
| `backend/app/services/generation.py` | Passes `eocep` to `generate_set`; records the scope note in `options`. |
| `backend/app/services/families/protein_synthesis.py` | EOCEP rendering without strand ends. |
| `backend/app/schemas/__init__.py`, `backend/app/services/bank.py` | `StandardSummary.eocep_scope_note`. |
| `backend/tests/test_eocep_families.py` (new) | Scans, classroom guarantees, B-LS1-1 EOCEP checks. |
| `backend/tests/test_api.py`, `backend/tests/test_variants_api.py` | Import, availability, scope note, provenance, variant. |
| `frontend/src/pages/Generate.tsx`, `frontend/openapi.json`, `frontend/src/api/schema.d.ts` | Scope note on the Generate page; regenerated API types. |
| `HANDOFF.md` | Records what exists and what is unverified. |

---

### Task 0: Prepare the checkout (no code)

**Files:** none.

- [ ] **Step 1: Confirm nothing else is editing this checkout**

Run: `ps aux | grep -E "[c]odex|[c]laude" | awk '{print $2, $11, $12, $13}'` and `git status --short`

Expected: you know which other sessions are open. If a Codex or other Claude session might be working in `/home/brandon/apps/science-bank`, **stop and ask Brandon to close it**. Two agents editing one working tree will overwrite each other.

- [ ] **Step 2: Confirm the branch and preserve, never discard, the old uncommitted edits**

The working tree may hold uncommitted edits for the superseded design (`data/standards/SC/2026-2027/biology-1-eocep.json` and `backend/tests/test_api.py`). Keep them in a stash in case Brandon wants them; do not run `git checkout -- <file>` or `git restore` on them.

```bash
git branch --show-current                    # Expected: feat/eocep-new-biology-families
git log --oneline -4                          # Expected: 56e223e and the spec commits on top of f4b90b1
git stash push -m "superseded EOCEP design: exclude-templates JSON and tests" -- \
  data/standards/SC/2026-2027/biology-1-eocep.json backend/tests/test_api.py
git status --short                            # Expected: no output (clean)
git stash list                                # Expected: the stash above
```

- [ ] **Step 3: Start the throwaway test database**

```bash
docker ps --format '{{.Names}}' | grep -x sb-testdb || docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
sleep 6
cd backend && TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest tests/test_engine.py -q
```

Expected: all pass (a baseline on a clean tree).

Every `pytest` command below runs from `backend/` with `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test` set. Every `git apply` command runs from the repository root.

---

### Task 1: Constraint data and its structural test

**Files:**
- Modify: `data/standards/SC/2026-2027/biology-1-eocep.json`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: the importer (`app.standards.importer`) which stores each `constraints[code]` object whole in `standards.eocep_constraints`; the `db` fixture, which imports `data/standards` into the test database.
- Produces: for B-LS1-1, B-LS3-2, B-LS4-4 the keys `source_pages`, `allowed_terminology`, `prohibitions`, `requirements`, `excluded_templates`, `banned_terms`, and (B-LS3-2 only) `scope_note`. Task 2's scans read `banned_terms` from the JSON file; Task 3 reads `scope_note`.

- [ ] **Step 1: Write the failing tests (count, structure, and the three old denials removed)**

This patch changes the expected EOCEP import count from 2 to 5, adds `test_new_eocep_constraints_are_imported_as_the_source_states_them`, and deletes the three assertions that EOCEP is denied for B-LS1-1, B-LS3-2 and B-LS4-4 (they become wrong once the data exists; their replacement is in Task 3).

```bash
git apply -p1 <<'PATCH'
--- a/backend/tests/test_api.py
+++ b/backend/tests/test_api.py
@@ -36,7 +36,7 @@
         "courses": 3,
         "standards": 38,
         "bundles": 15,
-        "eocep_constraints": 2,
+        "eocep_constraints": 5,
     }
     assert sorted(db.execute(select(Standard.id, Standard.content_sha256)).all()) == before
     # PE codes shared by Biology 1 and 2 are distinct rows with their own boundaries
@@ -56,6 +56,58 @@
     assert mismatched == 0
 
 
+def test_new_eocep_constraints_are_imported_as_the_source_states_them(db):
+    from app.models import Course, Standard
+
+    standards = {
+        code: standard
+        for code, standard in db.execute(
+            select(Standard.code, Standard)
+            .join(Course)
+            .where(Course.slug == "biology-1", Standard.code.in_(("B-LS1-1", "B-LS3-2", "B-LS4-4")))
+        )
+    }
+
+    dna = standards["B-LS1-1"].eocep_constraints
+    assert dna["source_pages"] == [3, 4]
+    assert len(dna["allowed_terminology"]) == 37 and "codon" in dna["allowed_terminology"]
+    assert dna["banned_terms"] == [
+        "3'",
+        "5'",
+        "intron",
+        "exon",
+        "Okazaki",
+        "initiation",
+        "elongation",
+        "termination",
+        "codon wheel",
+    ]
+    assert dna["excluded_templates"] == {} and "scope_note" not in dna
+    assert "A codon chart will be included in an item when needed as a reference." in dna["requirements"]
+
+    mutation = standards["B-LS3-2"].eocep_constraints
+    assert mutation["source_pages"] == [15]
+    assert len(mutation["allowed_terminology"]) == 37
+    assert mutation["banned_terms"] == ["prophase", "metaphase", "anaphase", "telophase", "codon wheel"]
+    assert mutation["excluded_templates"] == {}
+    assert (
+        mutation["scope_note"] == "Covers the mutation part of this standard only; meiosis items are not yet available."
+    )
+
+    selection = standards["B-LS4-4"].eocep_constraints
+    assert selection["source_pages"] == [19]
+    assert len(selection["allowed_terminology"]) == 20
+    assert selection["banned_terms"] == [
+        "allele frequenc",
+        "Hardy-Weinberg",
+        "Hardy Weinberg",
+        "chi-square",
+        "chi square",
+    ]
+    assert selection["requirements"] == [] and selection["excluded_templates"] == {}
+    assert "scope_note" not in selection
+
+
 # ---- auth ------------------------------------------------------------------------------------
 
 
@@ -216,39 +268,6 @@
         },
     )
     assert denied_2.status_code == 422
-    bio_1_dna = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS1-1")
-    denied_3 = client.post(
-        "/api/generate/preview",
-        json={
-            "standard_id": bio_1_dna["id"],
-            "family_key": "dna-protein-synthesis",
-            "quantity": 1,
-            "generation_mode": "eocep",
-        },
-    )
-    assert denied_3.status_code == 422
-    bio_1_mut = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS3-2")
-    denied_4 = client.post(
-        "/api/generate/preview",
-        json={
-            "standard_id": bio_1_mut["id"],
-            "family_key": "mutation-effects",
-            "quantity": 1,
-            "generation_mode": "eocep",
-        },
-    )
-    assert denied_4.status_code == 422
-    bio_1_ns = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS4-4")
-    denied_5 = client.post(
-        "/api/generate/preview",
-        json={
-            "standard_id": bio_1_ns["id"],
-            "family_key": "natural-selection-trend",
-            "quantity": 1,
-            "generation_mode": "eocep",
-        },
-    )
-    assert denied_5.status_code == 422
 
 
 def test_eocep_mode_excludes_constructed_response(client):
PATCH
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_api.py -q -k "import_counts or imported_as_the_source or eocep_mode_uses_imported"`

Expected: `2 failed, 1 passed`. `test_import_counts_and_idempotency` fails with `{'eocep_constraints': 2} != {'eocep_constraints': 5}`; `test_new_eocep_constraints_are_imported_as_the_source_states_them` fails with `TypeError: 'NoneType' object is not subscriptable` (the standards have no constraints yet). `test_eocep_mode_uses_imported_biology_1_constraints` already passes, because the removed denial assertions were the only part that conflicts.

- [ ] **Step 3: Write the data**

Replace the whole of `data/standards/SC/2026-2027/biology-1-eocep.json` with exactly this. The B-LS2-1 and B-LS3-3 entries are unchanged from `HEAD`. The new entries' term lists were checked against the PDF text (37 terms for B-LS1-1 including `codon`, 37 for B-LS3-2, 20 for B-LS4-4).

```json
{
  "course_slug": "biology-1",
  "source_document": "EOCEP Biology 1 Assessment Specifications 2025-2026",
  "source_authority": "South Carolina Department of Education",
  "source_file": "SCDoE Targets/State Assessment Specifications_EOCEP Biology 1_2025-2026.pdf",
  "constraints": {
    "B-LS1-1": {
      "source_pages": [3, 4],
      "allowed_terminology": ["adenine", "amino acid", "anticodon", "chromosome", "codon", "cytoplasm", "cytosine", "deoxyribose", "differentiation", "DNA", "double helix", "endoplasmic reticulum (SER & RER)", "enzyme", "gene", "Golgi apparatus", "guanine", "mRNA", "mutation", "nucleic acid", "nucleotide", "nucleus", "nuclear membrane", "peptide bond", "polypeptide", "protein synthesis", "ribose", "ribosome", "RNA", "rRNA", "start codon", "stop codon", "thymine", "transcription", "translation", "tRNA", "uracil", "vesicle"],
      "prohibitions": ["identify specific cell types/proteins without a description of the cell type/protein and its function", "refer to protein structures beyond primary structure (sequence of amino acids)", "require student knowledge of post-translational modification", "require students to recall which codons produce specific amino acids", "require students to identify the biochemistry of protein synthesis, e.g., RNA polymerase", "use or reference the codon wheel", "use the terms intron, exon, 3'/5', Okazaki fragment, initiation, elongation, termination"],
      "requirements": ["A codon chart will be included in an item when needed as a reference.", "Students are expected to understand and apply the base pair rule for DNA and RNA.", "Students are expected to understand and translate codon sequences using the codon chart.", "Students are expected to understand the general steps/process of protein synthesis.", "Students are expected to know the roles of the ER and Golgi apparatus in protein production: i.e., ER modifies proteins and the Golgi apparatus packages them for transport.", "Students may be expected to show understanding of the role of differentiation in the functioning of specialized systems of cells (i.e., the results of the process of differentiation)."],
      "excluded_templates": {},
      "banned_terms": ["3'", "5'", "intron", "exon", "Okazaki", "initiation", "elongation", "termination", "codon wheel"]
    },
    "B-LS2-1": {
      "source_pages": [11, 12],
      "allowed_terminology": ["biotic factor", "abiotic factor", "carrying capacity", "competition", "limiting factor", "population", "predation", "resource"],
      "prohibitions": ["population growth calculations", "specific nutrient cycles", "specific relationships among multiple populations"],
      "requirements": ["use models communicating data or information on carrying capacity and limiting factors"],
      "excluded_templates": {}
    },
    "B-LS3-2": {
      "source_pages": [15],
      "allowed_terminology": ["allele", "centromere", "chromatid", "chromosome", "codon (chart)", "crossing over", "daughter cell", "deletion", "diploid", "DNA", "fertilization", "frameshift", "gamete", "gene", "gene mutation", "genetic code", "genetic variation", "haploid", "homologous chromosome", "independent assortment", "insertion", "meiosis", "meiosis I", "meiosis II", "monosomy", "mutagen", "mutation", "nondisjunction", "offspring", "parent cell", "point mutation", "replication", "sexual reproduction", "somatic cell", "substitution", "trait", "trisomy"],
      "prohibitions": ["require students to define, identify, or sequence the names of phases in meiosis I and II (e.g., prophase I, metaphase I, etc.)", "require students to use the codon wheel"],
      "requirements": ["A codon chart will be provided, when necessary.", "References to viable errors occurring during replication are defined as errors that bypass DNA proofreading (the cell cycle successfully moves past G2).", "Students are required to use models of meiosis to construct explanations of new genetic combinations.", "Students must be able to recognize and sequence the events represented in models of meiosis."],
      "excluded_templates": {},
      "banned_terms": ["prophase", "metaphase", "anaphase", "telophase", "codon wheel"],
      "scope_note": "Covers the mutation part of this standard only; meiosis items are not yet available."
    },
    "B-LS3-3": {
      "source_pages": [15, 16],
      "allowed_terminology": ["allele", "codominance", "complete dominance", "genotype", "phenotype", "probability", "Punnett square", "ratio"],
      "prohibitions": ["construct or complete a pedigree", "construct or complete a dihybrid cross", "specific genetic disorders", "Hardy-Weinberg", "Chi-square"],
      "requirements": ["may calculate monohybrid ratios or probabilities", "may analyze a completed dihybrid cross"],
      "excluded_templates": {}
    },
    "B-LS4-4": {
      "source_pages": [19],
      "allowed_terminology": ["abiotic", "adaptation", "advantageous trait", "biotic", "coevolution", "convergent evolution", "distribution", "diverge", "ecosystem", "fitness", "gene", "gene frequency", "gene pool", "geographic isolation", "natural selection", "phenotypic variation", "population", "survival rate", "trait", "variation"],
      "prohibitions": ["require students to calculate allele frequencies", "require student knowledge of Hardy-Weinberg or Chi-square"],
      "requirements": [],
      "excluded_templates": {},
      "banned_terms": ["allele frequenc", "Hardy-Weinberg", "Hardy Weinberg", "chi-square", "chi square"]
    }
  }
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_api.py -q`

Expected: PASS (all of `test_api.py`). Note: until Task 2 lands, EOCEP mode for B-LS1-1 is enabled but still prints 3′/5′. This branch must not be merged or deployed between Tasks 1 and 2.

- [ ] **Step 5: Commit**

```bash
cd backend && .venv/bin/ruff format tests/test_api.py && .venv/bin/ruff check tests/test_api.py && cd ..
git add data/standards/SC/2026-2027/biology-1-eocep.json backend/tests/test_api.py
git commit -m "feat: import EOCEP constraints for B-LS1-1, B-LS3-2 and B-LS4-4

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: EOCEP rendering for B-LS1-1 and the banned-term scans

**Files:**
- Create: `backend/tests/test_eocep_families.py`
- Modify: `backend/app/services/engine/family.py`
- Modify: `backend/app/services/generation.py`
- Modify: `backend/app/services/families/protein_synthesis.py`

**Interfaces:**
- Consumes: `banned_terms` in `biology-1-eocep.json` (Task 1); `FAMILIES` from `app.services.families.registry`.
- Produces: `QuestionFamily.eocep_aware: bool = False`; `generate_set(family, seed, quantity, doks=None, question_types=None, template_keys=None, eocep=False)`; when `eocep and family.eocep_aware`, the scenario params gain `"eocep": True` (only then, so other families' output, including the echoed `parameters`, is unchanged); `strand_text(seq, left, right, ends=True)`; `generate_for_request` passes `eocep=` to `generate_set`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_eocep_families.py` with exactly this content. It reads `banned_terms` from the data file (the thing under test), types the base-pairing ground truth itself, and includes a positive control: Classroom B-LS1-1 output must trip the scan, so a scan that cannot see 3′/5′ cannot pass silently.

```python
"""EOCEP practice mode for B-LS1-1, B-LS3-2 and B-LS4-4: banned-term scans and the classroom guarantees.

The banned terms are read from the imported data file, the thing under test. Ground truth for base pairing is typed
here, not imported from the family module.
"""

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
TEMPLATE_PAIR = {"A": "U", "T": "A", "G": "C", "C": "G"}  # template base -> mRNA base


def _constraints() -> dict:
    path = get_settings().standards_dir / "SC" / "2026-2027" / "biology-1-eocep.json"
    return json.loads(path.read_text())["constraints"]


def _selected_response_keys(family) -> list[str]:
    return [t.key for t in family.templates if t.question_type != "constructed_response"]


def _student_text(out: dict) -> str:
    """Everything a student or teacher reads, as one string with the primes normalised to an apostrophe."""
    shown = [{k: v for k, v in group.items() if k != "parameters"} for group in out["groups"]]
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
                q["template_key"],
                q["dok"],
                next((c["label"] for c in q["choices"] if c["correct"]), None),
                len(q["choices"]),
            )
            for q in group["questions"]
        ]
        for group in out["groups"]
    ]


# ---- the scan itself is sensitive -------------------------------------------------------------


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


def test_classroom_dna_output_does_contain_strand_ends_so_the_scan_has_a_positive_control():
    banned = _constraints()["B-LS1-1"]["banned_terms"]
    out = generate_set(FAMILIES["dna-protein-synthesis"], "positive-control", 8, template_keys=SEQUENCE_KEYS)
    assert {"3'", "5'"} <= set(_hits(_student_text(out), banned))


# ---- EOCEP output obeys each standard's "items may not" rules ---------------------------------


@pytest.mark.parametrize("key", list(FAMILY_STANDARD))
def test_eocep_output_has_no_banned_terms(key):
    family = FAMILIES[key]
    banned = _constraints()[FAMILY_STANDARD[key]]["banned_terms"]
    keys = _selected_response_keys(family)
    for seed in SEEDS:
        out = generate_set(family, seed, 8, template_keys=keys, eocep=True)
        assert _hits(_student_text(out), banned) == [], (key, seed)


# ---- classroom and the other families are untouched -------------------------------------------


@pytest.mark.parametrize("key", ["mutation-effects", "natural-selection-trend", "trait-probability", "reaction-rate"])
def test_families_that_do_not_render_differently_are_identical_in_both_modes(key):
    family = FAMILIES[key]
    assert family.eocep_aware is False
    for seed in SEEDS[:20]:
        assert _digest(generate_set(family, seed, 8)) == _digest(generate_set(family, seed, 8, eocep=True))


def test_only_the_dna_family_is_eocep_aware():
    assert {k for k, f in FAMILIES.items() if f.eocep_aware} == {"dna-protein-synthesis"}


def test_dna_classroom_output_is_the_same_whether_or_not_the_flag_is_named():
    family = FAMILIES["dna-protein-synthesis"]
    for seed in SEEDS[:20]:
        assert _digest(generate_set(family, seed, 8)) == _digest(generate_set(family, seed, 8, eocep=False))


def test_dna_eocep_keeps_scenarios_keys_and_choice_counts():
    family = FAMILIES["dna-protein-synthesis"]
    keys = _selected_response_keys(family)
    for seed in SEEDS:
        classroom = generate_set(family, seed, 8, template_keys=keys)
        eocep = generate_set(family, seed, 8, template_keys=keys, eocep=True)
        assert _shape(classroom) == _shape(eocep), seed
        assert [g["parameters"]["genes"] for g in classroom["groups"]] == [
            g["parameters"]["genes"] for g in eocep["groups"]
        ]
        assert _digest(classroom) != _digest(eocep)


# ---- B-LS1-1 in EOCEP mode ---------------------------------------------------------------------


def test_dna_eocep_codon_table_covers_every_codon_the_student_must_read():
    family = FAMILIES["dna-protein-synthesis"]
    seen = {"translate_mrna": 0, "dna_to_protein": 0}
    for seed in SEEDS:
        out = generate_set(family, seed, 8, template_keys=SEQUENCE_KEYS, eocep=True)
        for group in out["groups"]:
            table = next(t for t in group["stimulus"]["tables"] if t["caption"].startswith("Codon table"))
            assert table["caption"] == "Codon table (mRNA codons)"
            shown = {row["codon"] for row in table["rows"]}
            for q in group["questions"]:
                if q["template_key"] == "translate_mrna":
                    mrna = re.search(r"is ([ACGU]+), read from left to right", q["stem"]).group(1)
                elif q["template_key"] == "dna_to_protein":
                    template = re.search(r"is ([ACGT]+), read from left to right", q["stem"]).group(1)
                    mrna = "".join(TEMPLATE_PAIR[b] for b in template)
                else:
                    continue
                seen[q["template_key"]] += 1
                needed = {mrna[i : i + 3] for i in range(0, len(mrna), 3)}
                assert needed <= shown, (seed, q["template_key"], needed - shown)
    assert all(seen.values()), seen


def test_dna_eocep_transcribe_key_is_the_pairing_of_the_strand_shown():
    family = FAMILIES["dna-protein-synthesis"]
    checked = 0
    for seed in SEEDS:
        out = generate_set(family, seed, 4, template_keys=["transcribe_mrna"], eocep=True)
        for q in (q for g in out["groups"] for q in g["questions"]):
            template = re.search(r"is ([ACGT]+), read from left to right", q["stem"]).group(1)
            expected = "".join(TEMPLATE_PAIR[b] for b in template)
            assert [c["text"] for c in q["choices"] if c["correct"]] == [expected], seed
            assert sum(c["text"] == expected for c in q["choices"]) == 1
            checked += 1
    assert checked == len(SEEDS) * 4


def test_dna_eocep_states_direction_in_words_and_never_in_prime_notation():
    family = FAMILIES["dna-protein-synthesis"]
    out = generate_set(family, "words", 12, template_keys=SEQUENCE_KEYS, eocep=True)
    text = _student_text(out)
    assert "left to right" in text
    assert "'" not in text
    for group in out["groups"]:
        for q in group["questions"]:
            if q["template_key"] == "transcribe_mrna":
                assert re.fullmatch(r"[ACGU]+", next(c["text"] for c in q["choices"] if c["correct"]))


def test_dna_eocep_reversed_distractors_are_explained_without_ends():
    family = FAMILIES["dna-protein-synthesis"]
    rationales = set()
    for seed in SEEDS:
        out = generate_set(family, seed, 8, template_keys=["translate_mrna", "dna_to_protein"], eocep=True)
        for group in out["groups"]:
            for q in group["questions"]:
                rationales |= {c["rationale"] for c in q["choices"] if "reverse" in c["rationale"]}
    assert rationales == {
        "The amino acids are in reverse order. "
        "Codons are read in order from the first codon, at the left end of the mRNA."
    }
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_eocep_families.py -q`

Expected: `14 failed, 5 passed`, the failures mostly `TypeError: generate_set() got an unexpected keyword argument 'eocep'` and `AttributeError: ... has no attribute 'eocep_aware'`. The five that already pass are the scan-sensitivity tests (`test_scan_finds_every_planted_banned_term` for the three standards and `test_scan_does_not_flag_ordinary_numbers`) and the Classroom positive control; they test the scan itself and are proved sensitive by the mutations in Step 5.

- [ ] **Step 3: Add the engine flag and pass the mode through**

This patch adds `eocep_aware` to `QuestionFamily`, the `eocep` argument to `generate_set`, the `eocep=eocep` pass-through in `generate_for_request`, and the EOCEP rendering in `protein_synthesis.py` (strand text without ends, direction in words, "Codon table (mRNA codons)", and reworded "reversed"/"swapped" rationales). Classroom paths are untouched.

```bash
cd /home/brandon/apps/science-bank
git apply -p1 <<'PATCH'
--- a/backend/app/services/engine/family.py
+++ b/backend/app/services/engine/family.py
@@ -22,6 +22,8 @@
     stimulus_kind: str
     bindings: tuple[Binding, ...]
     templates: tuple[TemplateSpec, ...]
+    # True only for a family that renders differently in EOCEP practice mode; it then reads params["eocep"].
+    eocep_aware: bool = False
 
     @abstractmethod
     def build_scenario(self, rng: Rng) -> dict[str, Any]:
@@ -90,6 +92,7 @@
     doks: list[int] | None = None,
     question_types: list[str] | None = None,
     template_keys: list[str] | None = None,
+    eocep: bool = False,
 ) -> dict[str, Any]:
     if not 1 <= quantity <= MAX_QUANTITY:
         raise GenerationError(f"quantity must be between 1 and {MAX_QUANTITY}")
@@ -103,6 +106,8 @@
     while remaining > 0:
         base = (family.key, family.version, seed, group_index)
         params = family.build_scenario(Rng(*base, "scenario"))
+        if eocep and family.eocep_aware:
+            params = {**params, "eocep": True}
         take = min(remaining, len(eligible))
         chosen_keys = {t.key for t in Rng(*base, "select").sample(eligible, take)}
         chosen = [t for t in eligible if t.key in chosen_keys]
--- a/backend/app/services/families/protein_synthesis.py
+++ b/backend/app/services/families/protein_synthesis.py
@@ -82,8 +82,9 @@
     return AMINO_ACIDS[CODONS[codon]]
 
 
-def strand_text(seq: str, left: str, right: str) -> str:
-    return f"{left}′-{seq}-{right}′"
+def strand_text(seq: str, left: str, right: str, ends: bool = True) -> str:
+    """A strand as written for students; EOCEP practice items may not use 3'/5' notation, so `ends=False` omits it."""
+    return f"{left}′-{seq}-{right}′" if ends else seq
 
 
 def transcribe_candidates(gene: dict[str, Any]) -> list[tuple[str, str]]:
@@ -218,6 +219,12 @@
         "complementary mRNA."
     ),
 }
+# EOCEP practice items may not use 3'/5' notation, so direction is given in words (strands are written left to right).
+_PROTEIN_WHY_EOCEP = {
+    **_PROTEIN_WHY,
+    "reversed": "The amino acids are in reverse order. Codons are read in order from the first codon, at the left end of the mRNA.",
+    "swapped": "Two amino acids are in the wrong order. Each codon is read in order from the first codon, at the left end of the mRNA.",
+}
 
 
 CATEGORY_TEXT = {
@@ -247,6 +254,7 @@
         "sequence, and explain how the order of nucleotides in a gene determines the protein."
     )
     stimulus_kind = "dna_protein_synthesis"
+    eocep_aware = True
     bindings = (Binding("SC", "biology-1", "B-LS1-1"),)
     templates = (
         TemplateSpec("transcribe_mrna", "Transcribe a template strand", 1, "multiple_choice", "evidence", 4),
@@ -276,7 +284,9 @@
             intro.append(_TABLE_RULE)
             tables.append(
                 {
-                    "caption": "Codon table (mRNA codons, read 5′ to 3′)",
+                    "caption": "Codon table (mRNA codons)"
+                    if params.get("eocep")
+                    else "Codon table (mRNA codons, read 5′ to 3′)",
                     "columns": [{"key": "codon", "label": "mRNA codon"}, {"key": "amino_acid", "label": "Amino acid"}],
                     "rows": params["codon_table"],
                 }
@@ -319,7 +329,8 @@
 
     def _q_transcribe_mrna(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
         g = params["genes"]["transcribe"]
-        correct = strand_text(g["mrna"], "5", "3")
+        ends = not params.get("eocep")
+        correct = strand_text(g["mrna"], "5", "3", ends)
         candidates = transcribe_candidates(g)
         # One wrong answer always starts with the correct AUG, so the start codon alone never gives the key away.
         forced = [c for c in candidates if c[0] == "later_codons_copied"]
@@ -330,12 +341,19 @@
                 True,
                 "Correct: transcription pairs each template base with its complement (A–U, T–A, G–C, C–G).",
             )
-        ] + [DraftChoice(strand_text(strand, "5", "3"), False, _TRANSCRIBE_WHY[kind]) for kind, strand in wrong]
-        return DraftQuestion(
-            stem=(
+        ] + [DraftChoice(strand_text(strand, "5", "3", ends), False, _TRANSCRIBE_WHY[kind]) for kind, strand in wrong]
+        if ends:
+            stem = (
                 f"The DNA template strand of {g['label']} is {strand_text(g['template'], '3', '5')}. Which mRNA, "
                 "written 5′ to 3′, is transcribed from this template strand?"
-            ),
+            )
+        else:
+            stem = (
+                f"The DNA template strand of {g['label']} is {g['template']}, read from left to right. Which mRNA, "
+                "written from left to right, is transcribed from this template strand?"
+            )
+        return DraftQuestion(
+            stem=stem,
             answer=correct,
             explanation=(
                 f"Each template base pairs with its complement (A–U, T–A, G–C, C–G), so {g['template']} is "
@@ -346,6 +364,7 @@
 
     def _q_translate_mrna(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
         g = params["genes"]["translate"]
+        why = _PROTEIN_WHY_EOCEP if params.get("eocep") else _PROTEIN_WHY
         options = protein_options(g)
         correct = sequence_text(g["protein"])
         choices = [
@@ -355,12 +374,14 @@
                 "Correct: the codons are read in order from the start codon, and each specifies the amino acid shown "
                 "in the table.",
             )
-        ] + [
-            DraftChoice(sequence_text(options[k]), False, _PROTEIN_WHY[k]) for k in ("reversed", "no_start", "swapped")
-        ]
+        ] + [DraftChoice(sequence_text(options[k]), False, why[k]) for k in ("reversed", "no_start", "swapped")]
+        if params.get("eocep"):
+            mrna = f"{g['mrna']}, read from left to right"
+        else:
+            mrna = strand_text(g["mrna"], "5", "3")
         return DraftQuestion(
             stem=(
-                f"The mRNA transcribed from {g['label']} is {strand_text(g['mrna'], '5', '3')}. Translation starts at "
+                f"The mRNA transcribed from {g['label']} is {mrna}. Translation starts at "
                 "the start codon (AUG) and ends at a stop codon. Use the codon table to find the amino acid sequence "
                 "this mRNA codes for."
             ),
@@ -374,6 +395,7 @@
 
     def _q_dna_to_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
         g = params["genes"]["protein"]
+        why = _PROTEIN_WHY_EOCEP if params.get("eocep") else _PROTEIN_WHY
         options = protein_options(g)
         correct = sequence_text(g["protein"])
         choices = [
@@ -382,13 +404,14 @@
                 True,
                 "Correct: the template is transcribed into mRNA, and the mRNA codons are translated with the table.",
             )
-        ] + [
-            DraftChoice(sequence_text(options[k]), False, _PROTEIN_WHY[k])
-            for k in ("template_as_mrna", "reversed", "swapped")
-        ]
+        ] + [DraftChoice(sequence_text(options[k]), False, why[k]) for k in ("template_as_mrna", "reversed", "swapped")]
+        if params.get("eocep"):
+            template = f"{g['template']}, read from left to right"
+        else:
+            template = strand_text(g["template"], "3", "5")
         return DraftQuestion(
             stem=(
-                f"The DNA template strand of {g['label']} is {strand_text(g['template'], '3', '5')}. The gene is "
+                f"The DNA template strand of {g['label']} is {template}. The gene is "
                 "transcribed into mRNA, and the mRNA is translated using the codon table shown. Which amino acid "
                 "sequence does this gene produce?"
             ),
--- a/backend/app/services/generation.py
+++ b/backend/app/services/generation.py
@@ -64,6 +64,7 @@
             doks=req.doks or None,
             question_types=question_types or None,
             template_keys=template_keys or None,
+            eocep=eocep,
         )
     except GenerationError as exc:
         raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
PATCH
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_eocep_families.py tests/test_protein_synthesis.py tests/test_engine.py -q`

Expected: `92 passed`, including the unchanged golden digests and all existing DNA tests.

- [ ] **Step 5: Prove the scans by planting mutations (each must make a test fail)**

Back up, mutate, run, restore. Expected results are in the comments.

```bash
cd backend
cp app/services/families/protein_synthesis.py /tmp/ps.bak
cp app/services/families/natural_selection.py /tmp/ns.bak
cp app/services/families/mutation_effects.py /tmp/me.bak

# 1. the DNA family ignores EOCEP mode: the DNA scan, the aware-family test and five B-LS1-1 tests fail (7 failed, 12 passed)
sed -i 's/^    eocep_aware = True$/    eocep_aware = False/' app/services/families/protein_synthesis.py
pytest tests/test_eocep_families.py -q | tail -9
cp /tmp/ps.bak app/services/families/protein_synthesis.py

# 2. a banned term appears in B-LS4-4 and B-LS3-2 output: both scans fail (2 failed, 1 passed)
sed -i 's/find it harder to see beetles that match the soil\./find it harder to see beetles that match the soil. Use Hardy-Weinberg./' app/services/families/natural_selection.py
sed -i '318s/.*/        intro = [_BASE_INTRO + " Name the phase, such as Prophase I."]/' app/services/families/mutation_effects.py
pytest tests/test_eocep_families.py -q -k no_banned_terms | tail -5
cp /tmp/ns.bak app/services/families/natural_selection.py
cp /tmp/me.bak app/services/families/mutation_effects.py

git diff --stat -- app/services/families/natural_selection.py app/services/families/mutation_effects.py   # Expected: empty
pytest tests/test_eocep_families.py -q                                                                  # Expected: 19 passed
```

If line 318 of `mutation_effects.py` is not the `intro = [_BASE_INTRO]` line, find it with `grep -n "intro = \[_BASE_INTRO\]" app/services/families/mutation_effects.py` and adjust the line number.

- [ ] **Step 6: Format, lint, commit**

```bash
.venv/bin/ruff format app/services/engine/family.py app/services/generation.py app/services/families/protein_synthesis.py tests/test_eocep_families.py
.venv/bin/ruff check app tests
cd .. && git add backend/tests/test_eocep_families.py backend/app/services/engine/family.py backend/app/services/generation.py backend/app/services/families/protein_synthesis.py
git commit -m "feat: render B-LS1-1 items without 3'/5' notation in EOCEP mode and scan EOCEP output for banned terms

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: `ruff format` reports files unchanged (the patch is already formatted); `ruff check` passes.

---

### Task 3: Scope note, availability, provenance and variants

**Files:**
- Modify: `backend/app/schemas/__init__.py`
- Modify: `backend/app/services/bank.py`
- Modify: `backend/app/services/generation.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_variants_api.py`

**Interfaces:**
- Consumes: `eocep_constraints["scope_note"]` (Task 1); the `eocep` pass-through (Task 2).
- Produces: `StandardSummary.eocep_scope_note: str | None` (set by `standard_summary`); `out["options"]["eocep_scope_note"]` on EOCEP generations whose standard has a note (this is what is stored in a saved question's `provenance["options"]`, because `eocep_constraints` itself is not stored).

- [ ] **Step 1: Write the failing tests**

This patch adds, to `test_api.py`: `test_eocep_is_available_for_the_new_biology_families` (three standards: 200, selected-response only, exactly the allowed templates, the constructed-response template rejected with 422 and still available in Classroom), `test_only_b_ls3_2_carries_an_eocep_scope_note`, `test_eocep_dna_items_show_no_strand_ends_but_classroom_items_do`, and `test_saved_eocep_question_records_its_mode_and_scope_note`; and to `test_variants_api.py`: `test_eocep_dna_parent_produces_a_variant_without_strand_ends`. It also contains the production changes in the same patch because they are three small lines; **apply only the test hunks first** so you can watch them fail:

```bash
git apply -p1 --include='backend/tests/*' <<'PATCH'
--- a/backend/app/schemas/__init__.py
+++ b/backend/app/schemas/__init__.py
@@ -64,6 +64,7 @@
     question_family_candidate: bool
     repeat_of_biology_1: bool
     families: list[FamilyRef]
+    eocep_scope_note: str | None = None
 
 
 class NamedText(BaseModel):
--- a/backend/app/services/bank.py
+++ b/backend/app/services/bank.py
@@ -59,6 +59,7 @@
         question_family_candidate=std.question_family_candidate,
         repeat_of_biology_1=std.repeat_of_biology_1,
         families=[FamilyRef(key=f.key, title=f.title, version=f.version) for f in families_for_standard(std)],
+        eocep_scope_note=(std.eocep_constraints or {}).get("scope_note"),
     )
 
 
--- a/backend/app/services/generation.py
+++ b/backend/app/services/generation.py
@@ -74,4 +74,7 @@
     out["options"]["generation_mode"] = req.generation_mode
     if req.generation_mode == "eocep":
         out["eocep_constraints"] = std.eocep_constraints
+        scope_note = (std.eocep_constraints or {}).get("scope_note")
+        if scope_note:
+            out["options"]["eocep_scope_note"] = scope_note
     return std, family, out
--- a/backend/tests/test_api.py
+++ b/backend/tests/test_api.py
@@ -270,6 +270,112 @@
     assert denied_2.status_code == 422
 
 
+NEW_EOCEP = (
+    (
+        "B-LS1-1",
+        "dna-protein-synthesis",
+        {"transcribe_mrna", "translate_mrna", "dna_to_protein", "gene_activity_by_cell"},
+        None,
+        "explain_dna_to_protein",
+    ),
+    (
+        "B-LS3-2",
+        "mutation-effects",
+        {"identify_mutation_type", "new_protein_after_change", "effect_on_protein", "inheritance_of_mutation"},
+        "Covers the mutation part of this standard only; meiosis items are not yet available.",
+        "defend_claim_about_change",
+    ),
+    (
+        "B-LS4-4",
+        "natural-selection-trend",
+        {"compare_survival", "trait_trend", "effect_of_change", "explain_adaptation", "predict_new_change"},
+        None,
+        "explain_with_data",
+    ),
+)
+
+
+@pytest.mark.parametrize("code,family,allowed,note,constructed", NEW_EOCEP)
+def test_eocep_is_available_for_the_new_biology_families(client, code, family, allowed, note, constructed):
+    standard = _std(client, "biology-1", code)
+    assert standard["eocep_scope_note"] == note
+    response = client.post(
+        "/api/generate/preview",
+        json={
+            "standard_id": standard["id"],
+            "family_key": family,
+            "quantity": len(allowed),
+            "generation_mode": "eocep",
+        },
+    )
+    assert response.status_code == 200
+    body = response.json()
+    assert body["options"]["generation_mode"] == "eocep"
+    assert body["standard"]["eocep_scope_note"] == note
+    questions = [q for group in body["groups"] for q in group["questions"]]
+    assert {q["question_type"] for q in questions} == {"multiple_choice"}
+    assert {q["template_key"] for q in questions} == allowed
+    rejected = client.post(
+        "/api/generate/preview",
+        json={
+            "standard_id": standard["id"],
+            "family_key": family,
+            "quantity": 1,
+            "generation_mode": "eocep",
+            "template_keys": [constructed],
+        },
+    )
+    assert rejected.status_code == 422 and constructed in rejected.json()["detail"]
+    classroom = client.post(
+        "/api/generate/preview",
+        json={"standard_id": standard["id"], "family_key": family, "quantity": 1, "template_keys": [constructed]},
+    )
+    assert classroom.status_code == 200
+
+
+def test_only_b_ls3_2_carries_an_eocep_scope_note(client):
+    noted = {(s["course_slug"], s["code"]) for s in client.get("/api/standards").json() if s["eocep_scope_note"]}
+    assert noted == {("biology-1", "B-LS3-2")}
+
+
+def test_eocep_dna_items_show_no_strand_ends_but_classroom_items_do(client):
+    standard = _std(client, "biology-1", "B-LS1-1")
+    base = {"standard_id": standard["id"], "family_key": "dna-protein-synthesis", "quantity": 3, "seed": "ends"}
+    keys = ["transcribe_mrna", "translate_mrna", "dna_to_protein"]
+    eocep = client.post(
+        "/api/generate/preview", json={**base, "generation_mode": "eocep", "template_keys": keys}
+    ).json()
+    classroom = client.post("/api/generate/preview", json={**base, "template_keys": keys}).json()
+    eocep_text = json.dumps(eocep["groups"], ensure_ascii=False)
+    classroom_text = json.dumps(classroom["groups"], ensure_ascii=False)
+    assert "′" not in eocep_text and "5′" in classroom_text and "3′" in classroom_text
+    assert [q["template_key"] for g in eocep["groups"] for q in g["questions"]] == [
+        q["template_key"] for g in classroom["groups"] for q in g["questions"]
+    ]
+
+
+def test_saved_eocep_question_records_its_mode_and_scope_note(client, db):
+    from app.models import Question
+
+    standard = _std(client, "biology-1", "B-LS3-2")
+    body = {
+        "standard_id": standard["id"],
+        "family_key": "mutation-effects",
+        "quantity": 1,
+        "seed": "saved-eocep",
+        "generation_mode": "eocep",
+    }
+    saved = client.post("/api/generate/save", json=body)
+    assert saved.status_code == 201, saved.text
+    question = db.get(Question, saved.json()["question_ids"][0])
+    assert question.provenance["options"]["generation_mode"] == "eocep"
+    assert question.provenance["options"]["eocep_scope_note"] == standard["eocep_scope_note"]
+    assert (
+        "eocep_scope_note"
+        not in client.post("/api/generate/preview", json={**body, "generation_mode": "classroom"}).json()["options"]
+    )
+
+
 def test_eocep_mode_excludes_constructed_response(client):
     standards = client.get("/api/standards").json()
     bio1 = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS3-3")
--- a/backend/tests/test_variants_api.py
+++ b/backend/tests/test_variants_api.py
@@ -246,6 +246,28 @@
     assert variant.current_version.question_type == "multiple_choice"
 
 
+def test_eocep_dna_parent_produces_a_variant_without_strand_ends(anon, db):
+    login_as(anon, "regular")
+    _, body = _generate(
+        anon,
+        "biology-1",
+        "B-LS1-1",
+        "dna-protein-synthesis",
+        seed="eocep-dna",
+        generation_mode="eocep",
+        quantity=1,
+        template_keys=["translate_mrna"],
+    )
+    parent_id = anon.post("/api/generate/save", json=body).json()["question_ids"][0]
+    candidate = candidates(anon, [parent_id])[0]["candidate"]
+    assert "left to right" in candidate["stem"] and "′" not in candidate["stem"]
+    vid, _ = make_variant(anon, parent_id)
+    db.expire_all()
+    variant = db.get(Question, vid)
+    assert variant.provenance["options"]["generation_mode"] == "eocep"
+    assert "′" not in variant.current_version.stem
+
+
 def test_audit_event_names_ids_and_counts_but_no_content(anon, db):
     qid = make_question(anon, "regular")
     vid, rec = make_variant(anon, qid)
PATCH
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_api.py tests/test_variants_api.py -q -k "new_biology_families or scope_note or strand_ends or eocep_dna_parent"`

Expected: `5 failed, 2 passed`. The five fail with `KeyError: 'eocep_scope_note'` (the field does not exist yet): the three parametrised availability tests, `test_only_b_ls3_2_carries_an_eocep_scope_note` and `test_saved_eocep_question_records_its_mode_and_scope_note`. The strand-ends API test and the variant test already pass, because Task 2 delivered the rendering; here they are regression pins.

- [ ] **Step 3: Write the minimal implementation**

Apply the remaining hunks (the three production files) from the same patch:

```bash
git apply -p1 --include='backend/app/*' <<'PATCH'
--- a/backend/app/schemas/__init__.py
+++ b/backend/app/schemas/__init__.py
@@ -64,6 +64,7 @@
     question_family_candidate: bool
     repeat_of_biology_1: bool
     families: list[FamilyRef]
+    eocep_scope_note: str | None = None
 
 
 class NamedText(BaseModel):
--- a/backend/app/services/bank.py
+++ b/backend/app/services/bank.py
@@ -59,6 +59,7 @@
         question_family_candidate=std.question_family_candidate,
         repeat_of_biology_1=std.repeat_of_biology_1,
         families=[FamilyRef(key=f.key, title=f.title, version=f.version) for f in families_for_standard(std)],
+        eocep_scope_note=(std.eocep_constraints or {}).get("scope_note"),
     )
 
 
--- a/backend/app/services/generation.py
+++ b/backend/app/services/generation.py
@@ -74,4 +74,7 @@
     out["options"]["generation_mode"] = req.generation_mode
     if req.generation_mode == "eocep":
         out["eocep_constraints"] = std.eocep_constraints
+        scope_note = (std.eocep_constraints or {}).get("scope_note")
+        if scope_note:
+            out["options"]["eocep_scope_note"] = scope_note
     return std, family, out
--- a/backend/tests/test_api.py
+++ b/backend/tests/test_api.py
@@ -270,6 +270,112 @@
     assert denied_2.status_code == 422
 
 
+NEW_EOCEP = (
+    (
+        "B-LS1-1",
+        "dna-protein-synthesis",
+        {"transcribe_mrna", "translate_mrna", "dna_to_protein", "gene_activity_by_cell"},
+        None,
+        "explain_dna_to_protein",
+    ),
+    (
+        "B-LS3-2",
+        "mutation-effects",
+        {"identify_mutation_type", "new_protein_after_change", "effect_on_protein", "inheritance_of_mutation"},
+        "Covers the mutation part of this standard only; meiosis items are not yet available.",
+        "defend_claim_about_change",
+    ),
+    (
+        "B-LS4-4",
+        "natural-selection-trend",
+        {"compare_survival", "trait_trend", "effect_of_change", "explain_adaptation", "predict_new_change"},
+        None,
+        "explain_with_data",
+    ),
+)
+
+
+@pytest.mark.parametrize("code,family,allowed,note,constructed", NEW_EOCEP)
+def test_eocep_is_available_for_the_new_biology_families(client, code, family, allowed, note, constructed):
+    standard = _std(client, "biology-1", code)
+    assert standard["eocep_scope_note"] == note
+    response = client.post(
+        "/api/generate/preview",
+        json={
+            "standard_id": standard["id"],
+            "family_key": family,
+            "quantity": len(allowed),
+            "generation_mode": "eocep",
+        },
+    )
+    assert response.status_code == 200
+    body = response.json()
+    assert body["options"]["generation_mode"] == "eocep"
+    assert body["standard"]["eocep_scope_note"] == note
+    questions = [q for group in body["groups"] for q in group["questions"]]
+    assert {q["question_type"] for q in questions} == {"multiple_choice"}
+    assert {q["template_key"] for q in questions} == allowed
+    rejected = client.post(
+        "/api/generate/preview",
+        json={
+            "standard_id": standard["id"],
+            "family_key": family,
+            "quantity": 1,
+            "generation_mode": "eocep",
+            "template_keys": [constructed],
+        },
+    )
+    assert rejected.status_code == 422 and constructed in rejected.json()["detail"]
+    classroom = client.post(
+        "/api/generate/preview",
+        json={"standard_id": standard["id"], "family_key": family, "quantity": 1, "template_keys": [constructed]},
+    )
+    assert classroom.status_code == 200
+
+
+def test_only_b_ls3_2_carries_an_eocep_scope_note(client):
+    noted = {(s["course_slug"], s["code"]) for s in client.get("/api/standards").json() if s["eocep_scope_note"]}
+    assert noted == {("biology-1", "B-LS3-2")}
+
+
+def test_eocep_dna_items_show_no_strand_ends_but_classroom_items_do(client):
+    standard = _std(client, "biology-1", "B-LS1-1")
+    base = {"standard_id": standard["id"], "family_key": "dna-protein-synthesis", "quantity": 3, "seed": "ends"}
+    keys = ["transcribe_mrna", "translate_mrna", "dna_to_protein"]
+    eocep = client.post(
+        "/api/generate/preview", json={**base, "generation_mode": "eocep", "template_keys": keys}
+    ).json()
+    classroom = client.post("/api/generate/preview", json={**base, "template_keys": keys}).json()
+    eocep_text = json.dumps(eocep["groups"], ensure_ascii=False)
+    classroom_text = json.dumps(classroom["groups"], ensure_ascii=False)
+    assert "′" not in eocep_text and "5′" in classroom_text and "3′" in classroom_text
+    assert [q["template_key"] for g in eocep["groups"] for q in g["questions"]] == [
+        q["template_key"] for g in classroom["groups"] for q in g["questions"]
+    ]
+
+
+def test_saved_eocep_question_records_its_mode_and_scope_note(client, db):
+    from app.models import Question
+
+    standard = _std(client, "biology-1", "B-LS3-2")
+    body = {
+        "standard_id": standard["id"],
+        "family_key": "mutation-effects",
+        "quantity": 1,
+        "seed": "saved-eocep",
+        "generation_mode": "eocep",
+    }
+    saved = client.post("/api/generate/save", json=body)
+    assert saved.status_code == 201, saved.text
+    question = db.get(Question, saved.json()["question_ids"][0])
+    assert question.provenance["options"]["generation_mode"] == "eocep"
+    assert question.provenance["options"]["eocep_scope_note"] == standard["eocep_scope_note"]
+    assert (
+        "eocep_scope_note"
+        not in client.post("/api/generate/preview", json={**body, "generation_mode": "classroom"}).json()["options"]
+    )
+
+
 def test_eocep_mode_excludes_constructed_response(client):
     standards = client.get("/api/standards").json()
     bio1 = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS3-3")
--- a/backend/tests/test_variants_api.py
+++ b/backend/tests/test_variants_api.py
@@ -246,6 +246,28 @@
     assert variant.current_version.question_type == "multiple_choice"
 
 
+def test_eocep_dna_parent_produces_a_variant_without_strand_ends(anon, db):
+    login_as(anon, "regular")
+    _, body = _generate(
+        anon,
+        "biology-1",
+        "B-LS1-1",
+        "dna-protein-synthesis",
+        seed="eocep-dna",
+        generation_mode="eocep",
+        quantity=1,
+        template_keys=["translate_mrna"],
+    )
+    parent_id = anon.post("/api/generate/save", json=body).json()["question_ids"][0]
+    candidate = candidates(anon, [parent_id])[0]["candidate"]
+    assert "left to right" in candidate["stem"] and "′" not in candidate["stem"]
+    vid, _ = make_variant(anon, parent_id)
+    db.expire_all()
+    variant = db.get(Question, vid)
+    assert variant.provenance["options"]["generation_mode"] == "eocep"
+    assert "′" not in variant.current_version.stem
+
+
 def test_audit_event_names_ids_and_counts_but_no_content(anon, db):
     qid = make_question(anon, "regular")
     vid, rec = make_variant(anon, qid)
PATCH
```

The three changes are: `eocep_scope_note: str | None = None` on `StandardSummary`; `eocep_scope_note=(std.eocep_constraints or {}).get("scope_note")` in `standard_summary`; and in `generate_for_request`, after `out["eocep_constraints"] = ...`, `if scope_note: out["options"]["eocep_scope_note"] = scope_note`.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/test_api.py tests/test_variants_api.py tests/test_eocep_families.py -q`

Expected: `72 passed`.

- [ ] **Step 5: Format, lint, commit**

```bash
.venv/bin/ruff format app/schemas/__init__.py app/services/bank.py app/services/generation.py tests/test_api.py tests/test_variants_api.py
.venv/bin/ruff check app tests
cd .. && git add backend/app/schemas/__init__.py backend/app/services/bank.py backend/app/services/generation.py backend/tests/test_api.py backend/tests/test_variants_api.py
git commit -m "feat: EOCEP availability for the new Biology families, with a scope note for B-LS3-2

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Scope note on the Generate page and regenerated API types

**Files:**
- Modify: `frontend/openapi.json`, `frontend/src/api/schema.d.ts` (regenerated)
- Modify: `frontend/src/pages/Generate.tsx`

**Interfaces:**
- Consumes: `StandardSummary.eocep_scope_note` (Task 3), already used by `useStandards` and `useStandard`.
- Produces: a note under the standard list when EOCEP is selected and the chosen standard has one.

- [ ] **Step 1: Regenerate the API types**

```bash
cd backend && .venv/bin/python scripts/dump_openapi.py
cd ../frontend && npm run gen:api
git diff --stat openapi.json src/api/schema.d.ts
```

Expected: both files change, and the diff contains only the new optional `eocep_scope_note` field on `StandardSummary` (and any schema that embeds it). If anything else changes, stop and investigate.

- [ ] **Step 2: Show the note**

In `frontend/src/pages/Generate.tsx`, directly after the `standards` query (the line `const standards = useStandards({ course_id: courseId, with_family_only: true }, courseId !== null);`), add:

```tsx
  const selectedStandard = standards.data?.find((s) => s.id === standardId) ?? null;
```

Then, directly after `<ErrorNotice error={standards.error} />` inside the Step 1 fieldset, add:

```tsx
          {eocep && selectedStandard?.eocep_scope_note ? (
            <p role="note" className="mt-3 text-sm text-muted">
              EOCEP practice for {selectedStandard.code}: {selectedStandard.eocep_scope_note}
            </p>
          ) : null}
```

`eocep` is defined a few lines further down in the component, so move the new `selectedStandard` line (not the JSX) to sit **after** `const eocep = generationMode === "eocep";` if TypeScript reports the variable used before its declaration. The JSX only needs `selectedStandard` and `eocep`, which are both in scope by the time the component renders.

- [ ] **Step 3: Type-check, lint, build**

```bash
npx tsc -b && npm run lint && npm run build
```

Expected: all three clean.

- [ ] **Step 4: Look at it in a browser, or say it was not looked at**

If you can run the app against a scratch database, sign in, open `/generate`, choose EOCEP practice, pick B-LS3-2 and confirm the note appears; pick B-LS1-1 and confirm it does not; switch to Classroom and confirm it disappears. If you cannot, record in `HANDOFF.md` that the note was verified by type-check and build only.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/openapi.json frontend/src/api/schema.d.ts frontend/src/pages/Generate.tsx
git commit -m "feat: show the EOCEP scope note on the Generate page

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Record it, run everything, and hand over

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Update HANDOFF.md**

Make these four edits (exact old text, then new text).

1. In the "Implemented families" table, three rows end with "Classroom-only…". Replace the endings:
   - `dna-protein-synthesis`: replace `Classroom-only; no mutation-effect items (those belong to B-LS3-2, which can reuse `CODONS`/`translate`).` with `Classroom and EOCEP practice (EOCEP items show strands without 3′/5′ and say "read left to right"); no mutation-effect items (those belong to B-LS3-2, which can reuse `CODONS`/`translate`).`
   - `mutation-effects`: replace `Classroom-only; meiosis and mutagen-dataset items are a later B-LS3-2 family.` with `Classroom and EOCEP practice (EOCEP shows a note that only the mutation part of the standard is covered); meiosis and mutagen-dataset items are a later B-LS3-2 family.`
   - `natural-selection-trend`: replace `Classroom-only; no allele-frequency calculations.` with `Classroom and EOCEP practice; no allele-frequency calculations.`

2. In "Current imported EOCEP coverage", add these rows to the table (after the B-LS3-3 row) and replace the closing paragraph:

```text
| B-LS1-1 | dna-protein-synthesis | Assessment Specifications pp. 3–4 | No 3'/5', intron, exon, Okazaki fragment, initiation, elongation or termination; no codon wheel; codon chart supplied; no recall of codon meanings. EOCEP items print strands without ends. |
| B-LS3-2 | mutation-effects | Assessment Specifications p. 15 | No meiosis phase names; no codon wheel. Family covers the mutation part only (shown as a note in EOCEP mode). |
| B-LS4-4 | natural-selection-trend | Assessment Specifications p. 19 | No allele-frequency calculations, Hardy-Weinberg or chi-square. |

Enforcement: each entry's `banned_terms` is scanned in `tests/test_eocep_families.py` over many seeds. The `allowed_terminology` lists are reference only (the source says terms "could be used"). Do not claim EOCEP support for other Biology 1 standards until their constraints are imported and tested the same way.
```

3. In "Immediate recommended work", replace item 1 with: `1. **EOCEP constraints for B-LS1-1, B-LS3-2 and B-LS4-4**: built on branch `feat/eocep-new-biology-families`, awaiting review, merge and deploy by Brandon. See its spec and plan.`

4. Under "Not verified in a real browser on production", append: `, and the EOCEP scope note on the Generate page (verified by type-check and build only unless Step 4 of Task 4 was done)`.

Also state in the HANDOFF entry that `eocep_constraints` is not stored in a saved question's provenance, only `options.generation_mode` and (for B-LS3-2) `options.eocep_scope_note`.

- [ ] **Step 2: Full verification**

```bash
cd backend
.venv/bin/ruff check app tests
pytest -q -p no:cacheprovider
cd ../frontend && npx tsc -b && npm run lint && npm run build
```

Expected: ruff clean; **427 passed, zero skipped** (400 existing plus 19 in `test_eocep_families.py`, 7 in `test_api.py` and 1 in `test_variants_api.py`); frontend clean.

- [ ] **Step 3: Commit, stop the test database**

```bash
cd .. && git add HANDOFF.md && git commit -m "docs: record EOCEP constraints for the three new Biology 1 families

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
docker stop sb-testdb
git status --short   # Expected: clean
```

- [ ] **Step 4: Stop and hand over**

Report to Brandon: what was built, the test counts, the Review Focus items still needing a human read (a few EOCEP B-LS1-1 items; the Generate page note), and what was not verified. A fresh-context review of the whole branch comes next; merge, deploy and push wait for his explicit yes. The stash `superseded EOCEP design…` stays until he says to drop it.
