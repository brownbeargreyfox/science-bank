# Natural Selection Trend (B-LS4-4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the deterministic `natural-selection-trend` question family for Biology 1 B-LS4-4: six templates built from a curated fictional case, a table (and line chart) of trait counts out of 100 sampled individuals per generation, an environmental change partway through, and a survival experiment.

**Architecture:** One new module `families/natural_selection.py`: a six-case bank (each case has two environments, each favouring one variant), a trajectory drawer that simulates selection with independently drawn survival rates per environment and rejects any draw that breaks the spec's constraints, a survival-experiment drawer with engineered "trap" cases, a scenario function, and the `NaturalSelectionTrend` class. Templates are added task by task; registry, golden digest, API tests, and docs land last.

**Tech Stack:** Python 3.12, the existing question-family engine, pytest. No migration, no frontend change (tables and the multi-series line chart already render). The standards data already flags B-LS4-4 as a family candidate, so no data edit is needed.

**Spec:** `docs/superpowers/specs/2026-10-03-natural-selection-trend-design.md`

**Provenance:** every code block and test below was run in a sandbox copy of the repository before this plan was written (20 tests plus the engine tests passed, and four mutation checks failed as intended); the executor still follows TDD and watches each test fail first.

## Global Constraints

- Deterministic: randomness only through `Rng`; no `random`, no Python `hash()`; version `1.0.0`. Any later output change bumps the version and the golden digest in the same commit.
- Every displayed generation totals exactly 100 sampled individuals, with each variant in `[2, 98]`; every survival row has an integer `0 <= survived <= started`.
- Items speak only of the fraction of the population with a trait, at the level of the population across generations. No allele or gene frequency, Hardy-Weinberg, genetic drift, gene flow, or speciation. The word "need" appears only in the needs-based `explain_adaptation` distractor and its rationale, and in the model answer's sentence that individuals did not change because they needed to.
- Resistance cases are fictional, with no health or treatment claim: never infection, disease, patient, treatment, medicine, drug, hospital, human, or antibiotic.
- `predict_new_change` states that the environment reverses to its earlier conditions while all other conditions stay the same, and asks only for direction (no digits, percent signs, or generation numbers in its stem or choices).
- Choices are shuffled by the engine's deterministic `finalize_choices`; every MC item has exactly four distinct choices, one key, a rationale for each. Constructed response has an empty choice list.
- Classroom-only; bound only to `SC / biology-1 / B-LS4-4`; EOCEP mode stays rejected.
- Backend commands run from `backend/`. Format only the files you touched (`.venv/bin/ruff format <files>`); running `ruff format app tests` reformats two unrelated files. `.venv/bin/ruff check app tests` must be clean. Engine tests need no database; `test_api.py` needs `TEST_DATABASE_URL` against a throwaway Postgres (port 54332, container `sb-testdb`, never production).
- Unused imports break `ruff check`: add each import where it is first used.

## Review Focus

- A displayed row that does not total 100, or a survival row with `survived > started` (Tasks 1, 2, 5; the guards were mutation-checked in the sandbox).
- The correct answer identifiable by position or by one choice being longer: position variation across 200 seeds for every MC template, and `explain_adaptation` constant text where the key is not the unique longest (Tasks 3, 5).
- Individuals-changing-because-they-need-to language in a key, stem, or stimulus, or an `explain_adaptation` key missing a link of the chain (Tasks 3, 4, 5).
- `predict_new_change` containing a number or asking for more than direction, or "more common before the change" being ambiguous when the counts are near 50/50 (Tasks 1, 4).
- One item revealing another item's key within a set, notably `explain_adaptation` or `explain_with_data` giving away `effect_of_change` (Tasks 3, 4, 5).

## Decisions recorded from the sandbox run

- The fictional compound is **Compound Zeta**, not "R-12", so the digit-free guard on `predict_new_change` can cover every case.
- Selection constraints add `counts[l1] >= 60` and `counts[-1] <= 45` for the variant favoured first, so "more common before the change" and "more common now" are never near 50/50; the `predict_new_change` key is therefore phrased "the variant that was more common before the change".
- The survival-trap flag is chosen once per scenario and the trajectory is redrawn when the chosen kind is infeasible for the drawn rates; choosing it inside the retry loop gave only 20% traps.
- The spec has been amended with these three points.

## File map

| File | Responsibility |
|---|---|
| `backend/app/services/families/natural_selection.py` (create) | case bank, data drawers, scenario, `NaturalSelectionTrend` |
| `backend/tests/test_natural_selection.py` (create) | independent checks |
| `backend/app/services/families/registry.py` (modify) | register |
| `backend/tests/test_engine.py`, `backend/tests/test_api.py` (modify) | golden digest, generation matrix, EOCEP denial, Biology 2 mismatch, with-family list |
| `HANDOFF.md`, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md` (modify) | docs |

---

### Task 1: Case bank and scenario

**Files:**
- Create: `backend/app/services/families/natural_selection.py`
- Create: `backend/tests/test_natural_selection.py`

**Interfaces:**
- Produces (importable as `from app.services.families import natural_selection as ns`): `CASES` (six cases, each with `organism`, `trait`, `intro`, `variants` keyed `a`/`b` with `label` and `noun`, and `envs` each with `favors`, `is`, `became`, `returns`), `SAMPLE = 100`, `next_count`, `draw_trajectory`, `draw_survival`, and `draw_scenario(rng)` returning `case`, `env_first`, `env_second`, `first_favors`, `second_favors`, `l1`, `l2`, `rows` (list of `{"generation", "a", "b"}`), and `survival` (`trap` and `rows` of `{"variant", "started", "survived"}`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_natural_selection.py`:

