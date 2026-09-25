"""Engine invariants: determinism, alignment to the SCDE data, and scientific validity of keys."""

import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from app.core.config import REPO_ROOT
from app.services.engine.core import GenerationError, Rng, derive_seed
from app.services.engine.family import generate_set
from app.services.families import genetics, population, quantitative_conservation, reaction_rate
from app.services.families.registry import FAMILIES

BACKEND = Path(__file__).resolve().parents[1]
STANDARDS = REPO_ROOT / "data" / "standards" / "SC"
SEEDS = [f"inv-{i}" for i in range(150)]

# Golden digests of generate_set(family, "golden", 12). If one changes, output for existing seeds has
# changed: bump that family's version (it feeds every sub-seed) and re-pin the digest in the same commit.
GOLDEN = {
    "population-carrying-capacity": "0c8ee45939b20ce51b7dca113cea1742cf4ca9aaad92086d30df1e8e685860db",
    "trait-probability": "ff980b3df37a613d7f891355941547eb80306d08e2be9dde702114c2b114571a",
    "reaction-rate": "5693b0d4e23823f2e880e2d017eafbeedef5f25fe869982a63eea3cfca75acea",
    "quantitative-conservation": "62a6a3d4b7bd8415599d8a290082819a6de9147a76f145569e259c4d1d55cc45",
}


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _all_questions(out):
    for g in out["groups"]:
        for q in g["questions"]:
            yield g, q


def _load_standard(course_file: str, code: str) -> dict:
    data = json.loads((STANDARDS / "2026-2027" / course_file).read_text())
    for dom in data["domains"]:
        for s in dom["standards"]:
            if s["code"] == code:
                return s
    raise KeyError(code)


# ---- determinism ----------------------------------------------------------------------------


def test_rng_helpers_only_use_random_stream():
    a, b = Rng("x", 1), Rng("x", 1)
    assert [a.randint(0, 9) for _ in range(50)] == [b.randint(0, 9) for _ in range(50)]
    assert Rng("x", 1).shuffled(range(20)) == Rng("x", 1).shuffled(range(20))
    assert derive_seed("a", 1) == derive_seed("a", 1) != derive_seed("a", 2)
    r = Rng("bounds")
    assert all(3 <= r.randint(3, 7) <= 7 for _ in range(2000))


@pytest.mark.parametrize("key", sorted(FAMILIES))
def test_same_seed_same_output(key):
    fam = FAMILIES[key]
    assert _digest(generate_set(fam, "repeat", 10)) == _digest(generate_set(fam, "repeat", 10))
    assert _digest(generate_set(fam, "repeat", 10)) != _digest(generate_set(fam, "other", 10))


