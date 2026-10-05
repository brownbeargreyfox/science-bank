# B-LS4-3 `trait-distribution-shifts` 1.1.0 (Redo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Biology 2 B-LS4-3 family after its first build (1.0.0) was withdrawn, so that every multiple-choice item has exactly one true choice evaluated against the displayed data, no item answers another, and the stimulus tells the truth.

**Architecture:** One new module builds each multiple-choice item from claims whose truth is computed from the stored scenario and requires exactly one true claim. The scenario also stores the pooled-percentage question so no sibling item can repeat or display its answer. A new independent test file recomputes truth from the displayed tables and the choice text with its own half-up arithmetic. The family is registered like the others; no engine, frontend, schema or migration change.

**Tech Stack:** Python 3.12, FastAPI, pytest on Postgres.

**Spec:** `docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md` (approved by Brandon 2026-10-05; commits `45d8f69`, `82b1724`, `58d2b33`). Read it first. Task 3 corrects four details the build settled (the pooled item's wrong-answer pool and its scenario-level choice, the analyze choice wording, the support evidence wording, and the roadmap).

## Global Constraints

- Brandon approves each spec, plan, merge, deploy and push himself. This plan stops after the branch is built, tested and reviewed. **Do not merge, deploy or push.** Nothing reaches `main` or production without a reviewed branch and his explicit yes for that change.
- Work only in the worktree `/home/brandon/apps/science-bank/.claude/worktrees/revert-bls4-3` on branch `feat/bls4-3-redo`. Do not touch any other worktree, branch or running container. Test database: port 54332 (container `sb-testdb`); stop it when done.
- No LLM-written live questions. Every item is deterministic code from a seed; every key is computed from values the student sees.
- The family key is `trait-distribution-shifts`, version **1.1.0** (1.0.0 was live; the version feeds every sub-seed). It binds only `SC / biology-2 / B-LS4-3`. EOCEP stays Biology 1 only and must still be rejected for it.
- Do not modify `natural_selection.py`, `mutation_effects.py`, standards JSON, the database schema, or frontend code. No migration. `HANDOFF.md` changes only as Task 4 says.
- Boundary: basic proportion arithmetic only; no allele or gene frequency, Hardy-Weinberg, chi-square, drift, gene flow, speciation, or health or human contexts.
- Percentages round **half up** (`Decimal`); never Python's `round()` for a displayed or keyed percentage.
- Run `ruff format` only on files you touched; `ruff check app tests` stays clean. Full backend suite: zero failures, zero skips (429 tests before this work, 455 after).
- Wording is product: grammatical agreement in every case, no mastery or verdict language.

## Review Focus

Failure modes the spec implies but a happy-path test could miss, most likely first:

1. **A distractor that is true for some draw** (the original C1 and C2 defect). The exactly-one tests parse each choice and evaluate it against the displayed table. Mutations M1c and M8 in Task 2 reproduce the two original forms.
2. **One item answering another** in a default six-item set. The leak test covers the verbatim key and the pooled key, and the support item is checked to state no rate, percentage or winner. A reviewer should still read a few full sets.
3. **The support item's choices cue the key** because each distractor differs from the key in one clause. The key is never the unique longest or shortest and all four lengths are within 20%, but the "centre of the four" pattern is a cue a reviewer should judge.
4. **A teacher-visible generation error.** The wide-seed test generates 250 seeds at quantity 40; the build was also stressed over 2,000 seeds at quantity 40 (66,628 multiple-choice items, none with other than one correct choice).
5. **EOCEP or Biology 1 reaching this family.** Task 1 adds a Biology 2 EOCEP rejection test and a Biology 1 B-LS4-4 binding-mismatch test.

---

## File map

| File | Responsibility |
|---|---|
| `backend/app/services/families/trait_distribution_shifts.py` (new) | Case bank, data draws, claims, stimulus and the six templates |
| `backend/tests/test_trait_distribution_shifts.py` (new) | Independent checks of truth, leaks, rounding, wording and scope |
| `backend/app/services/families/registry.py` | Registers the family |
| `backend/tests/test_engine.py` | Maps `biology-2.json` for the citation test; pins the golden digest |
| `backend/tests/test_api.py` | Browse row, preview case, binding mismatch, Biology 2 EOCEP rejection |
| `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`, the spec, `HANDOFF.md` | Records |

---

### Task 0: Prepare

**Files:** none.

- [ ] **Step 1: Confirm the checkout**

```bash
cd /home/brandon/apps/science-bank/.claude/worktrees/revert-bls4-3
git branch --show-current            # Expected: feat/bls4-3-redo
git status --short                    # Expected: no output
git log --oneline -4                  # Expected: 58d2b33, 82b1724, 45d8f69, 53bf9cd (merge of PR 10) on top
ls backend/app/services/families | grep -c trait_distribution   # Expected: 0 (the withdrawn module is not on this branch)
```

- [ ] **Step 2: Start the throwaway test database and take a baseline**

```bash
docker ps --format '{{.Names}}' | grep -x sb-testdb || docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
sleep 6
cd backend && TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test \
  /home/brandon/apps/science-bank/backend/.venv/bin/python -m pytest tests/test_engine.py -q
```

Expected: all pass on a clean tree. Every `pytest` command below runs from `backend/` with that `TEST_DATABASE_URL` and `/home/brandon/apps/science-bank/backend/.venv/bin/python`; every `git apply` runs from the repository root.

---

### Task 1: The tests first

**Files:**
- Create: `backend/tests/test_trait_distribution_shifts.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `generate_set(family, seed, quantity, ...)` and `FAMILIES` from `app.services.families.registry`.
- Produces: the contract Task 2 must meet (family key, version `1.1.0`, six templates in a fixed order with DOKs 1, 1, 2, 2, 2, 3, observable citations, table and chart shapes, item wording forms).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_trait_distribution_shifts.py` with exactly this content. Everything it asserts is recomputed from the displayed tables and the choice text with ground truth typed in the file (a `half_up` helper and `Fraction`s); it imports nothing from the module under test except `generate_set` and the registry.

```python
"""Independent checks for trait-distribution-shifts (Biology 2, B-LS4-3).

Every truth value below is recomputed from the DISPLAYED tables and the choice text with ground truth typed here
(half-up percentages, fractions); nothing is imported from the module under test except the generator entry points.
"""

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from app.services.engine.family import generate_set
from app.services.families.registry import FAMILIES

FAMILY = FAMILIES["trait-distribution-shifts"]
SEEDS = [f"tds-{i}" for i in range(200)]
CASE_TRAIT_TYPES = {"anatomical", "behavioral", "physiological"}


def half_up(count: int, total: int) -> int:
    return int((Decimal(100 * count) / Decimal(total)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def full_set(seed: str):
    """One default six-item set: every template shares one group and one stimulus."""
    out = generate_set(FAMILY, seed, 6)
    assert len(out["groups"]) == 1
    return out["groups"][0]


def tables(group):
    """Distribution rows (counts by variant, percent columns if shown) and fitness rows, from the displayed tables."""
    dist = fit = None
    for table in group["stimulus"]["tables"]:
        labels = {c["key"]: c["label"] for c in table["columns"]}
        if table["caption"].startswith("Trait distribution"):
            variants = {k: v for k, v in labels.items() if k in ("a", "b")}
            dist = {"variants": variants, "rows": table["rows"], "columns": table["columns"]}
        else:
            fit = {row["variant"]: row for row in table["rows"]}
    return dist, fit


def by_label(dist):
    return {label.lower(): key for key, label in dist["variants"].items()}


def items(group):
    return {q["template_key"]: q for q in group["questions"]}


def key_text(question):
    return next(c["text"] for c in question["choices"] if c["correct"])


def all_text(group):
    shown = {k: v for k, v in group.items() if k != "parameters"}
    return json.dumps(shown, ensure_ascii=False)


# ---- the data and the stimulus -------------------------------------------------------------------


def test_family_identity():
    assert FAMILY.version == "1.1.0"
    assert [(b.course_slug, b.code) for b in FAMILY.bindings] == [("biology-2", "B-LS4-3")]
    assert [t.key for t in FAMILY.templates] == [
        "represent_distribution",
        "calculate_proportion",
        "analyze_distribution_shift",
        "interpret_fitness_rate",
        "support_selection_claim",
        "explain_shift_with_data",
    ]
    assert [t.dok for t in FAMILY.templates] == [1, 1, 2, 2, 2, 3]
    assert all(t.standard_code is None for t in FAMILY.templates)


def test_totals_are_distinct_in_range_and_never_100_and_rows_sum():
    for seed in SEEDS:
        dist, _ = tables(full_set(seed))
        totals = [row["total"] for row in dist["rows"]]
        assert len(set(totals)) == 4 and 100 not in totals, seed
        assert all(80 <= t <= 140 and t % 5 == 0 for t in totals), seed
        assert all(row["a"] + row["b"] == row["total"] for row in dist["rows"]), seed


def test_percent_columns_and_chart_points_are_recomputed_half_up():
    for seed in SEEDS:
        group = full_set(seed)
        dist, _ = tables(group)
        pct_columns = [c for c in dist["columns"] if c["key"].endswith("_pct")]
        assert len(pct_columns) == 2, seed
        for row in dist["rows"]:
            for key in ("a", "b"):
                assert row[f"{key}_pct"] == half_up(row[key], row["total"]), (seed, row)
        chart = group["stimulus"]["charts"][0]
        assert chart["table_index"] == 0
        assert {s["key"] for s in chart["series"]} == {"a_pct", "b_pct"}
        assert "rounded to the nearest whole number; a half rounds up" in group["stimulus"]["intro"]


def test_a_set_with_only_the_calculation_item_shows_counts_only():
    for seed in SEEDS[:40]:
        out = generate_set(FAMILY, seed, 1, template_keys=["calculate_proportion"])
        stimulus = out["groups"][0]["stimulus"]
        assert stimulus["charts"] == []
        assert not any(c["key"].endswith("_pct") for c in stimulus["tables"][0]["columns"])
        assert len(stimulus["tables"]) == 1


def test_exact_halves_round_up_never_down():
    seen = 0
    for seed in SEEDS:
        dist, _ = tables(full_set(seed))
        for row in dist["rows"]:
            for key in ("a", "b"):
                exact = Fraction(100 * row[key], row["total"])
                if exact.denominator == 2:  # exactly x.5
                    seen += 1
                    assert row[f"{key}_pct"] == int(exact) + 1, (seed, row)
    assert seen >= 10, seen


def test_cases_trait_types_display_order_and_favored_variant_vary():
    cases, kinds, favored_positions = set(), set(), set()
    for seed in SEEDS:
        group = full_set(seed)
        dist, fit = tables(group)
        text = all_text(group).lower()
        for kind in CASE_TRAIT_TYPES:
            if f" {kind} trait" in json.dumps(items(group)["explain_shift_with_data"]["answer"]).lower():
                kinds.add(kind)
        cases.add(group["stimulus"]["intro"].split(".")[0])
        rates = {v: Fraction(r["survived"], r["started"]) for v, r in fit.items()}
        winner = max(rates, key=rates.get)
        order = [c["label"] for c in dist["columns"] if c["key"] in ("a", "b")]
        favored_positions.add(order.index(winner))
        assert text
    assert len(cases) == 6 and kinds == CASE_TRAIT_TYPES and favored_positions == {0, 1}


# ---- exactly one choice is true, evaluated against the displayed data -------------------------------


def test_represent_distribution_has_exactly_one_true_choice():
    checked = 0
    for seed in SEEDS:
        group = full_set(seed)
        dist, _ = tables(group)
        item = items(group)["represent_distribution"]
        time = int(re.search(r"At sample time (\d+)", item["stem"]).group(1))
        row = next(r for r in dist["rows"] if r["time"] == time)
        labels = by_label(dist)
        truths = []
        for choice in item["choices"]:
            match = re.fullmatch(r"(?:About )?(\d+)% of the sample had (.+)\.", choice["text"])
            if match:
                variant = labels[match.group(2)]
                truths.append(half_up(row[variant], row["total"]) == int(match.group(1)))
            else:
                truths.append(False)  # the "table does not show the total" claim is never true: totals are displayed
        assert sum(truths) == 1, (seed, item["choices"])
        assert truths == [c["correct"] for c in item["choices"]]
        checked += 1
    assert checked == len(SEEDS)


def test_calculate_proportion_is_a_pooled_percentage_with_one_true_choice():
    for seed in SEEDS:
        group = full_set(seed)
        dist, _ = tables(group)
        item = items(group)["calculate_proportion"]
        match = re.search(r"sample times (\d+) and (\d+) combined were (.+)\? Combine", item["stem"])
        t1, t2, noun = int(match.group(1)), int(match.group(2)), match.group(3)
        assert t1 < t2
        variant = by_label(dist)[noun]
        r1, r2 = (next(r for r in dist["rows"] if r["time"] == t) for t in (t1, t2))
        pooled = half_up(r1[variant] + r2[variant], r1["total"] + r2["total"])
        values = [int(c["text"].rstrip("%")) for c in item["choices"]]
        assert len(set(values)) == 4, (seed, values)
        assert [v == pooled for v in values] == [c["correct"] for c in item["choices"]]
        assert values.count(pooled) == 1, (seed, values, pooled)


def test_the_pooled_key_is_never_displayed():
    for seed in SEEDS:
        group = full_set(seed)
        dist, _ = tables(group)
        item = items(group)["calculate_proportion"]
        match = re.search(r"sample times (\d+) and (\d+) combined were (.+)\? Combine", item["stem"])
        variant = by_label(dist)[match.group(3)]
        key = int(key_text(item).rstrip("%"))
        shown = {row[f"{variant}_pct"] for row in dist["rows"]}
        assert key not in shown, (seed, key, shown)
        represent = items(group)["represent_distribution"]
        label = dist["variants"][variant].lower()
        assert f"About {key}% of the sample had {label}." not in [c["text"] for c in represent["choices"]], seed


def test_analyze_distribution_shift_uses_the_trap_window_with_one_true_choice():
    windows = 0
    for seed in SEEDS:
        group = full_set(seed)
        dist, _ = tables(group)
        labels, rows = by_label(dist), {r["time"]: r for r in dist["rows"]}
        item = items(group)["analyze_distribution_shift"]
        truths, falling = [], []
        for choice in item["choices"]:
            match = re.fullmatch(
                r"The share of (.+) in the sample (rose by about (\d+) percentage points|fell by about (\d+) "
                r"percentage points|did not change \(by about 0 percentage points\)) from sample time (\d+) to "
                r"sample time (\d+), and its count went from (\d+) to (\d+)\.",
                choice["text"],
            )
            variant = labels[match.group(1)]
            t1, t2 = int(match.group(5)), int(match.group(6))
            assert t2 == t1 + 1
            r1, r2 = rows[t1], rows[t2]
            assert (int(match.group(7)), int(match.group(8))) == (r1[variant], r2[variant])  # the count facts are true
            change = half_up(r2[variant], r2["total"]) - half_up(r1[variant], r1["total"])
            text = match.group(2)
            if text.startswith("rose"):
                truth = change == int(match.group(3)) > 0
            elif text.startswith("fell"):
                truth = change == -int(match.group(4)) < 0
            else:
                truth = change == 0
            truths.append(truth)
            if truth:
                falling.append(r2[variant] < r1[variant])
        assert sum(truths) == 1 and truths == [c["correct"] for c in item["choices"]], (seed, truths)
        assert falling == [True], (seed, "the true claim must be the trap: its count fell while its share rose")
        windows += 1
    assert windows == len(SEEDS)


def test_interpret_fitness_rate_has_exactly_one_true_choice_and_both_measures_and_traps_occur():
    measures, trap_states = set(), []
    for seed in SEEDS:
        group = full_set(seed)
        dist, fit = tables(group)
        item = items(group)["interpret_fitness_rate"]
        measure = "survived" if "survival rate" in item["stem"] else "offspring"
        measures.add(measure)
        rate = {label.lower(): Fraction(row[measure], row["started"]) for label, row in fit.items()}
        names = list(rate)
        truths = []
        for choice in item["choices"]:
            text = choice["text"]
            higher = re.fullmatch(
                r"(.+) (?:had the higher survival rate|produced more offspring per starting individual)\.", text
            )
            if higher:
                name = higher.group(1).lower()
                other = next(n for n in names if n != name)
                truths.append(rate[name] > rate[other])
            elif text.startswith("The two variants"):
                truths.append(rate[names[0]] == rate[names[1]])
            else:
                assert "cannot be compared" in text
                truths.append(False)  # dividing by the starting numbers always allows a comparison
        assert sum(truths) == 1 and truths == [c["correct"] for c in item["choices"]], (seed, truths)
        winner = max(rate, key=rate.get)
        loser = next(n for n in names if n != winner)
        row_of = {label.lower(): row for label, row in fit.items()}
        trap_states.append(row_of[winner]["survived"] < row_of[loser]["survived"])
    assert measures == {"survived", "offspring"}
    share = sum(trap_states) / len(trap_states)
    assert 0.35 <= share <= 0.65, share


def test_support_selection_claim_has_one_supported_choice_and_is_concrete():
    for seed in SEEDS:
        group = full_set(seed)
        dist, fit = tables(group)
        item = items(group)["support_selection_claim"]
        texts = [c["text"] for c in item["choices"]]
        starts = {str(row["started"]) for row in fit.values()}
        nouns = [label.lower() for label in dist["variants"].values()]
        for text in texts:
            assert all(noun in text for noun in nouns), (seed, text)  # both variants are named
            assert re.findall(r"\d+", text) and set(re.findall(r"\d+", text)) == starts, (
                seed,
                text,
            )  # starting sizes only
            assert "%" not in text and "rate" not in text  # no percentage and no rate
        supported = [
            t
            for t in texts
            if " is passed from parents to offspring, and " in t
            and "differed in how well they survived and reproduced" in t
            and "is evidence of natural selection" in t
        ]
        assert len(supported) == 1 and supported[0] == key_text(item), (seed, texts)
        lengths = [len(t) for t in texts]
        assert max(lengths) <= 1.2 * min(lengths), (seed, lengths)
        key_len = len(supported[0])
        assert not (key_len == max(lengths) and lengths.count(key_len) == 1), seed
        assert not (key_len == min(lengths) and lengths.count(key_len) == 1), seed
        assert sum("needed it" in t for t in texts) == 1


# ---- no item answers another -------------------------------------------------------------------------


def test_no_item_leaks_another_items_key_in_a_full_set():
    for seed in SEEDS:
        group = full_set(seed)
        by_template = items(group)
        for name, item in by_template.items():
            if not item["choices"]:
                continue
            key = key_text(item)
            for other_name, other in by_template.items():
                if other_name == name:
                    continue
                haystack = [other["stem"]] + [c["text"] for c in other["choices"]]
                assert key not in haystack, (seed, name, other_name)
                assert key not in other["stem"], (seed, name, other_name)
        support = " ".join(c["text"] for c in by_template["support_selection_claim"]["choices"])
        assert "higher" not in support and "more offspring" not in support


# ---- the keys are not cued ------------------------------------------------------------------------------


def test_correct_answer_positions_vary_and_no_position_exceeds_40_percent():
    counts = {t.key: {} for t in FAMILY.templates if t.question_type == "multiple_choice"}
    for seed in SEEDS:
        for name, item in items(full_set(seed)).items():
            if name in counts:
                label = next(c["label"] for c in item["choices"] if c["correct"])
                counts[name][label] = counts[name].get(label, 0) + 1
    for name, tally in counts.items():
        assert len(tally) == 4 and max(tally.values()) <= 0.4 * len(SEEDS), (name, tally)


def test_every_multiple_choice_item_has_four_distinct_choices_and_a_specific_rationale_for_each():
    for seed in SEEDS:
        for name, item in items(full_set(seed)).items():
            if item["question_type"] != "multiple_choice":
                continue
            texts = [c["text"] for c in item["choices"]]
            rationales = [c["rationale"] for c in item["choices"]]
            assert len(item["choices"]) == 4 and len(set(texts)) == 4, (seed, name)
            assert len(set(rationales)) == 4 and all(rationales), (seed, name)


# ---- the constructed response and the language -----------------------------------------------------------


def test_constructed_answer_cites_displayed_numbers_and_rejects_need():
    for seed in SEEDS[:80]:
        group = full_set(seed)
        dist, fit = tables(group)
        item = items(group)["explain_shift_with_data"]
        rates = {label: Fraction(row["survived"], row["started"]) for label, row in fit.items()}
        winner_label = max(rates, key=rates.get)
        winner = by_label(dist)[winner_label.lower()]
        first, last = dist["rows"][0], dist["rows"][-1]
        answer = item["answer"]
        assert f"from about {half_up(first[winner], first['total'])}% at sample time {first['time']}" in answer
        assert f"to about {half_up(last[winner], last['total'])}% at sample time {last['time']}" in answer
        row = fit[winner_label]
        assert f"survival rate of {half_up(row['survived'], row['started'])}%" in answer
        assert re.search(r"\b(an?) (anatomical|behavioral|physiological) trait\b", answer)
        assert "because individual organisms changed to meet a need" in answer or "changed to meet a need" in answer
        assert "need" in item["explanation"] and "Do not give credit" in item["explanation"]


def test_wording_is_grammatical_in_every_case_and_order():
    for seed in SEEDS:
        text = all_text(full_set(seed))
        assert not re.search(r"\ba [aeiou]", text, re.IGNORECASE), seed
        assert not re.search(r"\ban [^aeiou\W]", text, re.IGNORECASE), seed
        assert "organisms are heritable" not in text and "are heritable" not in text
        assert ". the " not in text and "  " not in text


def test_scope_and_vocabulary_guard():
    banned = [
        "allele frequency",
        "gene frequency",
        "hardy",
        "chi-square",
        "drift",
        "gene flow",
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
    ]
    for seed in SEEDS:
        group = full_set(seed)
        text = all_text(group).lower()
        assert not [word for word in banned if word in text], seed
        for name, item in items(group).items():
            needy = [c["text"] for c in item["choices"] if re.search(r"\bneed", c["text"], re.IGNORECASE)]
            if name == "support_selection_claim":
                assert len(needy) == 1
            else:
                assert not needy, (seed, name)


def test_wide_seed_range_never_raises_generation_error():
    for seed in [f"wide-{i}" for i in range(250)]:
        out = generate_set(FAMILY, seed, 40)
        assert sum(len(g["questions"]) for g in out["groups"]) == 40


def test_each_template_cites_a_distinct_observable_bullet_where_the_standard_has_one():
    cited = {(t.observable_category, t.observable_index) for t in FAMILY.templates}
    assert cited == {
        ("organizing_data", 0),
        ("identifying_relationships", 0),
        ("interpreting_data", 0),
        ("interpreting_data", 1),
        ("interpreting_data", 2),
    }
```

Then add the API tests (a browse row, a preview case, the Biology 1 binding mismatch and a Biology 2 EOCEP rejection test):

```bash
git apply -p1 <<'PATCH'
--- a/backend/tests/test_api.py
+++ b/backend/tests/test_api.py
@@ -365,6 +365,15 @@
     assert "eocep_scope_note" not in classroom["options"]
 
 
+def test_eocep_is_rejected_for_the_biology_2_trait_distribution_family(client):
+    _, body = _generate(client, "biology-2", "B-LS4-3", "trait-distribution-shifts", generation_mode="eocep")
+    response = client.post("/api/generate/preview", json=body)
+    assert response.status_code == 422
+    assert "Biology 1" in response.json()["detail"]
+    _, body = _generate(client, "biology-2", "B-LS4-3", "trait-distribution-shifts")
+    assert client.post("/api/generate/preview", json=body).status_code == 200
+
+
 def test_eocep_mode_excludes_constructed_response(client):
     standards = client.get("/api/standards").json()
     bio1 = next(s for s in standards if s["course_slug"] == "biology-1" and s["code"] == "B-LS3-3")
@@ -447,6 +456,7 @@
         ("biology-1", "B-LS3-2"),
         ("biology-1", "B-LS3-3"),
         ("biology-1", "B-LS4-4"),
+        ("biology-2", "B-LS4-3"),
         ("chemistry", "C-PS1-2"),
         ("chemistry", "C-PS1-5"),
         ("chemistry", "C-PS1-7"),
@@ -485,6 +495,7 @@
         ("biology-1", "B-LS1-1", "dna-protein-synthesis"),
         ("biology-1", "B-LS3-2", "mutation-effects"),
         ("biology-1", "B-LS4-4", "natural-selection-trend"),
+        ("biology-2", "B-LS4-3", "trait-distribution-shifts"),
     ],
 )
 def test_preview_is_reproducible(client, course, code, family):
@@ -507,6 +518,8 @@
     assert client.post("/api/generate/preview", json=body).status_code == 422
     _, body = _generate(client, "biology-2", "B-LS4-3", "natural-selection-trend")
     assert client.post("/api/generate/preview", json=body).status_code == 422
+    _, body = _generate(client, "biology-1", "B-LS4-4", "trait-distribution-shifts")
+    assert client.post("/api/generate/preview", json=body).status_code == 422
     _, body = _generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity", doks=[4])
     assert client.post("/api/generate/preview", json=body).status_code == 422
     _, body = _generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity")
PATCH
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_trait_distribution_shifts.py -q -p no:cacheprovider`

Expected: `1 error` (a collection error, not a pass): `KeyError: 'trait-distribution-shifts'` raised at import, because the family is not registered. Then run `pytest tests/test_api.py -q -p no:cacheprovider`; expected: `4 failed, 31 passed`, the failures being `test_eocep_is_rejected_for_the_biology_2_trait_distribution_family`, `test_standards_browse_and_detail`, `test_preview_is_reproducible[biology-2-B-LS4-3-trait-distribution-shifts]` and `test_family_must_match_exact_standard`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add backend/tests/test_trait_distribution_shifts.py backend/tests/test_api.py
git commit -m "test: add independent checks for the B-LS4-3 trait-distribution family (failing until it exists)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The family, its registration and the pinned digest

**Files:**
- Create: `backend/app/services/families/trait_distribution_shifts.py`
- Modify: `backend/app/services/families/registry.py`
- Modify: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `Binding`, `DraftChoice`, `DraftQuestion`, `GenerationError`, `Rng`, `TemplateSpec` (`app.services.engine.core`); `QuestionFamily` (`app.services.engine.family`).
- Produces: `TraitDistributionShifts` (key `trait-distribution-shifts`, version `1.1.0`, `bindings = (Binding("SC", "biology-2", "B-LS4-3"),)`, six templates); scenario params `{case, favored, swap, rows, window, pooled, fitness}`.

- [ ] **Step 1: Write the module**

Create `backend/app/services/families/trait_distribution_shifts.py` with exactly this content. Each multiple-choice item is a list of `Claim(text, holds, why)` where `holds` is computed from the stored data, and `_mc` raises `GenerationError` (so the engine redraws) unless exactly one claim holds. The pooled question is chosen when the scenario is drawn, and `represent_distribution` refuses to repeat the statement that equals the pooled key.

```python
"""B-LS4-3: statistical analysis of changing distributions of heritable traits (Biology 2).

Every count, percentage and rate shown to students is stored in the scenario. Each multiple-choice item is built from
claims whose truth is computed from that stored data, and the builder requires exactly one true claim, so a distractor
that happens to be true redraws the item instead of reaching a student. Only basic proportion arithmetic is used; the
family never calculates an allele frequency.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily

MAX_DRAWS = 400
TOTAL_CHOICES = tuple(t for t in range(80, 145, 5) if t != 100)
ROUNDING_NOTE = "Percentages are rounded to the nearest whole number; a half rounds up."

CASES: dict[str, dict[str, Any]] = {
    "beetles": {
        "organism": "ground beetles",
        "trait": "shell color",
        "trait_type": "anatomical",
        "place": "on the dark hillside soil",
        "intro": "Parents pass shell color to their offspring. Birds that eat the beetles find dark-shelled beetles harder to see against dark soil.",
        "condition": "The soil on the hillside is dark.",
        "favored": "a",
        "variants": {
            "a": {"label": "Dark-shelled beetles", "noun": "dark-shelled beetles"},
            "b": {"label": "Light-shelled beetles", "noun": "light-shelled beetles"},
        },
    },
    "finches": {
        "organism": "finches",
        "trait": "beak thickness",
        "trait_type": "anatomical",
        "place": "on the island where most seeds are soft",
        "intro": "Parents pass beak thickness to their offspring. Thin beaks eat soft seeds more easily than thick beaks do.",
        "condition": "Most seeds on the island are soft.",
        "favored": "b",
        "variants": {
            "a": {"label": "Thick-beaked finches", "noun": "thick-beaked finches"},
            "b": {"label": "Thin-beaked finches", "noun": "thin-beaked finches"},
        },
    },
    "minnows": {
        "organism": "pond minnows",
        "trait": "reaction speed",
        "trait_type": "behavioral",
        "place": "in the pond with predatory fish",
        "intro": "Parents pass reaction speed to their offspring. Minnows that react quickly escape predatory fish more often than slow-reacting minnows do.",
        "condition": "Predatory fish live in the pond.",
        "favored": "a",
        "variants": {
            "a": {"label": "Quick-reacting minnows", "noun": "quick-reacting minnows"},
            "b": {"label": "Slow-reacting minnows", "noun": "slow-reacting minnows"},
        },
    },
    "shrubs": {
        "organism": "desert shrubs",
        "trait": "root depth",
        "trait_type": "anatomical",
        "place": "on the plain where rain wets only the top layer of soil",
        "intro": "Parents pass root depth to their offspring. Shallow roots take up water from the top layer of soil before it dries.",
        "condition": "Rain falls often but wets only the top layer of the soil.",
        "favored": "b",
        "variants": {
            "a": {"label": "Deep-rooted shrubs", "noun": "deep-rooted shrubs"},
            "b": {"label": "Shallow-rooted shrubs", "noun": "shallow-rooted shrubs"},
        },
    },
    "marsh_grass": {
        "organism": "marsh grass plants",
        "trait": "salt tolerance",
        "trait_type": "physiological",
        "place": "in the salty marsh soil",
        "intro": "Parents pass salt tolerance to their offspring. Salt-tolerant plants keep growing in salty soil.",
        "condition": "Salt water reaches the marsh soil at high tide.",
        "favored": "a",
        "variants": {
            "a": {"label": "Salt-tolerant marsh grass plants", "noun": "salt-tolerant marsh grass plants"},
            "b": {"label": "Less salt-tolerant marsh grass plants", "noun": "less salt-tolerant marsh grass plants"},
        },
    },
    "lizards": {
        "organism": "desert lizards",
        "trait": "water conservation",
        "trait_type": "physiological",
        "place": "in the dry desert valley",
        "intro": "Parents pass water-conservation ability to their offspring. Lizards that conserve more water lose less of it on dry days.",
        "condition": "Rain is rare, and the water holes dry up early in the season.",
        "favored": "a",
        "variants": {
            "a": {"label": "High-conservation lizards", "noun": "high-conservation lizards"},
            "b": {"label": "Low-conservation lizards", "noun": "low-conservation lizards"},
        },
    },
}


def _other(variant: str) -> str:
    return "b" if variant == "a" else "a"


def _pct(count: int, total: int) -> int:
    """Whole-number percentage, half up (students round .5 up; Python's round() does not)."""
    return int((Decimal(100 * count) / Decimal(total)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _article(trait_type: str) -> str:
    return "an" if trait_type[0] in "aeiou" else "a"


def next_proportion(proportion: float, favored_rate: float, other_rate: float) -> float:
    """Relative-fitness update for the proportion of the favored variant."""
    return proportion * favored_rate / (proportion * favored_rate + (1 - proportion) * other_rate)


def draw_distribution(rng: Rng, favored: str) -> tuple[list[dict[str, int]], list[int]]:
    """Four unequal samples with a clear proportional trend and a window where the raw count falls but the share rises."""
    for _ in range(MAX_DRAWS):
        totals = rng.sample(list(TOTAL_CHOICES), 4)
        proportion = rng.uniform(0.20, 0.30)
        own, other = round(rng.uniform(0.66, 0.78), 2), round(rng.uniform(0.46, 0.56), 2)
        proportions = [proportion]
        for _ in range(3):
            proportions.append(next_proportion(proportions[-1], own, other))
        rows = []
        for time, (total, p) in enumerate(zip(totals, proportions, strict=True), start=1):
            count = round(total * p)
            values = {favored: count, _other(favored): total - count}
            rows.append({"time": time, "total": total, "a": values["a"], "b": values["b"]})
        if any(not 2 <= row[v] <= row["total"] - 2 for row in rows for v in ("a", "b")):
            continue
        pcts = [_pct(row[favored], row["total"]) for row in rows]
        if pcts[-1] - pcts[0] < 15 or min(b - a for a, b in zip(pcts, pcts[1:])) < 3:
            continue
        windows = [i for i in range(3) if rows[i + 1][favored] < rows[i][favored]]
        if not windows:
            continue
        window = rng.choice(windows)
        return rows, [window, window + 1]
    raise GenerationError("trait-distribution-shifts: no valid distribution after redraw limit")


def pooled_errors(
    rows: list[dict[str, int]], first: int, second: int, variant: str
) -> tuple[int, list[tuple[int, str]]]:
    """The pooled percentage of `variant` over two samples, and the classic wrong answers (value, rationale)."""
    r1, r2, other = rows[first], rows[second], _other(variant)
    count_sum, total_sum = r1[variant] + r2[variant], r1["total"] + r2["total"]
    key = _pct(count_sum, total_sum)
    p1, p2 = _pct(r1[variant], r1["total"]), _pct(r2[variant], r2["total"])
    mean = int(
        ((Decimal(100 * r1[variant]) / r1["total"] + Decimal(100 * r2[variant]) / r2["total"]) / 2).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    errors = [
        (
            mean,
            f"This averages the two percentages ({p1}% and {p2}%). The samples have different totals, so the combined percentage comes from the combined counts, which give {key}%.",
        ),
        (count_sum, f"{count_sum} is the combined count, not a percentage; the combined percentage is {key}%."),
        (p1, f"{p1}% is the percentage for sample time {r1['time']} alone; the combined percentage is {key}%."),
        (p2, f"{p2}% is the percentage for sample time {r2['time']} alone; the combined percentage is {key}%."),
        (
            _pct(r1[other] + r2[other], total_sum),
            f"{_pct(r1[other] + r2[other], total_sum)}% is the combined percentage of the other variant; the combined percentage of this variant is {key}%.",
        ),
    ]
    return key, errors


def usable_errors(key: int, errors: list[tuple[int, str]]) -> list[tuple[int, str]]:
    seen: set[int] = {key}
    usable = []
    for value, why in errors:
        if value not in seen and value <= 99:
            seen.add(value)
            usable.append((value, why))
    return usable


def choose_pooled(rng: Rng, rows: list[dict[str, int]]) -> dict[str, Any] | None:
    """A pair of samples and a variant whose pooled percentage is shown nowhere and has three usable wrong answers."""
    options = [(i, j, v) for i in range(4) for j in range(i + 1, 4) for v in ("a", "b")]
    for first, second, variant in rng.shuffled(options):
        key, errors = pooled_errors(rows, first, second, variant)
        if key in {_pct(row[variant], row["total"]) for row in rows} or len(usable_errors(key, errors)) < 3:
            continue
        return {"first": first, "second": second, "variant": variant}
    return None


def draw_fitness(rng: Rng, favored: str) -> dict[str, Any]:
    """Survival and offspring for one interval; about half the draws give the favored variant fewer raw survivors."""
    trap = rng.choice([True, False])
    for _ in range(MAX_DRAWS):
        big, small = 5 * rng.randint(14, 18), 5 * rng.randint(8, 11)
        favored_big = rng.choice([True, False])
        starts = {favored: big if favored_big else small, _other(favored): small if favored_big else big}
        favored_survival, other_survival = round(rng.uniform(0.72, 0.84), 2), round(rng.uniform(0.42, 0.54), 2)
        favored_offspring, other_offspring = round(rng.uniform(0.70, 0.84), 2), round(rng.uniform(0.30, 0.46), 2)
        survived = {v: round(starts[v] * (favored_survival if v == favored else other_survival)) for v in starts}
        offspring = {v: round(starts[v] * (favored_offspring if v == favored else other_offspring)) for v in starts}
        other = _other(favored)
        if (survived[favored] < survived[other]) != trap:
            continue
        if Fraction(survived[favored], starts[favored]) - Fraction(survived[other], starts[other]) < Fraction(15, 100):
            continue
        if Fraction(offspring[favored], starts[favored]) - Fraction(offspring[other], starts[other]) < Fraction(
            20, 100
        ):
            continue
        return {
            "trap": trap,
            "rows": [
                {"variant": v, "started": starts[v], "survived": survived[v], "offspring": offspring[v]}
                for v in ("a", "b")
            ],
        }
    raise GenerationError("trait-distribution-shifts: no valid fitness comparison after redraw limit")


def draw_scenario(rng: Rng) -> dict[str, Any]:
    case_key = rng.choice(sorted(CASES))
    favored = CASES[case_key]["favored"]
    for _ in range(MAX_DRAWS):
        rows, window = draw_distribution(rng, favored)
        pooled = choose_pooled(rng, rows)
        if pooled is not None:
            return {
                "case": case_key,
                "favored": favored,
                "swap": rng.choice([True, False]),
                "rows": rows,
                "window": window,
                "pooled": pooled,
                "fitness": draw_fitness(rng, favored),
            }
    raise GenerationError("trait-distribution-shifts: no scenario with a hidden pooled proportion")


@dataclass
class Claim:
    text: str
    holds: bool
    why: str


class TraitDistributionShifts(QuestionFamily):
    key = "trait-distribution-shifts"
    version = "1.1.0"
    title = "Trait distribution shifts"
    description = (
        "Analyze proportions and fitness rates to explain shifts in a heritable trait's distribution over time."
    )
    stimulus_kind = "trait_distribution_shifts"
    bindings = (Binding("SC", "biology-2", "B-LS4-3"),)
    templates = (
        TemplateSpec("represent_distribution", "Read a trait distribution", 1, "multiple_choice", "organizing_data", 0),
        TemplateSpec(
            "calculate_proportion",
            "Calculate a pooled trait proportion",
            1,
            "multiple_choice",
            "identifying_relationships",
            0,
        ),
        TemplateSpec(
            "analyze_distribution_shift",
            "Analyze a distribution shift",
            2,
            "multiple_choice",
            "identifying_relationships",
            0,
        ),
        TemplateSpec(
            "interpret_fitness_rate", "Interpret a fitness rate", 2, "multiple_choice", "interpreting_data", 0
        ),
        TemplateSpec(
            "support_selection_claim", "Support a selection claim", 2, "multiple_choice", "interpreting_data", 1
        ),
        TemplateSpec(
            "explain_shift_with_data",
            "Explain a trait distribution shift",
            3,
            "constructed_response",
            "interpreting_data",
            2,
        ),
    )

    # ---- helpers ----------------------------------------------------------------------------

    @staticmethod
    def _order(params: dict[str, Any]) -> list[str]:
        return ["b", "a"] if params["swap"] else ["a", "b"]

    @staticmethod
    def _variants(params: dict[str, Any]) -> dict[str, dict[str, str]]:
        return CASES[params["case"]]["variants"]

    @staticmethod
    def _fitness(params: dict[str, Any]) -> dict[str, dict[str, int]]:
        return {row["variant"]: row for row in params["fitness"]["rows"]}

    @staticmethod
    def _mc(stem: str, claims: list[Claim]) -> DraftQuestion:
        if sum(c.holds for c in claims) != 1:
            raise GenerationError("trait-distribution-shifts: not exactly one true claim")
        key = next(c for c in claims if c.holds)
        return DraftQuestion(
            stem=stem,
            answer=key.text,
            explanation=key.why,
            choices=[DraftChoice(c.text, c.holds, c.why) for c in claims],
        )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        case, labels, order = CASES[params["case"]], self._variants(params), self._order(params)
        keys = set(template_keys)
        chart_items = {
            "represent_distribution",
            "analyze_distribution_shift",
            "support_selection_claim",
            "explain_shift_with_data",
        }
        needs_distribution = keys & (chart_items | {"calculate_proportion"})
        with_chart = bool(keys & chart_items)
        tables: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        intro = [case["intro"], case["condition"]]
        if needs_distribution:
            columns = [{"key": "time", "label": "Sample time"}, {"key": "total", "label": "Total sampled"}]
            columns += [{"key": v, "label": labels[v]["label"]} for v in order]
            rows = [dict(row) for row in params["rows"]]
            if with_chart:
                columns += [{"key": f"{v}_pct", "label": f"{labels[v]['label']} (percent of sample)"} for v in order]
                for row in rows:
                    for v in ("a", "b"):
                        row[f"{v}_pct"] = _pct(row[v], row["total"])
                intro.append(ROUNDING_NOTE)
            tables.append(
                {"caption": f"Trait distribution in sampled {case['organism']}", "columns": columns, "rows": rows}
            )
            if with_chart:
                charts.append(
                    {
                        "type": "line",
                        "title": f"Percentage of sampled {case['organism']} with each variant",
                        "x": {"key": "time", "label": "Sample time"},
                        "y": {"label": "Percentage of sample", "min": 0},
                        "series": [{"key": f"{v}_pct", "label": labels[v]["label"]} for v in order],
                        "table_index": 0,
                    }
                )
        if keys & {"interpret_fitness_rate", "support_selection_claim", "explain_shift_with_data"}:
            fitness = self._fitness(params)
            tables.append(
                {
                    "caption": "Survival and offspring during one sample interval",
                    "columns": [
                        {"key": "variant", "label": "Variant"},
                        {"key": "started", "label": "Started"},
                        {"key": "survived", "label": "Survived"},
                        {"key": "offspring", "label": "Offspring produced"},
                    ],
                    "rows": [
                        {
                            "variant": labels[v]["label"],
                            "started": fitness[v]["started"],
                            "survived": fitness[v]["survived"],
                            "offspring": fitness[v]["offspring"],
                        }
                        for v in order
                    ],
                }
            )
        return {
            "title": "Trait distributions in a population",
            "intro": " ".join(intro),
            "sections": [],
            "tables": tables,
            "charts": charts,
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_represent_distribution(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, row = self._variants(params), rng.choice(params["rows"])
        variant = rng.choice(["a", "b"])
        noun = labels[variant]["noun"]
        actual = _pct(row[variant], row["total"])
        other = _pct(row[_other(variant)], row["total"])

        def pct_claim(number: int, why: str) -> Claim:
            return Claim(f"About {number}% of the sample had {noun}.", _pct(row[variant], row["total"]) == number, why)

        claims = [
            pct_claim(actual, f"{row[variant]} of {row['total']} is about {actual}%."),
            pct_claim(
                row[variant],
                f"{row[variant]} is the count of {noun}, not a percentage; {row[variant]} of {row['total']} is about {actual}%.",
            ),
            pct_claim(
                other,
                f"{other}% is the share of the other variant ({row[_other(variant)]} of {row['total']}); {noun} were about {actual}%.",
            ),
            Claim(
                "The table does not show the total sampled, so the proportion cannot be found.",
                False,
                f"The table shows the total sampled at each time ({row['total']} at time {row['time']}), so the proportion can be found.",
            ),
        ]
        pooled = params["pooled"]
        hidden = f"About {pooled_errors(params['rows'], pooled['first'], pooled['second'], pooled['variant'])[0]}% of the sample had {labels[pooled['variant']]['noun']}."
        if any(claim.text == hidden for claim in claims):
            raise GenerationError("trait-distribution-shifts: represent choice would repeat the pooled answer")
        return self._mc(
            f"At sample time {row['time']}, which statement accurately represents the distribution?", claims
        )

    def _q_calculate_proportion(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, rows, pooled = self._variants(params), params["rows"], params["pooled"]
        first, second, variant = pooled["first"], pooled["second"], pooled["variant"]
        r1, r2 = rows[first], rows[second]
        key, errors = pooled_errors(rows, first, second, variant)
        noun = labels[variant]["noun"]
        chosen = rng.sample(usable_errors(key, errors), 3)
        claims = [
            Claim(
                f"{key}%",
                True,
                f"Combine the counts first: ({r1[variant]} + {r2[variant]}) divided by ({r1['total']} + {r2['total']}) is about {key}%.",
            )
        ] + [Claim(f"{value}%", False, why) for value, why in chosen]
        return self._mc(
            f"What percentage of all the individuals sampled at sample times {r1['time']} and {r2['time']} "
            f"combined were {noun}? Combine the counts from the two samples first.",
            claims,
        )

    def _q_analyze_distribution_shift(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._variants(params), params["favored"]
        other = _other(favored)
        first, second = params["window"]
        r1, r2 = params["rows"][first], params["rows"][second]

        def change(variant: str) -> int:
            return _pct(r2[variant], r2["total"]) - _pct(r1[variant], r1["total"])

        shift = change(favored)

        def claim(variant: str, direction: str, amount: int, why: str) -> Claim:
            actual = change(variant)
            holds = (
                (direction == "rose" and actual == amount and amount > 0)
                or (direction == "fell" and actual == -amount and amount > 0)
                or (direction == "did not change" and actual == 0 and amount == 0)
            )
            what = (
                "did not change (by about 0 percentage points)"
                if direction == "did not change"
                else f"{direction} by about {amount} percentage points"
            )
            text = (
                f"The share of {labels[variant]['noun']} in the sample {what} from sample time {r1['time']} "
                f"to sample time {r2['time']}, and its count went from {r1[variant]} to {r2[variant]}."
            )
            return Claim(text, holds, why)

        favored_noun = labels[favored]["noun"]
        claims = [
            claim(
                favored,
                "rose",
                shift,
                f"The share of {favored_noun} was about {_pct(r1[favored], r1['total'])}% and then about {_pct(r2[favored], r2['total'])}%, a rise of {shift} points, even though the count went from {r1[favored]} to {r2[favored]}.",
            ),
            claim(
                favored,
                "fell",
                shift,
                f"The count of {favored_noun} went from {r1[favored]} to {r2[favored]}, but the totals sampled were different ({r1['total']} and {r2['total']}), so the share rose by {shift} points.",
            ),
            claim(
                other,
                "rose",
                shift,
                f"The share of {labels[other]['noun']} went from about {_pct(r1[other], r1['total'])}% to about {_pct(r2[other], r2['total'])}%, so it fell, not rose.",
            ),
            claim(
                favored,
                "did not change",
                0,
                f"A different total sampled does not mean the share stayed the same; the share of {favored_noun} changed by {shift} points.",
            ),
        ]
        return self._mc(
            f"Which statement about the share of each variant from sample time {r1['time']} to sample time "
            f"{r2['time']} is supported by the table and graph?",
            claims,
        )

    def _q_interpret_fitness_rate(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._variants(params), params["favored"]
        other = _other(favored)
        rows = self._fitness(params)
        measure = rng.choice(["survived", "offspring"])
        rate = {v: Fraction(rows[v][measure], rows[v]["started"]) for v in rows}
        per = {v: _pct(rows[v][measure], rows[v]["started"]) for v in rows}
        word = "survival rate" if measure == "survived" else "number of offspring per starting individual"

        def higher(variant: str) -> str:
            label = labels[variant]["label"]
            return (
                f"{label} had the higher survival rate."
                if measure == "survived"
                else f"{label} produced more offspring per starting individual."
            )

        def numbers(variant: str) -> str:
            row = rows[variant]
            what = "survived" if measure == "survived" else "offspring were produced"
            return f"{row[measure]} of {row['started']} {what} ({per[variant]} per 100 starters)"

        def lower_note(variant: str, rival: str) -> str:
            more = rows[variant][measure] > rows[rival][measure]
            lead = (
                f"{labels[variant]['label']} had more ({rows[variant][measure]}) but started with more individuals. "
                if more
                else ""
            )
            return f"{lead}{numbers(variant)} compared with {numbers(rival)}."

        claims = [
            Claim(
                higher(favored),
                rate[favored] > rate[other],
                f"Compare rates, not counts: {numbers(favored)}, compared with {numbers(other)}.",
            ),
            Claim(
                higher(other),
                rate[other] > rate[favored],
                f"Not supported. {lower_note(other, favored)} Its rate is lower.",
            ),
            Claim(
                f"The two variants had the same {word}."
                if measure == "survived"
                else "The two variants produced the same number of offspring per starting individual.",
                rate[favored] == rate[other],
                f"Not supported. The rates are {per[favored]} and {per[other]} per 100 starters.",
            ),
            Claim(
                f"The {word}s cannot be compared because the two groups started with different numbers."
                if measure == "survived"
                else "The offspring rates cannot be compared because the two groups started with different numbers.",
                False,
                "Not supported. Dividing by the number that started puts the groups on the same scale, so the rates can be compared.",
            ),
        ]
        return self._mc(
            f"Which statement about the {word} of the two variants is supported by the survival and offspring table?",
            claims,
        )

    def _q_support_selection_claim(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case, labels, favored = CASES[params["case"]], self._variants(params), params["favored"]
        other = _other(favored)
        rows = self._fitness(params)
        fav_noun, other_noun = labels[favored]["noun"], labels[other]["noun"]
        trait = case["trait"]
        groups = (
            f"the {fav_noun} (started with {rows[favored]['started']}) and the {other_noun} "
            f"(started with {rows[other]['started']})"
        )
        survival_same = Fraction(rows[favored]["survived"], rows[favored]["started"]) == Fraction(
            rows[other]["survived"], rows[other]["started"]
        )
        conclusion = f"the rise in the share of {fav_noun} is evidence of natural selection"
        claims = [
            Claim(
                f"{trait.capitalize()} is passed from parents to offspring, and {case['place']}, {groups} differed in how well they survived and reproduced, so {conclusion}.",
                not survival_same,
                "Correct: the trait is inherited and the two groups survived and reproduced at different rates, so a change in the share of one variant can be evidence of natural selection.",
            ),
            Claim(
                f"Individual {case['organism']} changed their {trait} because they needed it, and {case['place']}, {groups} differed in how well they survived and reproduced, so {conclusion}.",
                False,
                "Not supported. Individuals do not change a heritable trait because they need it; the share of a variant changes when its members survive and reproduce more.",
            ),
            Claim(
                f"{trait.capitalize()} is passed from parents to offspring, but {case['place']}, {groups} survived and reproduced equally well, so {conclusion}.",
                survival_same,
                "Not supported. The survival table shows the two groups did not survive and reproduce at the same rates.",
            ),
            Claim(
                f"{trait.capitalize()} is not passed from parents to offspring, and {case['place']}, {groups} differed in how well they survived and reproduced, so {conclusion}.",
                False,
                f"Not supported. The stimulus states that parents pass {trait} to their offspring, and selection acts only on heritable traits.",
            ),
        ]
        return self._mc(
            f"Which explanation for the rise in the share of {fav_noun} is best supported by the data?", claims
        )

    def _q_explain_shift_with_data(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case, labels, favored = CASES[params["case"]], self._variants(params), params["favored"]
        other = _other(favored)
        rows = params["rows"]
        first, last = rows[0], rows[-1]
        fit = self._fitness(params)
        p_first, p_last = _pct(first[favored], first["total"]), _pct(last[favored], last["total"])
        survival = {v: _pct(fit[v]["survived"], fit[v]["started"]) for v in fit}
        offspring = {v: _pct(fit[v]["offspring"], fit[v]["started"]) for v in fit}
        fav_label, fav_noun, other_noun = labels[favored]["label"], labels[favored]["noun"], labels[other]["noun"]
        kind = case["trait_type"]
        answer = (
            f"The share of {fav_noun} rose from about {p_first}% at sample time {first['time']} to about {p_last}% at "
            f"sample time {last['time']}. {case['trait'].capitalize()} is {_article(kind)} {kind} trait that parents pass "
            f"to their offspring. In the survival table, {fav_noun} had a survival rate of {survival[favored]}% and "
            f"produced {offspring[favored]} offspring per 100 starting individuals, compared with {survival[other]}% and "
            f"{offspring[other]} for {other_noun}. Because the trait is inherited and {fav_noun} survived and reproduced at "
            f"higher rates, their share of the population increased. The change did not happen because individual "
            f"organisms changed to meet a need."
        )
        return DraftQuestion(
            stem=(
                f"Use both tables and the graph to explain the change in the distribution of {case['trait']} in these "
                f"{case['organism']}. Include data from the tables, and say what type of trait it is."
            ),
            answer=answer,
            explanation=(
                "Scoring guide (4 points): (1) identify the trait type (anatomical, behavioral or physiological) and the "
                f"variant whose share changed ({fav_label}); (2) cite two percentages from the table or graph; (3) cite "
                "the survival or offspring rates, computed from the starting numbers, as the evidence for the fitness "
                "difference; (4) explain that the trait is passed from parents to offspring, so higher survival and "
                "reproduction can increase the variant's share over time. Do not give credit for an explanation in which "
                "individual organisms change because they need to."
            ),
        )
```

- [ ] **Step 2: Register it and pin its digest**

```bash
git apply -p1 <<'PATCH'
--- a/backend/app/services/families/registry.py
+++ b/backend/app/services/families/registry.py
@@ -13,6 +13,7 @@
 from app.services.families.quantitative_conservation import QuantitativeConservation
 from app.services.families.reaction_outcome import ReactionOutcome
 from app.services.families.reaction_rate import ReactionRate
+from app.services.families.trait_distribution_shifts import TraitDistributionShifts
 
 FAMILIES: dict[str, QuestionFamily] = {
     f.key: f
@@ -26,6 +27,7 @@
         DnaProteinSynthesis(),
         MutationEffects(),
         NaturalSelectionTrend(),
+        TraitDistributionShifts(),
     )
 }
 
--- a/backend/tests/test_engine.py
+++ b/backend/tests/test_engine.py
@@ -32,6 +32,7 @@
     "dna-protein-synthesis": "9f2f9a47a24ce709ee576bc919d84c5512020cf35a2993d03bae506109c80fca",
     "mutation-effects": "1d5b9a9ab23f50190c4035c0d4981d639efa9ce863c777119d41e45a0fb1dead",
     "natural-selection-trend": "50b86d0a1fa6f0a194571beb68954d007b1ec5e82211897224db7b7f3177dd3f",
+    "trait-distribution-shifts": "e6c536601bc70d98318a3a8f86332ab4f8d31a0db487d28bc48c794c9cfca49f",
 }
 
 
@@ -109,7 +110,7 @@
 @pytest.mark.parametrize("key", sorted(FAMILIES))
 def test_template_citations_exist_in_scde_data(key):
     fam = FAMILIES[key]
-    files = {"biology-1": "biology-1.json", "chemistry": "chemistry.json"}
+    files = {"biology-1": "biology-1.json", "biology-2": "biology-2.json", "chemistry": "chemistry.json"}
     for b in fam.bindings:
         std = _load_standard(files[b.course_slug], b.code)
         assert std.get("question_family_candidate") is True
PATCH
```

The patch adds the import and the registry entry, maps `biology-2.json` for the citation test, and pins the golden digest of `generate_set(family, "golden", 12)` for this module. Because the module text is fixed above, the digest is too; if it does not match, the module was copied incorrectly.

- [ ] **Step 3: Run the family tests and the engine matrix**

Run: `pytest tests/test_trait_distribution_shifts.py tests/test_engine.py -q -p no:cacheprovider`

Expected: `73 passed` (20 family tests plus the engine matrix, including the new family's determinism, golden and citation cases).

- [ ] **Step 4: Prove each guard by planting the defect (every one must make a named test fail)**

Back up, plant, run, restore. The expected failures are in the comments.

```bash
M=app/services/families/trait_distribution_shifts.py
cp $M /tmp/tds.clean
run(){ pytest tests/test_trait_distribution_shifts.py -q -p no:cacheprovider "$@" 2>&1 | grep -E "^FAILED|passed|failed" | sed 's/ - .*//;s#tests/test_trait_distribution_shifts.py::##'; }

# M2 half-to-even round() instead of half up: 6 failures (percent columns, exact halves, represent, pooled, analyze, constructed answer)
python3 - <<'EOF'
p='app/services/families/trait_distribution_shifts.py'; s=open(p).read()
a=s.index("def _pct(count: int, total: int) -> int:"); b=s.index("def _article")
open(p,'w').write(s[:a]+"def _pct(count: int, total: int) -> int:\n    return round(100 * count / total)\n\n\n"+s[b:])
EOF
run; cp /tmp/tds.clean $M

# M3 a support choice states a rate: concreteness and leak test fails
sed -i 's/survived and reproduced equally well/survived and reproduced at the same rates/' $M; run; cp /tmp/tds.clean $M

# M4 the pooled key may equal a displayed percentage: test_the_pooled_key_is_never_displayed fails
sed -i 's/        if key in {_pct(row\[variant\], row\["total"\]) for row in rows} or len(usable_errors(key, errors)) < 3:/        if len(usable_errors(key, errors)) < 3:/' $M; run; cp /tmp/tds.clean $M

# M6 a banned term in a case intro: test_scope_and_vocabulary_guard fails
sed -i 's/Birds that eat the beetles find/Genetic drift is not involved. Birds that eat the beetles find/' $M; run; cp /tmp/tds.clean $M

# M7 a row that no longer sums to its total: test_totals_are_distinct_in_range_and_never_100_and_rows_sum fails
sed -i 's/            values = {favored: count, _other(favored): total - count}/            values = {favored: count, _other(favored): total - count + 1}/' $M; run; cp /tmp/tds.clean $M

# M1c the original C2 defect: a total of 100 allowed, the raw-count distractor worded differently and hand-labelled false:
# test_represent_distribution_has_exactly_one_true_choice and the totals test fail
python3 - <<'EOF'
p='app/services/families/trait_distribution_shifts.py'; s=open(p).read()
s=s.replace("TOTAL_CHOICES = tuple(t for t in range(80, 145, 5) if t != 100)","TOTAL_CHOICES = tuple(range(80, 145, 5))")
a=s.index("            pct_claim(\n                row[variant],"); b=s.index("            pct_claim(\n                other,")
s=s[:a]+'            Claim(f"{row[variant]}% of the sample had {noun}.", False, "The count is not a percentage."),\n'+s[b:]
open(p,'w').write(s)
EOF
run -k "represent or totals"; cp /tmp/tds.clean $M

# M8 the original C1 defect: "the variant with more survivors had the higher survival rate" hand-labelled false:
# test_interpret_fitness_rate_has_exactly_one_true_choice_and_both_measures_and_traps_occur fails
python3 - <<'EOF'
p='app/services/families/trait_distribution_shifts.py'; s=open(p).read()
old = """            Claim(
                higher(other),
                rate[other] > rate[favored],
                f"Not supported. {lower_note(other, favored)} Its rate is lower.",
            ),
"""
assert s.count(old) == 1, "the fitness claim moved; find it with grep -n 'higher(other)'"
open(p,'w').write(s.replace(old, """            Claim("The variant with more survivors had the higher survival rate.", False, "Not supported."),
"""))
EOF
run; cp /tmp/tds.clean $M

diff -q /tmp/tds.clean $M && git diff --stat -- $M   # Expected: no differences, then empty
pytest tests/test_trait_distribution_shifts.py -q -p no:cacheprovider   # Expected: 20 passed
```

If a mutation line does not change the file (the `sed` pattern did not match after `ruff format`), find the real line with `grep -n` and adjust; a mutation that changes nothing proves nothing.

- [ ] **Step 5: Format, lint, commit**

```bash
/home/brandon/apps/science-bank/backend/.venv/bin/ruff format app/services/families/trait_distribution_shifts.py tests/test_trait_distribution_shifts.py
/home/brandon/apps/science-bank/backend/.venv/bin/ruff check app tests
cd .. && git add backend/app/services/families/trait_distribution_shifts.py backend/app/services/families/registry.py backend/tests/test_engine.py
git commit -m "feat: B-LS4-3 trait-distribution-shifts 1.1.0 with one-true-choice claims

Rebuilt after the first build was withdrawn. Every multiple-choice item is built from claims whose truth is
computed from the stored data and requires exactly one true claim; totals are never 100; percentages round half
up; the pooled calculation item is shown nowhere; the support choices are concrete and state no rate or winner.

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

Expected: `ruff format` reports the two files unchanged (the text above is already formatted) and `ruff check` passes.

---

### Task 3: Make the spec and roadmap match what was built

**Files:**
- Modify: `docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md`
- Modify: `docs/superpowers/plans/2026-09-29-coverage-roadmap.md`

- [ ] **Step 1: Apply the documentation edits**

The spec edits record what the build settled: the pooled item's wrong-answer pool and its scenario-level choice, the analyze choice wording (every choice states the true counts, so the raw-count trap is carried by the share direction), the support evidence wording ("differed in how well they survived and reproduced" and "survived and reproduced equally well"), and the stem name of the fitness table. The roadmap edit moves the Biology 2 B-LS4-3 row to "built" and corrects the family and standard counts.

```bash
git apply -p1 <<'PATCH'
--- a/docs/superpowers/plans/2026-09-29-coverage-roadmap.md
+++ b/docs/superpowers/plans/2026-09-29-coverage-roadmap.md
@@ -5,7 +5,7 @@
 
 ## Where coverage stands
 
-38 standards are imported (Biology 1: 14, Biology 2: 12, Chemistry: 12). Nine families are live:
+38 standards are imported (Biology 1: 14, Biology 2: 12, Chemistry: 12). Ten families are live:
 
 | Family | Standard(s) |
 |---|---|
@@ -18,8 +18,9 @@
 | `dna-protein-synthesis` | Biology 1 B-LS1-1 (built 2026-10-02; Biology 1 only, classroom-only) |
 | `mutation-effects` | Biology 1 B-LS3-2 (built 2026-10-03; sequence-level mutation effects only; meiosis and mutagen data items still to do) |
 | `natural-selection-trend` | Biology 1 B-LS4-4 (built 2026-10-03; Biology 1 only, classroom-only) |
+| `trait-distribution-shifts` | Biology 2 B-LS4-3 (built 2026-10-05 as 1.1.0, after the first build was withdrawn; classroom-only) |
 
-That is 8 standards with a family. Biology 2 has none. Every question in the bank comes from a family, so
+That is 9 standards with a family. Biology 2 has one. Every question in the bank comes from a family, so
 results tracking and variants (see `2026-09-29-results-and-variants-design.md`) only help standards that have
 one. This roadmap is the parallel track.
 
@@ -53,9 +54,8 @@
 ### Tier B — remaining Biology 1
 
 B-LS1-5 (photosynthesis), B-LS1-7 (cellular respiration), B-LS4-1 (evidence for evolution), B-LS4-2 (natural
-selection), B-LS4-4 (adaptation, flagged as a good candidate: gene-frequency change over generations) **(built as `natural-selection-trend`; Biology 2 B-LS4-3 still needs its own templates)**, B-LS4-5
-(extinction and speciation). `natural-selection-trend` from the existing catalog serves both B-LS4-4 and
-Biology 2 B-LS4-3.
+selection), B-LS4-4 (adaptation, flagged as a good candidate: gene-frequency change over generations) **(built as `natural-selection-trend`; Biology 2 B-LS4-3 is separately built as `trait-distribution-shifts`)**, B-LS4-5
+(extinction and speciation).
 
 ### Tier C — Biology 2 (reuse first)
 
@@ -64,7 +64,7 @@
 | B-LS2-2 | Extends `population-carrying-capacity` to scale and resilience |
 | B-LS2-4 | Trophic energy transfer (flagged candidate) |
 | B-LS3-3 | Hardy-Weinberg on the `trait-probability` engine (flagged candidate) |
-| B-LS4-3 | Shares the natural-selection family with B-LS4-4 |
+| B-LS4-3 | **Built** as `trait-distribution-shifts` (1.1.0); its basic statistical and graphical boundary has its own templates |
 | B-LS1-1, B-LS3-2, B-LS4-1 | Already covered by Biology 1 families once built (repeat PEs); check that the Biology 2 boundary is not narrower |
 | B-LS2-3, B-LS2-6, B-LS2-8, B-LS3-1, B-LS4-6 | New scenario-style families; lowest priority |
 
--- a/docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md
+++ b/docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md
@@ -148,18 +148,21 @@
 - **`calculate_proportion`** asks for a **pooled** percentage: "What percentage of all the individuals sampled at sample
   times i and j combined were [variant]?" (two distinct named samples; the question says to combine them). The key is
   `(count_i + count_j) / (total_i + total_j) * 100` rounded half up. It is shown nowhere: the generator redraws the pair
-  whenever the keyed value equals any percentage displayed for that variant in a percent column. Choices: the pooled
-  percentage; the mean of the two samples' percentages (the classic error, kept only when it differs from the key); the
-  summed counts read as a percent; and the first sample's percentage alone. All four values are distinct. It stays within
-  the boundary (basic proportion arithmetic; no allele frequency).
+  whenever the keyed value equals any percentage displayed for that variant in a percent column. The pair and variant are
+  chosen when the scenario is drawn (and stored), so the scenario is redrawn if no hidden pooled value with enough wrong
+  answers exists, and `represent_distribution` never repeats the statement that equals the pooled key. Choices: the pooled
+  percentage and three wrong answers drawn from the classic errors: the mean of the two samples' percentages, the summed
+  counts read as a percent (only when 99 or less, since a percent above 100 would cue the key), either sample's percentage
+  alone, and the other variant's pooled percentage. All four values are distinct. It stays within the boundary (basic
+  proportion arithmetic; no allele frequency).
 - **`analyze_distribution_shift`** shows the table (with percent columns) and the chart for the stored trap window
   `(i, i+1)` and asks which statement about the **favoured variant's share of the sample** is supported. Choices share one
