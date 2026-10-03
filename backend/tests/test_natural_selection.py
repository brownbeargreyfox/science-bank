"""Independent checks for natural-selection-trend (B-LS4-4).

Which variant each environment favours is typed here, not read from the module under test; every item key is recomputed
from the numbers in the displayed tables.
"""

import json
import re

from app.services.engine.core import Rng
from app.services.engine.family import generate_set
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
        assert (
            _correct(q) == "The variant that was more common before the change will tend to become more common again."
        )
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
        for phrase in (
            "heritable variation",
            "survived and reproduced more",
            "did not change their traits because they needed to",
        ):
            assert phrase in answer.lower()
        assert variants[winner]["noun"] not in q["stem"] and variants[loser]["noun"] not in q["stem"]  # no leak
        assert "not as individuals changing because they need to" in q["stem"]
        assert q["explanation"].count("(1)") == 1 and "(4)" in q["explanation"]
