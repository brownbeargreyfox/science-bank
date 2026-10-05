"""Independent checks for the Biology 2 B-LS4-3 trait-distribution family."""

import json
from collections import Counter

from app.services.engine.core import Rng
from app.services.engine.family import generate_set
from app.services.families import trait_distribution_shifts as tds

SEEDS = [f"tds-{i}" for i in range(200)]
FAVORS = {"beetles": "a", "finches": "b", "minnows": "a", "shrubs": "b", "marsh_grass": "a", "lizards": "b"}
TYPES = {
    "beetles": "anatomical",
    "finches": "anatomical",
    "minnows": "behavioral",
    "shrubs": "anatomical",
    "marsh_grass": "physiological",
    "lizards": "physiological",
}


def _scenario(seed: str) -> dict:
    return tds.draw_scenario(Rng("scenario", seed))


def _set(seed: str, *keys: str) -> dict:
    return generate_set(tds.TraitDistributionShifts(), seed, len(keys), template_keys=list(keys))


def _only(out: dict, key: str) -> dict:
    return next(
        question for group in out["groups"] for question in group["questions"] if question["template_key"] == key
    )


def _correct(question: dict) -> str:
    return next(choice["text"] for choice in question["choices"] if choice["correct"])


def _tables(out: dict) -> dict[str, dict]:
    return {table["caption"]: table for table in out["groups"][0]["stimulus"]["tables"]}


def _distribution_table(out: dict) -> dict:
    return next(table for caption, table in _tables(out).items() if caption.startswith("Trait distribution"))


def _fitness_table(out: dict) -> dict:
    return next(table for caption, table in _tables(out).items() if caption.startswith("Survival and offspring"))


def test_case_bank_has_independent_favored_variants_and_trait_types():
    assert set(tds.CASES) == set(FAVORS) == set(TYPES)
    for key, case in tds.CASES.items():
        assert case["favors"] == FAVORS[key]
        assert case["trait_type"] == TYPES[key]
        assert set(case["variants"]) == {"a", "b"}
        assert case["condition"].endswith(".") and case["intro"].endswith(".")
    assert set(FAVORS.values()) == {"a", "b"}
    assert set(TYPES.values()) == {"anatomical", "behavioral", "physiological"}


def test_distribution_rows_and_percentages_are_valid_and_include_a_count_trap():
    traps = 0
    for seed in SEEDS:
        scenario = _scenario(seed)
        json.dumps(scenario)
        rows, favored = scenario["rows"], FAVORS[scenario["case"]]
        assert [row["time"] for row in rows] == [1, 2, 3, 4]
        assert len({row["total"] for row in rows}) == 4
        pcts = []
        for row in rows:
            assert 80 <= row["total"] <= 140 and row["a"] + row["b"] == row["total"]
            assert all(2 <= row[v] <= row["total"] - 2 for v in ("a", "b"))
            pcts.append(round(100 * row[favored] / row["total"]))
        assert pcts[-1] - pcts[0] >= 15
        assert min(after - before for before, after in zip(pcts, pcts[1:])) >= 3
        counts = [row[favored] for row in rows]
        traps += any(after < before for before, after in zip(counts, counts[1:]))
    assert traps == len(SEEDS)


def test_fitness_rates_are_valid_and_both_raw_survivor_states_occur():
    traps = 0
    for seed in SEEDS:
        scenario = _scenario(seed)
        favored = FAVORS[scenario["case"]]
        rows = {row["variant"]: row for row in scenario["fitness"]["rows"]}
        assert set(rows) == {"a", "b"}
        assert rows["a"]["started"] != rows["b"]["started"]
        assert all(40 <= row["started"] <= 90 and row["started"] % 5 == 0 for row in rows.values())
        assert all(0 <= row["survived"] <= row["started"] and row["offspring"] >= 0 for row in rows.values())
        other = "b" if favored == "a" else "a"
        survival = {variant: row["survived"] / row["started"] for variant, row in rows.items()}
        offspring = {variant: row["offspring"] / row["started"] for variant, row in rows.items()}
        assert survival[favored] - survival[other] >= 0.15
        assert offspring[favored] - offspring[other] >= 0.20
        raw_trap = rows[favored]["survived"] < rows[other]["survived"]
        assert scenario["fitness"]["trap"] == raw_trap
        traps += raw_trap
    assert 60 <= traps <= 140


def test_family_binding_templates_and_selected_stimuli():
    family = tds.TraitDistributionShifts()
    assert family.version == "1.0.0"
    assert [(binding.state, binding.course_slug, binding.code) for binding in family.bindings] == [
        ("SC", "biology-2", "B-LS4-3")
    ]
    assert {
        template.key: (template.dok, template.observable_category, template.observable_index)
        for template in family.templates
    } == {
        "represent_distribution": (1, "organizing_data", 0),
        "calculate_proportion": (1, "identifying_relationships", 0),
        "analyze_distribution_shift": (2, "identifying_relationships", 0),
        "interpret_fitness_rate": (2, "interpreting_data", 0),
        "support_selection_claim": (2, "interpreting_data", 1),
        "explain_shift_with_data": (3, "interpreting_data", 2),
    }
    distribution = _set("dist-only", "calculate_proportion")["groups"][0]["stimulus"]
    assert len(distribution["tables"]) == len(distribution["charts"]) == 1
    fitness = _set("fitness-only", "interpret_fitness_rate")["groups"][0]["stimulus"]
    assert len(fitness["tables"]) == 1 and fitness["charts"] == []
    both = _set("both", "support_selection_claim")["groups"][0]["stimulus"]
    assert len(both["tables"]) == 2 and both["charts"][0]["table_index"] == 0