-  form, "[Variant]'s share of the sample [rose / fell / did not change] by about [d] percentage points from sample time i to
-  sample time i+1, [clause about its count]": the key (rose by the true difference of the two rounded percentages, while its
-  count fell); the raw-count trap (fell, "because its count fell"); the other variant claimed to have risen by the same
-  amount; and no change "because the total sampled changed". It states a difference, never one of the two percentages
-  alone.
-- **`interpret_fitness_rate`** shows the fitness table only and asks about **either survival rate or offspring per starter**
+  form, "The share of [variant] in the sample [rose / fell / did not change] by about [d] percentage points from sample time i
+  to sample time i+1, and its count went from [x] to [y]" (the count facts are true in every choice): the key (the favoured
+  variant rose by the true difference of the two rounded percentages, while its count fell); the raw-count trap (the
+  favoured variant "fell" by the same amount); the other variant claimed to have risen by that amount; and no change (0
+  points). It states a difference, never one of the two percentages alone.
+- **`interpret_fitness_rate`** shows the fitness table only (its stem calls it the survival and offspring table) and asks about **either survival rate or offspring per starter**
   (drawn). Choices: the favoured variant had the higher rate; the other variant had the higher rate (the raw-count trap
   whenever `trap` is set, because that variant then has more survivors); the two rates were the same; and the rates cannot
   be compared because the groups started with different numbers. Exactly one is true in every draw. Each rationale cites the