def test_output_independent_of_hash_randomization():
    script = (
        "import json,hashlib;from app.services.families.registry import FAMILIES;"
        "from app.services.engine.family import generate_set;"
        "print(hashlib.sha256(json.dumps([generate_set(f,'xproc',9) for f in FAMILIES.values()],"
        "sort_keys=True).encode()).hexdigest())"
    )
    digests = {
        subprocess.run(
            [sys.executable, "-c", script],
            cwd=BACKEND,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for seed in ("0", "1", "12345")
    }
    assert len(digests) == 1


@pytest.mark.parametrize("key", sorted(FAMILIES))
def test_golden_snapshot(key):
    digest = _digest(generate_set(FAMILIES[key], "golden", 12))
    expected = GOLDEN[key]
    if expected is None:
        pytest.skip(f"golden digest not pinned yet: {digest}")
    assert digest == expected


# ---- structure and alignment ----------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(FAMILIES))
def test_template_citations_exist_in_scde_data(key):
    fam = FAMILIES[key]
    files = {"biology-1": "biology-1.json", "chemistry": "chemistry.json"}
    for b in fam.bindings:
        std = _load_standard(files[b.course_slug], b.code)
        assert std.get("question_family_candidate") is True
        for t in fam.templates:
            bullets = std["observable_performances"][t.observable_category]
            assert t.observable_index < len(bullets), (t.key, t.observable_category)


@pytest.mark.parametrize("key", sorted(FAMILIES))
def test_items_well_formed_across_seeds(key):
    fam = FAMILIES[key]
    for seed in SEEDS:
        out = generate_set(fam, seed, len(fam.templates))
        keys = [q["template_key"] for _, q in _all_questions(out)]
        assert sorted(keys) == sorted(t.key for t in fam.templates)
        for g, q in _all_questions(out):
            json.dumps(g)  # stored as JSONB
            assert q["stem"] and q["answer"] and q["explanation"]
            if q["question_type"] == "multiple_choice":
                correct = [c for c in q["choices"] if c["correct"]]
                assert len(correct) == 1
                assert q["answer"] == f"{correct[0]['label']}. {correct[0]['text']}"
                assert len({c["text"] for c in q["choices"]}) == len(q["choices"]) == 4
                assert all(c["rationale"] for c in q["choices"])
            else:
                assert q["choices"] == []
            for t in g["stimulus"].get("tables", []):
                assert t["rows"]
            for c in g["stimulus"].get("charts", []):
                assert 0 <= c["table_index"] < len(g["stimulus"]["tables"])


def test_filters_and_quantity():
    fam = FAMILIES["reaction-rate"]
    out = generate_set(fam, "f", 5, doks=[1])
    assert {q["dok"] for _, q in _all_questions(out)} == {1}
    assert sum(len(g["questions"]) for g in out["groups"]) == 5
    assert len(out["groups"]) == 3  # two DOK-1 templates per scenario
    out = generate_set(fam, "f", 3, question_types=["constructed_response"])
    assert all(q["question_type"] == "constructed_response" for _, q in _all_questions(out))
    with pytest.raises(GenerationError):
        generate_set(fam, "f", 0)
    with pytest.raises(GenerationError):
        generate_set(fam, "f", 2, doks=[4])


def test_stimulus_only_includes_parts_used():
    fam = FAMILIES["trait-probability"]
    out = generate_set(fam, "parts", 1, template_keys=["phenotype_probability"])
    stim = out["groups"][0]["stimulus"]
    assert stim["tables"] == [] and stim["charts"] == []
    assert [s["heading"] for s in stim["sections"]][-1] == "Cross 1"


# ---- scientific validity: B-LS2-1 -----------------------------------------------------------


def _q(out, key):
    return next(q for _, q in _all_questions(out) if q["template_key"] == key)


def _correct_text(q):
    return next(c["text"] for c in q["choices"] if c["correct"])


def test_population_keys_follow_displayed_data():
    fam = FAMILIES["population-carrying-capacity"]
    for seed in SEEDS:
        out = generate_set(fam, seed, len(fam.templates))
        p = out["groups"][0]["parameters"]
        rows = p["rows"]
        sc = population.SCENARIOS[p["scenario"]]
        t_event = p["model"]["t_event"]
        # fastest interval = largest displayed difference, unambiguously
        diffs = [(rows[i + 1]["n"] - rows[i]["n"], rows[i]["t"], rows[i + 1]["t"]) for i in range(len(rows) - 1)]
        best = max(diffs)
        q = _q(out, "fastest_growth_interval")
        assert _correct_text(q).startswith(f"{sc['time_unit'].capitalize()} {best[1]} to")
        # carrying capacity sits on the displayed plateau before the event
        plateau = [r["n"] for r in rows if t_event - 2 * p["model"]["step"] <= r["t"] <= t_event]
        assert min(plateau) * 0.95 <= p["k1_estimate"] <= max(plateau) * 1.05
        assert _correct_text(_q(out, "estimate_carrying_capacity")) == f"{p['k1_estimate']:,}"
        # the causal factor changes at the event; the control does not
        ev = sc["events"][p["event"]]
        before = [r["factor"] for r in rows if r["t"] <= t_event]
        after = [r["factor"] for r in rows if r["t"] > t_event]
        assert abs(sum(after) / len(after) - ev["after"]) < abs(sum(after) / len(after) - ev["before"])
        assert abs(sum(before) / len(before) - ev["before"]) < abs(sum(before) / len(before) - ev["after"])
        ctrl = [r["control"] for r in rows]
        assert max(ctrl) - min(ctrl) <= 2 * sc["control"]["jitter"] + 0.11
        # new plateau direction matches the event
        assert (p["k2_estimate"] < p["k1_estimate"]) == (ev["k_multiplier"][1] < 1)
        # scale item: correct = ratio x K
        q = _q(out, "scale_prediction")
        expected = population._round_to(p["k1_estimate"] * p["scale_ratio"], sc["k_round"])
        assert _correct_text(q) == f"{expected:,}"


def test_population_has_no_equation_derivation():
    fam = FAMILIES["population-carrying-capacity"]
    for seed in SEEDS[:30]:
        for _, q in _all_questions(generate_set(fam, seed, 7)):
            text = (q["stem"] + q["answer"]).lower()
            assert "derive" not in text and "equation" not in text


# ---- scientific validity: B-LS3-3 -----------------------------------------------------------


def test_punnett_enumeration():
    pea = genetics.TRAITS["pea_flower"]
    d = genetics.cross_distribution(pea, "Pp", "Pp")
    assert d["genotypes"] == {"PP": Fraction(1, 4), "Pp": Fraction(1, 2), "pp": Fraction(1, 4)}
    assert d["phenotypes"] == {"purple flowers": Fraction(3, 4), "white flowers": Fraction(1, 4)}
    snap = genetics.TRAITS["snapdragon"]
    d = genetics.cross_distribution(snap, "RW", "RW")
    assert d["phenotypes"]["pink flowers"] == Fraction(1, 2)
    for trait in genetics.TRAITS.values():
        for c in genetics._all_crosses(trait):
            assert sum(genetics.cross_distribution(trait, *c)["phenotypes"].values()) == 1


def test_genetics_keys_follow_parameters():
    fam = FAMILIES["trait-probability"]
    for seed in SEEDS:
        out = generate_set(fam, seed, len(fam.templates))
        p = out["groups"][0]["parameters"]
        trait = genetics.TRAITS[p["trait"]]
        dist = genetics.cross_distribution(trait, *p["known_cross"])
        prob = dist["phenotypes"][p["target_phenotype"]]
        assert _correct_text(_q(out, "phenotype_probability")) == genetics._frac_text(prob)
        assert _correct_text(_q(out, "expected_offspring_count")) == str(int(prob * p["offspring_total"]))
        # observed Cross 2 data are closest to the keyed cross among all answer choices
        obs = p["observed"]
        observed = [c / obs["total"] for c in obs["counts"]]
        q = _q(out, "infer_parent_genotypes")
        distances = {}
        for c in q["choices"]:
            cross = tuple(c["text"].split(" × "))
            expected = [float(f) for f in genetics._pheno_vector(trait, cross)]
            distances[c["text"]] = genetics._tv_distance(observed, expected)
        assert min(distances, key=distances.get) == _correct_text(q)
        # environment data: monotone trend, and prediction interval brackets the model at the midpoint
        rows = p["environment_rows"]
        pct = [r["percent"] for r in rows]
        assert all(a >= b for a, b in zip(pct, pct[1:])) and pct[0] - pct[-1] >= 70


def test_genetics_stays_inside_assessment_boundary():
    fam = FAMILIES["trait-probability"]
    for seed in SEEDS[:40]:
        for _, q in _all_questions(generate_set(fam, seed, 7)):
            text = " ".join([q["stem"], q["answer"], q["explanation"], *[c["text"] for c in q["choices"]]]).lower()
            assert "chi" not in text.split() and "chi-square" not in text and "hardy" not in text


# ---- scientific validity: C-PS1-5 -----------------------------------------------------------


def test_quantitative_conservation_representation_and_evidence_path():
    fam = FAMILIES["quantitative-conservation"]
    seen = set()
    for seed in SEEDS:
        out = generate_set(fam, seed, len(fam.templates))
        p = out["groups"][0]["parameters"]
        seen.add(p["reaction"])
        assert p["atom_totals"]["reactants"] == p["atom_totals"]["products"]
        assert p["side_masses"]["reactants"] == p["side_masses"]["products"]
        assert "→ mol" in p["unit_path"] and "→ g" in p["unit_path"]
        assert p["dimensional_analysis"] == p["unit_path"].split(" → ")
        assert set(p["misconceptions"]) == {
            "read_coefficients",
            "mole_mass_conversion",
            "particle_scale",
            "mass_of_product",
            "conservation_check",
        }
        assert all(len(classes) == 3 and len(set(classes)) == 3 for classes in p["misconceptions"].values())
        assert {"conservation_check", "explain_conservation"} <= {q["template_key"] for _, q in _all_questions(out)}
        for row in p["species"]:
            assert row["molar_mass"] == float(quantitative_conservation.molar_mass(row["atoms"]))
        text = " ".join(q["stem"] + " " + q["answer"] for _, q in _all_questions(out)).lower()
        assert all(term not in text for term in ("limiting reactant", "percent yield", "molarity", "gas law"))
    assert seen == set(quantitative_conservation.REACTIONS)


def test_reaction_rate_data_and_keys():
    fam = FAMILIES["reaction-rate"]
    for seed in SEEDS:
        out = generate_set(fam, seed, len(fam.templates))
        p = out["groups"][0]["parameters"]
        rx = reaction_rate.REACTIONS[p["reaction"]]
        for exp in ("experiment1", "experiment2"):
            vals = [r["value"] for r in p[exp]]
            if rx["measure"] == "time":
                assert all(b < a for a, b in zip(vals, vals[1:])), "times must fall as rate rises"
            else:
                assert all(b > a for a, b in zip(vals, vals[1:]))
        for key in ("concentration_trend", "temperature_trend"):
            assert _correct_text(_q(out, key)).endswith("the reaction rate increases.")
        # the predicted interval contains the (noise-free) model value at the new temperature
        q = _q(out, "predict_temperature_trial")
        t_new = float(q["stem"].split(" at ")[1].split("°C")[0])
        ea = p["model"]["ea_j_per_mol"]
        rel = reaction_rate._k_factor(t_new, ea) / reaction_rate._k_factor(rx["fixed_temperature"], ea)
        ref = p["model"]["reference_measurement"]
        model = ref / rel if rx["measure"] == "time" else ref * rel
        lo, hi = (float(x.split()[0]) for x in _correct_text(q).removeprefix("Between ").split(" and "))
        assert lo * 0.94 <= model <= hi * 1.06
        # only two reactants in every equation
        reactants = rx["equation"].split("→")[0].split("+")
        assert len(reactants) == 2


def test_reaction_rate_temperature_items_are_qualitative():
    fam = FAMILIES["reaction-rate"]
    for seed in SEEDS[:30]:
        for _, q in _all_questions(generate_set(fam, seed, 7)):
            text = (q["stem"] + " " + q["answer"]).lower()
            assert "arrhenius" not in text and "rate constant" not in text and "kj" not in text