def test_distribution_chart_is_computed_from_the_displayed_table():
    out = _set("chart", "represent_distribution")
    table = _distribution_table(out)
    chart = out["groups"][0]["stimulus"]["charts"][0]
    assert chart["series"] and {series["key"] for series in chart["series"]} == {"a_pct", "b_pct"}
    for row in table["rows"]:
        assert row["a_pct"] == round(100 * row["a"] / row["total"])
        assert row["b_pct"] == round(100 * row["b"] / row["total"])


def test_calculate_and_distribution_keys_follow_displayed_numbers():
    for seed in SEEDS:
        out = _set(seed, "calculate_proportion", "represent_distribution", "analyze_distribution_shift")
        params = out["groups"][0]["parameters"]
        favored = FAVORS[params["case"]]
        labels = {column["label"]: column["key"] for column in _distribution_table(out)["columns"]}
        for key in ("calculate_proportion", "represent_distribution"):
            question = _only(out, key)
            blob = question["stem"] + " " + _correct(question)
            variant = max((label for label in labels if label.lower() in blob.lower()), key=len)
            row = next(row for row in _distribution_table(out)["rows"] if f"time {row['time']}" in question["stem"])
            pct = round(100 * row[labels[variant]] / row["total"])
            assert str(pct) in _correct(question)
        question = _only(out, "analyze_distribution_shift")
        first, last = params["rows"][0], params["rows"][-1]
        assert f"{round(100 * first[favored] / first['total'])}%" in _correct(question)
        assert f"{round(100 * last[favored] / last['total'])}%" in _correct(question)


def test_fitness_and_selection_keys_follow_displayed_data():
    for seed in SEEDS:
        out = _set(seed, "interpret_fitness_rate", "support_selection_claim")
        params = out["groups"][0]["parameters"]
        favored = FAVORS[params["case"]]
        table = _fitness_table(out)
        column = {entry["label"]: entry["key"] for entry in table["columns"]}
        labels = {row[column["Variant"]]: row for row in table["rows"]}
        winner = max(labels, key=lambda label: labels[label][column["Survived"]] / labels[label][column["Started"]])
        assert _correct(_only(out, "interpret_fitness_rate")) == f"{winner} had the higher survival rate."
        noun = tds.CASES[params["case"]]["variants"][favored]["noun"]
        assert noun in _correct(_only(out, "support_selection_claim"))


def test_selection_claim_keeps_need_based_change_only_as_a_misconception():
    for seed in SEEDS:
        out = _set(seed, "support_selection_claim")
        question = _only(out, "support_selection_claim")
        stimulus = out["groups"][0]["stimulus"]
        needy = [choice for choice in question["choices"] if "needed" in choice["text"]]
        assert len(needy) == 1 and not needy[0]["correct"]
        assert "need" not in question["stem"].lower()
        assert "need" not in stimulus["title"].lower() + stimulus["intro"].lower()


def test_constructed_response_uses_the_case_type_and_visible_data():
    for seed in SEEDS:
        out = _set(seed, "explain_shift_with_data")
        params = out["groups"][0]["parameters"]
        answer = _only(out, "explain_shift_with_data")["answer"]
        favored = FAVORS[params["case"]]
        first, last = params["rows"][0], params["rows"][-1]
        assert TYPES[params["case"]] in answer
        assert f"{round(100 * first[favored] / first['total'])}%" in answer
        assert f"{round(100 * last[favored] / last['total'])}%" in answer
        assert "parents pass" in answer.lower() and "survival" in answer.lower() and "offspring" in answer.lower()


def test_choices_vary_in_position_and_scope_words_are_absent():
    positions = {
        template.key: Counter()
        for template in tds.TraitDistributionShifts.templates
        if template.question_type == "multiple_choice"
    }
    banned = (
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
    )
    for seed in SEEDS:
        out = generate_set(tds.TraitDistributionShifts(), seed, 6)
        text = []
        for group in out["groups"]:
            stimulus = group["stimulus"]
            text.extend([stimulus["title"], stimulus["intro"]])
            for table in stimulus["tables"]:
                text.append(table["caption"])
                text.extend(column["label"] for column in table["columns"])
            for question in group["questions"]:
                text.extend([question["stem"], question["answer"], question["explanation"]])
                text.extend(choice["text"] + " " + choice["rationale"] for choice in question["choices"])
                if question["question_type"] == "multiple_choice":
                    positions[question["template_key"]][
                        next(choice["label"] for choice in question["choices"] if choice["correct"])
                    ] += 1
        blob = " ".join(text).lower()
        assert not any(word in blob for word in banned)
    for counts in positions.values():
        assert set(counts) == {"A", "B", "C", "D"}
        assert max(counts.values()) <= 80