@@ -169,10 +172,9 @@
   both variants, the stated condition and the displayed starting group sizes (the `started` numbers, which no item keys on),
   in three parallel clauses of similar length ("[heritability clause], [evidence clause], so [conclusion]"). Key: the trait
   is passed from parents to offspring, and under the stated condition the two groups (named, with their starting sizes)
-  differed in survival and reproduction, so the rise in the named variant's share is evidence of natural selection.
+  differed in how well they survived and reproduced, so the rise in the named variant's share is evidence of natural selection.
   Distractors: the need-based misconception (individuals in the group developed the trait because they needed it under the
-  condition); evidence that contradicts the tables (the two groups, with their sizes, survived and reproduced at the same
-  rates); and the heritability contradiction (the trait is not passed from parents to offspring). **No choice states a
+  condition); evidence that contradicts the tables (the two groups, with their sizes, survived and reproduced equally well); and the heritability contradiction (the trait is not passed from parents to offspring). **No choice states a
   survival or offspring rate, a percentage, a points change, or which variant did better**, so this item does not answer
   `interpret_fitness_rate`, `calculate_proportion` or `analyze_distribution_shift`; the displayed starting sizes may appear
   because no item's key is a starting size. Wording says the trait is passed on, never that organisms "are heritable".
PATCH
git diff --stat
```

Expected: two files changed.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md docs/superpowers/plans/2026-09-29-coverage-roadmap.md
git commit -m "docs: align the B-LS4-3 spec and the coverage roadmap with the 1.1.0 build

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Record it, run everything, hand over

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Update HANDOFF.md**

Run this from the repository root. Each replacement asserts that its old text is present exactly once.

```bash
python3 - <<'EOF'
p = "HANDOFF.md"
s = open(p).read()


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:60])
    s = s.replace(old, new)