```python
"""Independent checks for natural-selection-trend (B-LS4-4).

Which variant each environment favours is typed here, not read from the module under test; every item key is recomputed
from the numbers in the displayed tables.
"""

import json

from app.services.engine.core import Rng
from app.services.families import natural_selection as ns

SEEDS = [f"nst-{i}" for i in range(200)]
FAVORS = {  # case -> environment -> the variant it favours
    "beetles": {"dark_soil": "a", "light_soil": "b"},
    "bacteria": {"with_zeta": "a", "without_zeta": "b"},
    "finches": {"hard_seeds": "a", "soft_seeds": "b"},
    "hares": {"snow": "a", "bare": "b"},
    "minnows": {"predators": "a", "no_predators": "b"},
    "shrubs": {"dry": "a", "wet": "b"},
}


def _scenario(seed: str) -> dict:
    return ns.draw_scenario(Rng("scenario", seed))


# ---- the case bank -------------------------------------------------------------------------


def test_every_case_has_two_environments_that_favour_different_variants():
    assert set(ns.CASES) == set(FAVORS)
    for key, case in ns.CASES.items():
        assert {e: v["favors"] for e, v in case["envs"].items()} == FAVORS[key]
        assert sorted(FAVORS[key].values()) == ["a", "b"]
        assert set(case["variants"]) == {"a", "b"}
        for env in case["envs"].values():
            assert all(env[k].endswith(".") for k in ("is", "became", "returns"))
            assert not any(ch.isdigit() for k in ("is", "became", "returns") for ch in env[k])


# ---- the generation table ------------------------------------------------------------------


def test_every_generation_row_totals_exactly_100_and_stays_in_bounds():
    for seed in SEEDS:
        s = _scenario(seed)
        json.dumps(s)
        rows = s["rows"]
        assert s["l1"] in (3, 4) and s["l2"] in (3, 4)
        assert [r["generation"] for r in rows] == list(range(s["l1"] + s["l2"] + 1))
        for r in rows:
            assert r["a"] + r["b"] == 100, (seed, r)
            assert 2 <= r["a"] <= 98 and 2 <= r["b"] <= 98, (seed, r)


def test_selection_moves_the_favoured_variant_every_generation_and_reverses_after_the_change():
    for seed in SEEDS:
        s = _scenario(seed)
        rows = s["rows"]
        first = FAVORS[s["case"]][s["env_first"]]
        second = FAVORS[s["case"]][s["env_second"]]
        assert first != second and (s["first_favors"], s["second_favors"]) == (first, second)
        for g in range(len(rows) - 1):
            favoured = first if g < s["l1"] else second
            assert rows[g + 1][favoured] - rows[g][favoured] >= 3, (seed, g)
        assert 18 <= rows[0][first] <= 32
        assert rows[s["l1"]][first] - rows[0][first] >= 25
        assert rows[s["l1"]][first] >= 60 and rows[-1][first] <= 45  # clearly ahead, then clearly behind
        assert rows[s["l1"]][first] - rows[-1][first] >= 20


def test_the_winner_varies_and_the_table_is_not_a_mirror_image():
    winners, mirrored = {"a": 0, "b": 0}, 0
    for seed in SEEDS:
        s = _scenario(seed)
        winners[s["second_favors"]] += 1
        counts = [r[s["first_favors"]] for r in s["rows"]]
        mirrored += s["l1"] == s["l2"] and counts == counts[::-1]
    assert min(winners.values()) >= 60  # each variant wins after the change in a good share of 200 seeds
    assert mirrored <= 10  # rates are drawn independently for each environment


# ---- the survival experiment ---------------------------------------------------------------


def test_survival_rows_are_valid_and_traps_occur_about_half_the_time():
    traps = 0
    for seed in SEEDS:
        s = _scenario(seed)
        rows = {r["variant"]: r for r in s["survival"]["rows"]}
        assert set(rows) == {"a", "b"}
        for r in rows.values():
            assert r["started"] % 5 == 0 and 40 <= r["started"] <= 85
            assert isinstance(r["survived"], int) and 0 <= r["survived"] <= r["started"]
        rate = {v: rows[v]["survived"] / rows[v]["started"] for v in rows}
        assert abs(rate["a"] - rate["b"]) >= 0.15 and rows["a"]["survived"] != rows["b"]["survived"]
        higher = "a" if rate["a"] > rate["b"] else "b"
        assert higher == s["first_favors"]  # the first environment favours the higher-rate variant
        more_survivors = "a" if rows["a"]["survived"] > rows["b"]["survived"] else "b"
        assert s["survival"]["trap"] == (more_survivors != higher)
        traps += s["survival"]["trap"]
    assert 60 <= traps <= 140  # about half of 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `.venv/bin/python -m pytest tests/test_natural_selection.py -q`
Expected: FAIL at collection (`ImportError: cannot import name 'natural_selection'`).

- [ ] **Step 3: Write the module**

Create `backend/app/services/families/natural_selection.py`:

```python
"""Natural selection and adaptation (B-LS4-4): trait counts over generations after an environmental change.

Curated, fictional cases only. Each displayed generation is exactly 100 sampled individuals, and every key is computed
from the counts the student sees. The Biology 1 boundary excludes allele frequency calculations, so items speak only of
the fraction of the population with a trait, and always at the level of the population across generations (never
individuals changing because they need to). Resistance cases are fictional lab cultures with no health claim.
"""

from typing import Any

from app.services.engine.core import GenerationError, Rng

SAMPLE = 100
MAX_DRAWS = 300
SIZES = tuple(range(40, 90, 5))

# Each case: two heritable variants of one trait and two environments, each favouring one variant. Sentences are
# complete: `is` describes the state, `became` the change into it, `returns` the change back into it later.
CASES: dict[str, dict[str, Any]] = {
    "beetles": {
        "organism": "ground beetles",
        "trait": "shell color",
        "intro": (
            "A population of ground beetles lives on a hillside. Shell color varies among the beetles, and parents pass "
            "their shell color to their offspring. Birds that eat beetles find it harder to see beetles that match the soil."
        ),
        "variants": {
            "a": {"label": "Dark-shelled beetles", "noun": "dark-shelled beetles"},
            "b": {"label": "Light-shelled beetles", "noun": "light-shelled beetles"},
        },
        "envs": {
            "dark_soil": {
                "favors": "a",
                "is": "The hillside soil is dark.",
                "became": "The hillside soil became dark.",
                "returns": "The hillside soil becomes dark again.",
            },
            "light_soil": {
                "favors": "b",
                "is": "The hillside soil is light.",
                "became": "The hillside soil became light.",
                "returns": "The hillside soil becomes light again.",
            },
        },
    },
    "bacteria": {
        "organism": "soil bacteria",
        "trait": "resistance to Compound Zeta",
        "intro": (
            "A lab culture contains a fictional soil bacterium. Some of the bacteria are resistant to Compound Zeta, a "
            "fictional chemical that stops the growth of bacteria that are not resistant. Resistance is passed from parent "
            "cells to the cells they produce. When Compound Zeta is absent, resistant bacteria grow more slowly than "
            "bacteria that are not resistant."
        ),
        "variants": {
            "a": {"label": "Resistant bacteria", "noun": "resistant bacteria"},
            "b": {"label": "Non-resistant bacteria", "noun": "non-resistant bacteria"},
        },
        "envs": {
            "with_zeta": {
                "favors": "a",
                "is": "Compound Zeta is in the culture.",
                "became": "Compound Zeta was added to the culture.",
                "returns": "Compound Zeta is added to the culture again.",
            },
            "without_zeta": {
                "favors": "b",
                "is": "There is no Compound Zeta in the culture.",
                "became": "Compound Zeta was removed from the culture.",
                "returns": "Compound Zeta is removed from the culture again.",
            },
        },
    },
    "finches": {
        "organism": "finches",
        "trait": "beak thickness",
        "intro": (
            "A population of finches lives on an island. Beak thickness varies among the finches, and parents pass their "
            "beak thickness to their offspring. Finches with thick beaks crack hard seeds more easily, and finches with "
            "thin beaks eat soft seeds more easily."
        ),
        "variants": {
            "a": {"label": "Thick-beaked finches", "noun": "thick-beaked finches"},
            "b": {"label": "Thin-beaked finches", "noun": "thin-beaked finches"},
        },
        "envs": {
            "hard_seeds": {
                "favors": "a",
                "is": "Most of the seeds on the island are hard.",
                "became": "Most of the seeds on the island became hard.",
                "returns": "Most of the seeds on the island become hard again.",
            },
            "soft_seeds": {
                "favors": "b",
                "is": "Most of the seeds on the island are soft.",
                "became": "Most of the seeds on the island became soft.",
                "returns": "Most of the seeds on the island become soft again.",
            },
        },
    },
    "hares": {
        "organism": "marsh hares",
        "trait": "winter fur color",
        "intro": (
            "A population of marsh hares lives in a cold region. Winter fur color varies among the hares, and parents pass "
            "their fur color to their offspring. Predators find it harder to see hares that match the ground."
        ),
        "variants": {
            "a": {"label": "White-furred hares", "noun": "white-furred hares"},
            "b": {"label": "Brown-furred hares", "noun": "brown-furred hares"},
        },
        "envs": {
            "snow": {
                "favors": "a",
                "is": "Snow covers the ground all winter.",
                "became": "Snow began to cover the ground all winter.",
                "returns": "Snow covers the ground all winter again.",
            },
            "bare": {
                "favors": "b",
                "is": "The ground stays bare all winter.",
                "became": "The ground began to stay bare all winter.",
                "returns": "The ground stays bare all winter again.",
            },
        },
    },
    "minnows": {
        "organism": "pond minnows",
        "trait": "reaction speed",
        "intro": (
            "A population of minnows lives in a pond. Some minnows react quickly to danger and others react slowly, and "
            "parents pass their reaction speed to their offspring. Reacting quickly uses extra energy."
        ),
        "variants": {
            "a": {"label": "Quick-reacting minnows", "noun": "quick-reacting minnows"},
            "b": {"label": "Slow-reacting minnows", "noun": "slow-reacting minnows"},
        },
        "envs": {
            "predators": {
                "favors": "a",
                "is": "Predatory fish live in the pond.",
                "became": "Predatory fish were added to the pond.",
                "returns": "Predatory fish are added to the pond again.",
            },
            "no_predators": {
                "favors": "b",
                "is": "There are no predatory fish in the pond.",
                "became": "The predatory fish were removed from the pond.",
                "returns": "The predatory fish are removed from the pond again.",
            },
        },
    },
    "shrubs": {
        "organism": "desert shrubs",
        "trait": "root depth",
        "intro": (
            "A population of desert shrubs grows on a plain. Root depth varies among the shrubs, and parents pass their "
            "root depth to their offspring. Deep roots reach water far below the surface, and shallow roots take up "
            "surface water quickly after rain."
        ),
        "variants": {
            "a": {"label": "Deep-rooted shrubs", "noun": "deep-rooted shrubs"},
            "b": {"label": "Shallow-rooted shrubs", "noun": "shallow-rooted shrubs"},
        },
        "envs": {
            "dry": {
                "favors": "a",
                "is": "Rain is rare on the plain.",
                "became": "Rain became rare on the plain.",
                "returns": "Rain becomes rare on the plain again.",
            },
            "wet": {
                "favors": "b",
                "is": "Rain is frequent on the plain.",
                "became": "Rain became frequent on the plain.",
                "returns": "Rain becomes frequent on the plain again.",
            },
        },
    },
}


