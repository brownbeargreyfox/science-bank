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