rep(
    """1. **Merge the revert PR for B-LS4-3, then redo Biology 2 B-LS4-3** (statistics and distributions of traits). The first build was
   withdrawn; see "Withdrawn family" above for the defects and the conditions for bringing it back as 1.1.0.
""",
    """1. **Biology 2 B-LS4-3 redo: built on branch `feat/bls4-3-redo`, awaiting a fresh-context review, then Brandon's explicit yes to
   merge and a separate yes to deploy.** It is `trait-distribution-shifts` 1.1.0. See "Withdrawn family" for why 1.0.0 was
   pulled and `docs/superpowers/specs/2026-10-04-trait-distribution-shifts-design.md` for the design.
""",
)
rep(
    """mutation. Then a fresh review, then Brandon's explicit yes to merge and again to deploy.

## Results tracking and linked variants""",
    """mutation. Then a fresh review, then Brandon's explicit yes to merge and again to deploy.

Status (2026-10-05): the redo is built and tested on `feat/bls4-3-redo` (independent tests recompute truth from the displayed
tables; 455 backend tests). Not merged, not deployed, and not yet reviewed by a fresh context.

## Results tracking and linked variants""",
)
open(p, "w").write(s)
EOF
git diff --stat HANDOFF.md
```

Expected: one file changed.

- [ ] **Step 2: Full verification**

```bash
cd backend
/home/brandon/apps/science-bank/backend/.venv/bin/ruff check app tests
pytest -q -p no:cacheprovider
```

Expected: ruff clean; **455 passed, zero skipped** (429 existing plus 20 in `test_trait_distribution_shifts.py` plus the new API and engine-matrix cases).

- [ ] **Step 3: Commit and stop the test database**

```bash
cd .. && git add HANDOFF.md && git commit -m "docs: record the B-LS4-3 redo in HANDOFF

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
docker stop sb-testdb
git status --short   # Expected: clean
git log --oneline origin/main..HEAD
```

- [ ] **Step 4: Stop and hand over**

Report to Brandon: what was built, the test counts, the Review Focus items that still need a human read (a few full sets, the support item's choice pattern), and what was not verified (a real browser; how the two-series line chart looks in print). Then run the fresh-context review of the whole branch. Merge and deploy wait for his explicit yes for each. Do not push before he says so.