# ---- the data ----------------------------------------------------------------------------------


def next_count(count: int, own: float, other: float) -> int:
    """Count (out of 100) of a variant after one generation, given its survival rate and the other variant's."""
    p = count / SAMPLE
    return round(SAMPLE * p * own / (p * own + (1 - p) * other))


def draw_trajectory(rng: Rng) -> dict[str, Any]:
    """Counts of the variant favoured in the first environment over `l1 + l2` transitions, with the change after `l1`."""
    for _ in range(MAX_DRAWS):
        l1, l2 = rng.randint(3, 4), rng.randint(3, 4)
        fav1, unf1 = round(rng.uniform(0.74, 0.90), 2), round(rng.uniform(0.35, 0.55), 2)
        fav2, unf2 = round(rng.uniform(0.74, 0.90), 2), round(rng.uniform(0.35, 0.55), 2)
        counts = [rng.randint(18, 32)]
        for step in range(l1 + l2):
            if step < l1:
                counts.append(next_count(counts[-1], fav1, unf1))
            else:
                counts.append(next_count(counts[-1], unf2, fav2))
        rises = [b - a for a, b in zip(counts[:l1], counts[1 : l1 + 1])]
        falls = [a - b for a, b in zip(counts[l1:-1], counts[l1 + 1 :])]
        if min(rises) < 3 or min(falls) < 3 or min(counts) < 2 or max(counts) > 98:
            continue
        if counts[l1] - counts[0] < 25 or counts[l1] < 60 or counts[-1] > 45 or counts[l1] - counts[-1] < 20:
            continue
        return {"l1": l1, "l2": l2, "counts": counts, "fav1": fav1, "unf1": unf1}
    raise GenerationError(f"natural-selection-trend: no valid trajectory after {MAX_DRAWS} draws")


def draw_survival(rng: Rng, fav1: float, unf1: float, trap: bool) -> dict[str, Any] | None:
    """A one-season experiment in the first environment, or None if these rates cannot make one. A trap is a draw where
    the variant with the higher survival rate has fewer survivors, so comparing counts alone gives the wrong answer."""
    for _ in range(40):
        if trap:
            started_fav, started_other = rng.choice(SIZES[:4]), rng.choice(SIZES[-4:])
        else:
            started_fav, started_other = rng.choice(SIZES), rng.choice(SIZES)
        survived_fav = min(started_fav, max(0, round(started_fav * (fav1 + rng.uniform(-0.03, 0.03)))))
        survived_other = min(started_other, max(0, round(started_other * (unf1 + rng.uniform(-0.03, 0.03)))))
        if survived_fav / started_fav - survived_other / started_other < 0.15 or survived_fav == survived_other:
            continue
        if trap != (survived_fav < survived_other):
            continue
        return {
            "trap": trap,
            "fav": {"started": started_fav, "survived": survived_fav},
            "other": {"started": started_other, "survived": survived_other},
        }
    return None


