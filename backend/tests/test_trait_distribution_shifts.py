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