def draw_scenario(rng: Rng) -> dict[str, Any]:
    case_key = rng.choice(sorted(CASES))
    case = CASES[case_key]
    env_first, env_second = rng.shuffled(sorted(case["envs"]))
    first_favors = case["envs"][env_first]["favors"]
    second_favors = case["envs"][env_second]["favors"]
    trap = rng.random() < 0.5  # about half of the survival experiments are traps
    for _ in range(MAX_DRAWS):
        trajectory = draw_trajectory(rng)
        survival = draw_survival(rng, trajectory["fav1"], trajectory["unf1"], trap)
        if survival is not None:
            break
    else:
        raise GenerationError(f"natural-selection-trend: no valid survival experiment after {MAX_DRAWS} draws")
    rows = []
    for generation, first_count in enumerate(trajectory["counts"]):
        a = first_count if first_favors == "a" else SAMPLE - first_count
        rows.append({"generation": generation, "a": a, "b": SAMPLE - a})
    survival_rows = {first_favors: survival["fav"], second_favors: survival["other"]}
    return {
        "case": case_key,
        "env_first": env_first,
        "env_second": env_second,
        "first_favors": first_favors,
        "second_favors": second_favors,
        "l1": trajectory["l1"],
        "l2": trajectory["l2"],
        "rows": rows,
        "survival": {
            "trap": survival["trap"],
            "rows": [{"variant": v, **survival_rows[v]} for v in ("a", "b")],
        },
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q && .venv/bin/ruff format app/services/families/natural_selection.py tests/test_natural_selection.py && .venv/bin/ruff check app tests`
Expected: 5 passed, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/families/natural_selection.py backend/tests/test_natural_selection.py
git commit -m "feat: case bank and scenario for the B-LS4-4 family"
```

---

### Task 2: Family class with the survival and trend items; registry

**Files:**
- Modify: `backend/app/services/families/natural_selection.py` (append the class)
- Modify: `backend/app/services/families/registry.py`
- Modify: `backend/tests/test_engine.py` (golden placeholder)
- Modify: `backend/tests/test_natural_selection.py` (append, and extend the imports)

**Interfaces:**
- Consumes: Task 1's `CASES`, `SAMPLE`, `draw_scenario`; `Binding`, `DraftChoice`, `DraftQuestion`, `TemplateSpec` from `app.services.engine.core`; `QuestionFamily` from `app.services.engine.family`.
- Produces: `NaturalSelectionTrend` (key `natural-selection-trend`, version `1.0.0`, `stimulus_kind = "natural_selection_trend"`) with templates `compare_survival` and `trait_trend`; helpers `_case`, `_other`, `_pct`; constant `_GENERATION_KEYS`.

- [ ] **Step 1: Write the failing tests**

Add `import re` and `from app.services.engine.family import generate_set` to the imports at the top of `test_natural_selection.py` (keep the import block sorted), then append:

```python
# ---- items: shared helpers, registration, compare_survival, trait_trend -------------------------

def _set(seed: str, *keys: str) -> dict:
    return generate_set(ns.NaturalSelectionTrend(), seed, len(keys), template_keys=list(keys))


def _only(out: dict, key: str) -> dict:
    return next(q for g in out["groups"] for q in g["questions"] if q["template_key"] == key)


def _correct(q: dict) -> str:
    return next(c["text"] for c in q["choices"] if c["correct"])


def _tables(out: dict) -> dict[str, dict]:
    return {t["caption"]: t for t in out["groups"][0]["stimulus"]["tables"]}


def _generation_table(out: dict) -> dict:
    return next(t for c, t in _tables(out).items() if "in each generation" in c)


def _survival_table(out: dict) -> dict:
    return next(t for c, t in _tables(out).items() if c.startswith("Survival"))


def test_family_is_registered_and_bound_to_biology_1_only():
    from app.services.families.registry import FAMILIES

    fam = FAMILIES["natural-selection-trend"]
    assert fam.version == "1.0.0"
    assert [(b.state, b.course_slug, b.code) for b in fam.bindings] == [("SC", "biology-1", "B-LS4-4")]
    assert all(t.standard_code is None for t in fam.templates)


def test_compare_survival_key_follows_the_displayed_survival_table():
    saw_trap = saw_plain = 0
    for seed in SEEDS:
        out = _set(seed, "compare_survival")
        q = _only(out, "compare_survival")
        table = _survival_table(out)
        assert [c["label"] for c in table["columns"]] == ["Variant", "Started", "Survived"]
        rows = table["rows"]
        assert len(rows) == 2 and all(0 <= r["survived"] <= r["started"] for r in rows)
        rates = {r["variant"]: r["survived"] / r["started"] for r in rows}
        winner = max(rates, key=rates.get)
        assert _correct(q) == f"{winner} had the higher survival rate."
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4
        assert "The two variants had the same survival rate." in texts
        assert any("cannot be compared" in t for t in texts)
        more_survivors = max(rows, key=lambda r: r["survived"])["variant"]
        if more_survivors == winner:
            saw_plain += 1
        else:
            saw_trap += 1
    assert saw_trap >= 60 and saw_plain >= 60  # counts alone mislead in about half of the items


def test_compare_survival_shows_only_the_survival_table():
    out = _set("only-survival", "compare_survival")
    stim = out["groups"][0]["stimulus"]
    assert len(stim["tables"]) == 1 and stim["charts"] == []


def _noun_in(stem: str, out: dict) -> str:
    labels = [c["label"] for c in _generation_table(out)["columns"][1:]]
    # "resistant bacteria" also appears inside "non-resistant bacteria", so take the longest label that matches
    return max((label for label in labels if label.lower() in stem), key=len)


def test_trait_trend_key_follows_the_displayed_counts():
    for seed in SEEDS:
        out = _set(seed, "trait_trend")
        q = _only(out, "trait_trend")
        label = _noun_in(q["stem"], out)
        column = {c["label"]: c["key"] for c in _generation_table(out)["columns"]}[label]
        end = int(re.search(r"to generation (\d+)", q["stem"]).group(1))
        rows = _generation_table(out)["rows"]
        direction = "increased" if rows[end][column] > rows[0][column] else "decreased"
        assert _correct(q) == f"The fraction of the population that is {label.lower()} {direction}."
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4
        assert abs(rows[end][column] - rows[0][column]) >= 25


def test_trait_trend_includes_the_table_and_a_chart_that_points_at_it():
    stim = _set("only-trend", "trait_trend")["groups"][0]["stimulus"]
    assert len(stim["tables"]) == 1 and len(stim["charts"]) == 1
    chart = stim["charts"][0]
    assert chart["type"] == "line" and chart["table_index"] == 0 and len(chart["series"]) == 2
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q`
Expected: the new tests FAIL (`AttributeError: ... NaturalSelectionTrend`); the five from Task 1 still pass.

- [ ] **Step 3: Append the class**

In `natural_selection.py` replace the import line `from app.services.engine.core import GenerationError, Rng` with:

```python
from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily
```

and append:

```python
# ---- family ------------------------------------------------------------------------------------

_GENERATION_KEYS = {
    "trait_trend",
    "effect_of_change",
    "explain_adaptation",
    "predict_new_change",
    "explain_with_data",
}


def _case(params: dict[str, Any]) -> dict[str, Any]:
    return CASES[params["case"]]


def _other(variant: str) -> str:
    return "b" if variant == "a" else "a"


def _pct(survived: int, started: int) -> str:
    return f"{round(100 * survived / started)}%"


class NaturalSelectionTrend(QuestionFamily):
    key = "natural-selection-trend"
    version = "1.0.0"
    title = "Natural selection and adaptation"
    description = (
        "Use counts of two heritable variants across generations, and an environmental change, to compare survival "
        "rates, read trends in the fraction of a population with a trait, explain how natural selection leads to "
        "adaptation, and predict the direction of change when the environment reverses."
    )
    stimulus_kind = "natural_selection_trend"
    bindings = (Binding("SC", "biology-1", "B-LS4-4"),)
    templates = (
        TemplateSpec("compare_survival", "Compare survival rates", 1, "multiple_choice", "evidence", 1),
        TemplateSpec("trait_trend", "Read a trend in a trait", 2, "multiple_choice", "reasoning", 1),
    )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        keys = set(template_keys)
        case = _case(params)
        first, second = case["envs"][params["env_first"]], case["envs"][params["env_second"]]
        a, b = case["variants"]["a"], case["variants"]["b"]
        intro = f"{case['intro']} {first['is']}"
        tables: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        if keys & _GENERATION_KEYS:
            intro += f" The environment changed after generation {params['l1']}. {second['became']}"
            tables.append(
                {
                    "caption": f"{case['organism'].capitalize()} in each generation, out of {SAMPLE} sampled",
                    "columns": [
                        {"key": "generation", "label": "Generation"},
                        {"key": "a", "label": a["label"]},
                        {"key": "b", "label": b["label"]},
                    ],
                    "rows": params["rows"],
                }
            )
            charts.append(
                {
                    "type": "line",
                    "title": f"{case['organism'].capitalize()} with each {case['trait']} over the generations",
                    "x": {"key": "generation", "label": "Generation"},
                    "y": {"label": f"Individuals out of {SAMPLE}", "min": 0},
                    "series": [{"key": "a", "label": a["label"]}, {"key": "b", "label": b["label"]}],
                    "table_index": 0,
                }
            )
        if "compare_survival" in keys:
            tables.append(
                {
                    "caption": "Survival through one season in the first environment",
                    "columns": [
                        {"key": "variant", "label": "Variant"},
                        {"key": "started", "label": "Started"},
                        {"key": "survived", "label": "Survived"},
                    ],
                    "rows": [
                        {"variant": case["variants"][r["variant"]]["label"], "started": r["started"], "survived": r["survived"]}
                        for r in params["survival"]["rows"]
                    ],
                }
            )
        return {"title": "Natural selection in a population", "intro": intro, "sections": [], "tables": tables, "charts": charts}

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_compare_survival(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        rows = {r["variant"]: r for r in params["survival"]["rows"]}
        label = {v: case["variants"][v]["label"] for v in ("a", "b")}
        rate = {v: rows[v]["survived"] / rows[v]["started"] for v in rows}
        facts = " ".join(
            f"{label[v]}: {rows[v]['survived']} of {rows[v]['started']} survived ({_pct(rows[v]['survived'], rows[v]['started'])})."
            for v in ("a", "b")
        )
        winner = "a" if rate["a"] > rate["b"] else "b"
        texts = {
            "a": f"{label['a']} had the higher survival rate.",
            "b": f"{label['b']} had the higher survival rate.",
            "same": "The two variants had the same survival rate.",
            "incomparable": "The survival rates cannot be compared, because the groups started with different numbers.",
        }
        why = {
            winner: f"Correct: {facts} A survival rate is the fraction that survived, so {label[winner]} had the higher rate.",
            _other(winner): f"Not supported: {facts} The higher rate belongs to {label[winner]}.",
            "same": f"Not supported: {facts} The two rates are not the same.",
            "incomparable": (
                "Not supported: a survival rate (the number that survived out of the number that started) can be "
                f"compared even when the groups started with different numbers. {facts}"
            ),
        }
        choices = [DraftChoice(texts[name], name == winner, why[name]) for name in texts]
        return DraftQuestion(
            stem=(
                "Scientists counted how many individuals of each variant started a season and how many survived. "
                f"{case['envs'][params['env_first']]['is']} Which statement is supported by the survival table?"
            ),
            answer=texts[winner],
            explanation=f"{facts} {label[winner]} had the higher survival rate.",
            choices=choices,
        )

    def _q_trait_trend(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        variant = rng.choice(["a", "b"])
        noun = case["variants"][variant]["noun"]
        l1 = params["l1"]
        start, end = params["rows"][0][variant], params["rows"][l1][variant]
        direction = "increased" if end > start else "decreased"
        texts = {
            "increased": f"The fraction of the population that is {noun} increased.",
            "decreased": f"The fraction of the population that is {noun} decreased.",
            "same": f"The fraction of the population that is {noun} stayed about the same.",
            "unknown": f"The change in the fraction of {noun} cannot be determined from the table.",
        }
        facts = f"{noun.capitalize()} went from {start} out of {SAMPLE} in generation 0 to {end} out of {SAMPLE} in generation {l1}."
        choices = [
            DraftChoice(texts[name], name == direction, f"Correct: {facts}" if name == direction else f"Not supported: {facts}")
            for name in texts
        ]
        return DraftQuestion(
            stem=(
                f"Look at the generation table. How did the fraction of the population that is {noun} change from "
                f"generation 0 to generation {l1}?"
            ),
            answer=texts[direction],
            explanation=f"{facts} The fraction {direction}.",
            choices=choices,
        )
```

- [ ] **Step 4: Register the family and add the golden placeholder**

In `registry.py` add `from app.services.families.natural_selection import NaturalSelectionTrend` (after the `mutation_effects` import) and `NaturalSelectionTrend(),` as the last entry of the `FAMILIES` tuple. In `backend/tests/test_engine.py` add `"natural-selection-trend": None,` after the `"mutation-effects"` entry in `GOLDEN`.

- [ ] **Step 5: Run the tests and format**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py tests/test_engine.py -q -k "natural or citations or same_seed or hash or items_well_formed"; .venv/bin/ruff format app/services/families/natural_selection.py app/services/families/registry.py tests/test_natural_selection.py tests/test_engine.py; .venv/bin/ruff check app tests`
Expected: pass (the golden test for the new family skips until Task 5; the engine matrix now includes the family).

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: survival and trend items for the natural selection family"
```

---

### Task 3: Effect of the change and the adaptation explanation

**Files:**
- Modify: `backend/app/services/families/natural_selection.py`
- Modify: `backend/tests/test_natural_selection.py` (append)

**Interfaces:**
- Produces: templates `effect_of_change` (DOK 2, `evidence[0]`) and `explain_adaptation` (DOK 2, `reasoning[2]`); module constants `ADAPTATION_KEY`, `ADAPTATION_NEED`, `ADAPTATION_ENV`, `ADAPTATION_ALWAYS`, `ADAPTATION_WHY`.

- [ ] **Step 1: Write the failing tests**

Append to `test_natural_selection.py`:

```python
# ---- items: effect_of_change, explain_adaptation -------------------------------------------


def test_effect_of_change_key_follows_the_displayed_counts():
    for seed in SEEDS:
        out = _set(seed, "effect_of_change")
        q = _only(out, "effect_of_change")
        numbers = [int(x) for x in re.findall(r"generation (\d+)", q["stem"])]
        l1, last = numbers[0], numbers[-1]  # the stem names the change generation twice, then the last generation
        table = _generation_table(out)
        a_label, b_label = (c["label"] for c in table["columns"][1:])
        a_up = table["rows"][last]["a"] > table["rows"][l1]["a"]
        winner = a_label if a_up else b_label
        assert _correct(q) == f"{winner} became more common."
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4
        named = [t for t in texts if t.endswith("became more common.") and not t.startswith(("Neither", "Both"))]
        assert len(named) == 2 and "Both variants became more common." in texts


def test_explain_adaptation_key_names_the_whole_chain_and_distinguishes_need_from_selection():
    chain = ("heritable", "survived", "reproduced", "passed", "more common")
    for seed in SEEDS[:60]:
        out = _set(seed, "explain_adaptation")
        q = _only(out, "explain_adaptation")
        texts = [c["text"] for c in q["choices"]]
        chain_texts = [t for t in texts if all(word in t for word in chain)]
        assert chain_texts == [_correct(q)]  # exactly one choice carries the full chain
        assert [t for t in texts if "need" in t] != [_correct(q)]
        assert sum("needed" in t for t in texts) == 1  # only the needs-based distractor
        assert "need" not in _correct(q) and "need" not in q["stem"]
        assert "need" not in out["groups"][0]["stimulus"]["intro"]
        needy = next(c for c in q["choices"] if "needed" in c["text"])
        assert "do not change their traits because they need to" in needy["rationale"]
        labels = [c["label"].lower() for c in _generation_table(out)["columns"][1:]]
        assert not any(label in t.lower() for label in labels for t in texts)  # no variant is named
        assert len(_correct(q)) <= max(len(c["text"]) for c in q["choices"] if not c["correct"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q -k "effect_of_change or explain_adaptation"`
Expected: FAIL (template not found).

- [ ] **Step 3: Implement**

Insert the constants immediately before the `# ---- family` comment (after `draw_scenario`):

```python
ADAPTATION_KEY = (
    "The population already had heritable variation in the trait. Individuals with one variant survived and reproduced "
    "more in the new environment and passed the trait to their offspring, so that trait became more common over the "
    "generations."
)
ADAPTATION_NEED = (
    "Individuals in the population changed their trait because they needed it to survive in the new environment, and "
    "those changes were then passed on to their offspring, so the trait became more common in the whole population over "
    "the generations."
)
ADAPTATION_ENV = (
    "The new environment changed the offspring directly, so every offspring was born with one variant whatever traits "
    "its parents had, and in this way that variant became more common in the whole population over the generations."
)
ADAPTATION_ALWAYS = (
    "One variant is better than the other in every environment, so individuals with it always survive and reproduce "
    "more in any environment, and it becomes more common over the generations no matter what the environment is like."
)
ADAPTATION_WHY = {
    "key": (
        "Correct: it names the whole chain. The population had heritable variation, individuals with one variant "
        "survived and reproduced more, they passed the trait to their offspring, and the trait became more common over "
        "the generations."
    ),
    "need": (
        "Individuals do not change their traits because they need to. The population changed because variants that "
        "already existed survived and reproduced differently."
    ),
    "env": (
        "The environment does not change an offspring's inherited traits directly. It affects which individuals "
        "survive and reproduce."
    ),
    "always": (
        "Which variant survives better depends on the environment. The table shows each variant increasing in a "
        "different environment."
    ),
}
```

Extend `templates` in the class with:

```python
        TemplateSpec("effect_of_change", "Effect of an environmental change", 2, "multiple_choice", "evidence", 0),
        TemplateSpec("explain_adaptation", "Explain adaptation", 2, "multiple_choice", "reasoning", 2),
```

and append the methods to the class:

```python
def _q_effect_of_change(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        l1, last = params["l1"], len(params["rows"]) - 1
        label = {v: case["variants"][v]["label"] for v in ("a", "b")}
        noun = {v: case["variants"][v]["noun"] for v in ("a", "b")}
        winner = params["second_favors"]
        loser = _other(winner)
        rows = params["rows"]
        texts = {
            "a": f"{label['a']} became more common.",
            "b": f"{label['b']} became more common.",
            "neither": "Neither variant became more common; the fractions did not change.",
            "both": "Both variants became more common.",
        }
        won = f"{noun[winner].capitalize()} went from {rows[l1][winner]} out of {SAMPLE} in generation {l1} to {rows[last][winner]} out of {SAMPLE} in generation {last}."
        lost = f"{noun[loser].capitalize()} went from {rows[l1][loser]} out of {SAMPLE} in generation {l1} to {rows[last][loser]} out of {SAMPLE} in generation {last}, a decrease."
        why = {
            winner: f"Correct: {won}",
            loser: f"Not supported: {lost}",
            "neither": f"Not supported: the table shows the fractions changed. {won}",
            "both": f"Not supported: every generation has {SAMPLE} individuals, so when one variant becomes more common the other becomes less common. {won}",
        }
        choices = [DraftChoice(texts[name], name == winner, why[name]) for name in texts]
        return DraftQuestion(
            stem=(
                f"The environment changed after generation {l1}. Compare generation {l1} with generation {last}. Which "
                "variant became more common after the change?"
            ),
            answer=texts[winner],
            explanation=f"{won} {lost}",
            choices=choices,
        )

    def _q_explain_adaptation(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        choices = [
            DraftChoice(ADAPTATION_KEY, True, ADAPTATION_WHY["key"]),
            DraftChoice(ADAPTATION_NEED, False, ADAPTATION_WHY["need"]),
            DraftChoice(ADAPTATION_ENV, False, ADAPTATION_WHY["env"]),
            DraftChoice(ADAPTATION_ALWAYS, False, ADAPTATION_WHY["always"]),
        ]
        return DraftQuestion(
            stem=(
                "After the environment changed, one of the two variants became more common in the population. "
                "Which statement best explains why?"
            ),
            answer=ADAPTATION_KEY,
            explanation=ADAPTATION_WHY["key"],
            choices=choices,
        )
```

- [ ] **Step 4: Run tests and format**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q && .venv/bin/ruff format app/services/families/natural_selection.py tests/test_natural_selection.py && .venv/bin/ruff check app tests`
Expected: all pass. If `explain_adaptation`'s length assertion fails after a wording change, adjust the distractor wording, not the test: the key must not be the unique longest choice.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: effect and adaptation items for the natural selection family"
```

---

### Task 4: Predict a new change and the data-based explanation

**Files:**
- Modify: `backend/app/services/families/natural_selection.py`
- Modify: `backend/tests/test_natural_selection.py` (append)

**Interfaces:**
- Produces: templates `predict_new_change` (DOK 2, `reasoning[3]`) and `explain_with_data` (DOK 3, constructed response, `reasoning[0]`).

- [ ] **Step 1: Write the failing tests**

Append:

```python
# ---- items: predict_new_change, explain_with_data -------------------------------------------


def test_predict_new_change_states_the_reversal_and_asks_only_for_direction():
    for seed in SEEDS:
        out = _set(seed, "predict_new_change")
        q = _only(out, "predict_new_change")
        params = out["groups"][0]["parameters"]
        assert "goes back to its earlier conditions" in q["stem"]
        assert "All other conditions stay the same." in q["stem"]
        assert ns.CASES[params["case"]]["envs"][params["env_first"]]["returns"] in q["stem"]
        blob = q["stem"] + " " + " ".join(c["text"] for c in q["choices"])
        assert not any(ch.isdigit() for ch in blob) and "%" not in blob and "generation" not in blob.lower()
        texts = [c["text"] for c in q["choices"]]
        assert len(set(texts)) == len(texts) == 4
        assert _correct(q) == "The variant that was more common before the change will tend to become more common again."
        # the key is true: the variant ahead when the change happened is the one the first environment favours
        row = params["rows"][params["l1"]]
        leader = "a" if row["a"] > row["b"] else "b"
        assert leader == FAVORS[params["case"]][params["env_first"]]


def test_explain_with_data_is_constructed_response_with_a_computed_model_answer():
    for seed in SEEDS[:80]:
        out = _set(seed, "explain_with_data")
        q = _only(out, "explain_with_data")
        params = out["groups"][0]["parameters"]
        assert q["question_type"] == "constructed_response" and q["choices"] == [] and q["dok"] == 3
        winner = FAVORS[params["case"]][params["env_second"]]
        loser = "b" if winner == "a" else "a"
        variants = ns.CASES[params["case"]]["variants"]
        l1, last = params["l1"], len(params["rows"]) - 1
        answer = q["answer"]
        assert variants[winner]["noun"] in answer
        assert f"from {params['rows'][l1][winner]} out of 100 in generation {l1}" in answer
        assert f"to {params['rows'][last][winner]} out of 100 in generation {last}" in answer
        for phrase in ("heritable variation", "survived and reproduced more", "did not change their traits because they needed to"):
            assert phrase in answer.lower()
        assert variants[winner]["noun"] not in q["stem"] and variants[loser]["noun"] not in q["stem"]  # no leak
        assert "not as individuals changing because they need to" in q["stem"]
        assert q["explanation"].count("(1)") == 1 and "(4)" in q["explanation"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q -k "predict or explain_with_data"`
Expected: FAIL (template not found).

- [ ] **Step 3: Implement**

Extend `templates` with:

```python
        TemplateSpec("predict_new_change", "Predict a new change", 2, "multiple_choice", "reasoning", 3),
        TemplateSpec(
            "explain_with_data", "Explain natural selection with data", 3, "constructed_response", "reasoning", 0
        ),
```

and append the methods:

```python
def _q_predict_new_change(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        first = case["envs"][params["env_first"]]
        texts = {
            "key": "The variant that was more common before the change will tend to become more common again.",
            "keeps": "The variant that is now more common will keep increasing, because it has already been selected.",
            "fixed": "Both variants will stay at the same fractions, because each individual's trait is fixed and nothing can change.",
            "uniform": "Every individual will end up with the same trait, because the population can no longer vary.",
        }
        why = {
            "key": (
                "Correct: the earlier environment favored the variant that was more common before the change. When "
                "those conditions return, that variant is again more likely to survive and reproduce, so its fraction "
                "tends to rise."
            ),
            "keeps": "Which variant increases depends on the environment. The conditions that favored it have ended.",
            "fixed": "The table shows the fractions changing from generation to generation, so the population does change.",
            "uniform": "Both variants are still in the population, and individuals with each can still reproduce.",
        }
        choices = [DraftChoice(texts[name], name == "key", why[name]) for name in texts]
        return DraftQuestion(
            stem=(
                f"Later, the environment goes back to its earlier conditions. {first['returns']} All other conditions "
                "stay the same. Which prediction is best supported by the data?"
            ),
            answer=texts["key"],
            explanation=why["key"],
            choices=choices,
        )

    def _q_explain_with_data(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        l1, last = params["l1"], len(params["rows"]) - 1
        rows = params["rows"]
        winner = params["second_favors"]
        loser = _other(winner)
        noun_win, noun_lose = case["variants"][winner]["noun"], case["variants"][loser]["noun"]
        second = case["envs"][params["env_second"]]
        answer = (
            f"Claim: after the environment changed, {noun_win} became more common, going from {rows[l1][winner]} out of "
            f"{SAMPLE} in generation {l1} to {rows[last][winner]} out of {SAMPLE} in generation {last}. "
            f"Heritable variation: the population already had both {noun_win} and {noun_lose}, and parents pass their "
            f"{case['trait']} to their offspring. "
            f"Survival and reproduction: {second['is']} In this environment, {noun_win} survived and reproduced more "
            f"than {noun_lose}. "
            "Over the generations: because the trait is inherited, each new generation had a larger fraction with the "
            "trait. The individuals did not change their traits because they needed to; the population changed because "
            "the inherited trait became more common."
        )
        return DraftQuestion(
            stem=(
                "Use the data to explain how the population changed after the environment changed. Name the variant that "
                "became more common, and explain the change in the population across the generations, not as "
                "individuals changing because they need to."
            ),
            answer=answer,
            explanation=(
                "Scoring guide (4 points): (1) a claim that names the variant that became more common and uses the "
                "data; (2) the population already had heritable variation, and parents pass the trait to offspring; "
                "(3) in the new environment individuals with that variant survived and reproduced more; (4) because "
                "the trait is inherited, it became more common over the generations, and individuals did not change "
                "because they needed to."
            ),
        )
```

- [ ] **Step 4: Run tests and format**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q && .venv/bin/ruff format app/services/families/natural_selection.py tests/test_natural_selection.py && .venv/bin/ruff check app tests`
Expected: all pass (the module and tests now match the sandbox run: 14 tests before Task 5's guards, 20 after).

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: prediction and data-based explanation items for the natural selection family"
```

---

### Task 5: Family-wide guards, golden digest, API tests, docs, full suite

**Files:**
- Modify: `backend/tests/test_natural_selection.py`, `backend/tests/test_engine.py`, `backend/tests/test_api.py`
- Modify: `HANDOFF.md`, `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`

- [ ] **Step 1: Write the family-wide guards**

Add `from collections import Counter` to the imports at the top of `test_natural_selection.py` (after `import re`), then append:

```python
# ---- family-wide guards ----------------------------------------------------------------------

BANNED_ALWAYS = (
    "allele frequency",
    "gene frequency",
    "genetic drift",
    "gene flow",
    "hardy",
    "speciation",
    "infection",
    "disease",
    "patient",
    "treatment",
    "medicine",
    "drug",
    "hospital",
    "human",
    "antibiotic",
)
ALL_KEYS = [t.key for t in ns.NaturalSelectionTrend.templates]
MC_KEYS = [t.key for t in ns.NaturalSelectionTrend.templates if t.question_type == "multiple_choice"]


def _full(seed: str) -> dict:
    return generate_set(ns.NaturalSelectionTrend(), seed, len(ALL_KEYS))


def _all_text(out: dict) -> list[str]:
    texts = []
    for g in out["groups"]:
        texts += [g["stimulus"]["title"], g["stimulus"]["intro"]]
        for t in g["stimulus"]["tables"]:
            texts += [t["caption"]] + [c["label"] for c in t["columns"]]
        for q in g["questions"]:
            texts += [q["stem"], q["answer"], q["explanation"]]
            texts += [c["text"] + " " + c["rationale"] for c in q["choices"]]
    return texts


def test_templates_and_doks():
    assert {t.key: t.dok for t in ns.NaturalSelectionTrend.templates} == {
        "compare_survival": 1,
        "trait_trend": 2,
        "effect_of_change": 2,
        "explain_adaptation": 2,
        "predict_new_change": 2,
        "explain_with_data": 3,
    }


def test_vocabulary_and_health_guard():
    for seed in SEEDS:
        blob = " ".join(_all_text(_full(seed))).lower()
        for word in BANNED_ALWAYS:
            assert word not in blob, (seed, word)


def test_every_displayed_row_total_and_survival_count_is_valid_in_the_rendered_stimulus():
    for seed in SEEDS:
        out = _full(seed)
        for table in out["groups"][0]["stimulus"]["tables"]:
            for row in table["rows"]:
                if "survived" in row:
                    assert 0 <= row["survived"] <= row["started"]
                else:
                    assert row["a"] + row["b"] == 100


def test_the_correct_answer_position_varies_for_every_multiple_choice_template():
    for key in MC_KEYS:
        positions = Counter()
        for seed in SEEDS:
            positions[_only(_set(seed, key), key)["answer"][0]] += 1
        assert set(positions) == {"A", "B", "C", "D"}, (key, positions)
        assert max(positions.values()) <= 0.40 * len(SEEDS), (key, positions)


def test_no_item_leaks_another_items_key_in_the_same_set():
    for seed in SEEDS:
        out = _full(seed)
        group = out["groups"][0]
        qs = {q["template_key"]: q for q in group["questions"]}
        for key, q in qs.items():
            visible = q["stem"] + " " + group["stimulus"]["intro"]
            for other_key, other in qs.items():
                if other_key != key and other["choices"]:
                    assert _correct(other) not in visible, (seed, key, other_key)
        # the explanation item names no variant, so it does not hand over the effect_of_change key
        for c in qs["explain_adaptation"]["choices"]:
            assert not any(v["label"].lower() in c["text"].lower() for v in ns.CASES[group["parameters"]["case"]]["variants"].values())


def test_a_full_set_has_the_generation_table_chart_and_survival_table_only_when_needed():
    out = _full("full")
    stim = out["groups"][0]["stimulus"]
    captions = [t["caption"] for t in stim["tables"]]
    assert any("in each generation" in c for c in captions) and any(c.startswith("Survival") for c in captions)
    assert len(stim["charts"]) == 1 and stim["charts"][0]["table_index"] == 0
    only_cr = _set("cr-only", "explain_with_data")["groups"][0]["stimulus"]
    assert len(only_cr["tables"]) == 1 and "in each generation" in only_cr["tables"][0]["caption"]
```

- [ ] **Step 2: Run, then prove the guards bite**

Run: `.venv/bin/python -m pytest tests/test_natural_selection.py -q`
Expected: pass. Because the guards pass on the first run, prove they can fail. Back up the module (`cp app/services/families/natural_selection.py /tmp/ns_backup.py`), apply each mutation below, confirm the named test fails, and restore from the backup after each:

1. In the bacteria intro, change `fictional chemical that stops the growth` to `fictional drug that stops the growth` and run `-k vocabulary`; `test_vocabulary_and_health_guard` must fail.
2. Change `ADAPTATION_KEY`'s first sentence to `The individuals needed a new trait to survive.` and run `-k explain_adaptation`; the chain test must fail.
3. In `draw_scenario`, change `"b": SAMPLE - a` to `"b": SAMPLE - a - (1 if generation == 2 else 0)` and run `-k "totals or valid_in_the_rendered"`; both row-total tests must fail.
4. In `_q_predict_new_change`, replace the question sentence `Which prediction is best supported by the data?` with `Predict the percentage after 3 generations.` and run `-k predict`; the direction-only test must fail.

Record the four outcomes in the ledger. Rerun the whole file after restoring; it must pass.

- [ ] **Step 3: Pin the golden digest**

Run `.venv/bin/python -m pytest tests/test_engine.py -q -k "golden and natural" -rs`, copy the printed digest, replace `None` in `"natural-selection-trend": None,` with it (a quoted string), and rerun until it passes.

- [ ] **Step 4: API tests (throwaway Postgres)**

Start `docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine` (check `docker ps` first). In `test_api.py`:

1. Add `("biology-1", "B-LS4-4", "natural-selection-trend"),` after the `("biology-1", "B-LS3-2", "mutation-effects"),` line in the `test_preview_is_reproducible` parametrization.
2. After the `assert denied_4.status_code == 422` line in the EOCEP test, add:

```python
    bio_1_ns = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS4-4")
    denied_5 = client.post(
        "/api/generate/preview",
        json={
            "standard_id": bio_1_ns["id"],
            "family_key": "natural-selection-trend",
            "quantity": 1,
            "generation_mode": "eocep",
        },
    )
    assert denied_5.status_code == 422
```

3. In `test_family_must_match_exact_standard`, add after the `mutation-effects` Biology 2 lines:

```python
    _, body = _generate(client, "biology-2", "B-LS4-4", "natural-selection-trend")
    assert client.post("/api/generate/preview", json=body).status_code == 422
```

(If Biology 2 has no `B-LS4-4`, use `_generate(client, "biology-2", "B-LS4-3", "natural-selection-trend")` instead; the request must be rejected either way.)

4. In `test_standards_browse_and_detail`, insert `("biology-1", "B-LS4-4"),` after `("biology-1", "B-LS3-3"),` in the expected `with_family` list.

Run: `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest tests/test_api.py tests/test_coverage_api.py -q`
Expected: pass.

- [ ] **Step 5: Docs**

- `HANDOFF.md`: add a row to the "Implemented families" table after `mutation-effects`: `| \`natural-selection-trend\` | Biology 1 B-LS4-4 | 1.0.0 (built on branch \`feat/natural-selection\`, not yet merged or deployed) | Six fictional cases (beetles, a lab bacterium, finches, marsh hares, minnows, desert shrubs): compare survival rates (with trap cases), read a trait trend across generations of 100 sampled individuals, the effect of an environmental change, explain adaptation as population-level change (not individuals changing because they need to), predict the direction of a reversal, and a DOK 3 data-based explanation. Classroom-only; no allele-frequency calculations. |` and update "Last updated".
- `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`: "Eight families are live" becomes "Nine"; add `| \`natural-selection-trend\` | Biology 1 B-LS4-4 (built 2026-10-03; Biology 1 only, classroom-only) |` after the `mutation-effects` table row; "That is 7 standards with a family" becomes 8; in the Tier B paragraph, after "B-LS4-4 (adaptation, flagged as a good candidate: gene-frequency change over generations)" append " **(built as `natural-selection-trend`; Biology 2 B-LS4-3 still needs its own templates)**".

- [ ] **Step 6: Full suite and cleanup**

Run (background, about 2.5 minutes): `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q` and `.venv/bin/ruff check app tests`.
Expected: zero failures, zero skipped. Stop the test Postgres container you started.

- [ ] **Step 7: Commit**

```bash
git add -A backend HANDOFF.md docs/superpowers/plans/2026-09-29-coverage-roadmap.md
git commit -m "test: family-wide guards, golden digest, and docs for the B-LS4-4 family"
```

---

## Self-review

- **Spec coverage:** six cases and independent per-environment rates (Task 1); exact 100-total rows, bounds, steady selection, reversal, survival validity and traps (Tasks 1, 5 guards); six templates with citations and the item contracts (Tasks 2 to 4); direction-only and "other conditions stay the same" (Task 4); population-level chain and "need" restrictions (Tasks 3, 4, 5); fictional resistance and health vocabulary guard (Task 5); deterministic shuffle and position variation (Task 5); leak test (Task 5); golden, EOCEP and Biology 2 rejection, docs (Task 5); no migration, no frontend.
- **Placeholders:** none. Every code block was executed in the sandbox.
- **Type consistency:** scenario keys (`case`, `env_first`, `env_second`, `first_favors`, `second_favors`, `l1`, `l2`, `rows`, `survival`) are read by every item and by the tests' `group["parameters"]`; `ADAPTATION_*` constants are defined in Task 3 before the item that uses them; the class name `NaturalSelectionTrend` is the registered name.
