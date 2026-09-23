"""B-LS3-3 (Biology 1): probability and distribution of expressed traits.

Part A — a monohybrid cross with known parents (Punnett-square probability, ratios, expected counts).
Part B — offspring counts from parents of unknown genotype (compare the observed distribution to
         expected ones qualitatively; no chi-square, per the state assessment boundary).
Part C — genetically identical organisms raised under different environmental conditions, showing
         environmental influence on trait expression (the DCI LS3.B emphasis).

Every probability is computed by enumerating the Punnett square; every observed count shown to
students comes from a seeded draw that is checked so the intended conclusion is unambiguous.
No Hardy-Weinberg content.
"""

import math
from fractions import Fraction
from itertools import product
from typing import Any

from app.services.engine.core import (
    Binding,
    DraftChoice,
    DraftQuestion,
    GenerationError,
    Rng,
    TemplateSpec,
    fmt_pct,
)
from app.services.engine.family import QuestionFamily

# Trait catalog. `dominant`/`recessive` alleles for complete dominance; for incomplete dominance and
# codominance, `alleles` are two uppercase letters and each genotype has its own phenotype.
TRAITS: dict[str, dict[str, Any]] = {
    "pea_flower": {
        "mode": "complete",
        "organism": "pea plants",
        "trait": "flower color",
        "dominant": "P",
        "recessive": "p",
        "dominant_phenotype": "purple flowers",
        "recessive_phenotype": "white flowers",
    },
    "pea_seed": {
        "mode": "complete",
        "organism": "pea plants",
        "trait": "seed shape",
        "dominant": "R",
        "recessive": "r",
        "dominant_phenotype": "round seeds",
        "recessive_phenotype": "wrinkled seeds",
    },
    "guinea_pig_coat": {
        "mode": "complete",
        "organism": "guinea pigs",
        "trait": "coat color",
        "dominant": "B",
        "recessive": "b",
        "dominant_phenotype": "black coats",
        "recessive_phenotype": "white coats",
    },
    "snapdragon": {
        "mode": "incomplete",
        "organism": "snapdragon plants",
        "trait": "flower color",
        "alleles": ("R", "W"),
        "phenotypes": {"RR": "red flowers", "RW": "pink flowers", "WW": "white flowers"},
        "allele_note": "R = allele for red pigment, W = allele for no pigment. Neither allele is dominant (incomplete dominance).",
    },
    "roan_cattle": {
        "mode": "codominant",
        "organism": "shorthorn cattle",
        "trait": "coat color",
        "alleles": ("R", "W"),
        "phenotypes": {"RR": "red coats", "RW": "roan coats", "WW": "white coats"},
        "allele_note": "R = allele for red hair, W = allele for white hair. Both alleles are expressed in heterozygotes (codominance), producing a roan coat with a mix of red and white hairs.",
    },
}

ENVIRONMENTS: dict[str, dict[str, Any]] = {
    "hydrangea_ph": {
        "organism": "hydrangea plants",
        "setup": (
            "A gardener grew hydrangea plants that were all propagated from cuttings of a single parent plant, "
            "so every plant is genetically identical. Groups of plants were grown in soils with different pH."
        ),
        "variable": "Soil pH",
        "levels": [4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5],
        "level_decimals": 1,
        "group_size": 20,
        "trait_noun": "blue flowers",
        "trait_verb": "have blue flowers",
        "trait_past": "had blue flowers",
        "unit_suffix": "",
        "count_label": "Plants with blue flowers",
        "midpoint_range": (5.7, 6.2),
        "spread_range": (0.22, 0.32),
        "decreasing": True,
        "mechanism": (
            "In acidic soil, aluminum in the soil is more available to the roots, and the flower pigment binds "
            "aluminum and appears blue; in less acidic soil the same pigment appears pink"
        ),
    },
    "himalayan_rabbit": {
        "organism": "Himalayan rabbits",
        "setup": (
            "All of the rabbits in this study are homozygous for the Himalayan coat allele. A small patch of white "
            "fur was shaved on each rabbit's back, and the patch was kept at a controlled skin temperature while the "
            "fur grew back."
        ),
        "variable": "Skin temperature (°C)",
        "levels": [20, 23, 26, 29, 32, 35, 38],
        "level_decimals": 0,
        "group_size": 12,
        "trait_noun": "black fur regrown",
        "trait_verb": "regrow black fur",
        "trait_past": "regrew black fur",
        "unit_suffix": "°C",
        "count_label": "Rabbits whose patch grew back black",
        "midpoint_range": (30.0, 33.0),
        "spread_range": (1.0, 1.5),
        "decreasing": True,
        "mechanism": (
            "The Himalayan allele codes for a pigment-making enzyme that only works at cooler temperatures, so the "
            "same genotype produces black fur where the skin is cool and white fur where it is warm"
        ),
    },
}

OFFSPRING_TOTALS = (40, 80, 120, 160, 200, 240, 400)


def _genotype(a: str, b: str, order: str) -> str:
    return "".join(sorted((a, b), key=order.index))


def _alleles(trait: dict) -> tuple[str, str]:
    return (trait["dominant"], trait["recessive"]) if trait["mode"] == "complete" else trait["alleles"]


def _all_genotypes(trait: dict) -> list[str]:
    x, y = _alleles(trait)
    return [x + x, x + y, y + y]


def _phenotype(trait: dict, genotype: str) -> str:
    if trait["mode"] == "complete":
        return trait["dominant_phenotype"] if trait["dominant"] in genotype else trait["recessive_phenotype"]
    return trait["phenotypes"][genotype]


def _phenotype_order(trait: dict) -> list[str]:
    return list(dict.fromkeys(_phenotype(trait, g) for g in _all_genotypes(trait)))


def cross_distribution(trait: dict, p1: str, p2: str) -> dict[str, dict[str, Fraction]]:
    """Enumerate the 2x2 Punnett square."""
    order = "".join(_alleles(trait))
    genos: dict[str, Fraction] = {}
    for a, b in product(p1, p2):
        g = _genotype(a, b, order)
        genos[g] = genos.get(g, Fraction(0)) + Fraction(1, 4)
    phenos: dict[str, Fraction] = {}
    for g, f in genos.items():
        ph = _phenotype(trait, g)
        phenos[ph] = phenos.get(ph, Fraction(0)) + f
    return {"genotypes": genos, "phenotypes": phenos}


def _all_crosses(trait: dict) -> list[tuple[str, str]]:
    gs = _all_genotypes(trait)
    return [(gs[i], gs[j]) for i in range(3) for j in range(i, 3)]


def _pheno_vector(trait: dict, cross: tuple[str, str]) -> tuple[Fraction, ...]:
    dist = cross_distribution(trait, *cross)["phenotypes"]
    return tuple(dist.get(ph, Fraction(0)) for ph in _phenotype_order(trait))


def _distinct_crosses(trait: dict) -> list[tuple[str, str]]:
    """One representative cross per distinct expected phenotype distribution."""
    seen: dict[tuple, tuple[str, str]] = {}
    for c in _all_crosses(trait):
        seen.setdefault(_pheno_vector(trait, c), c)
    return list(seen.values())


def _frac_text(f: Fraction) -> str:
    if f == 0:
        return "0 (0%)"
    if f == 1:
        return "1 (100%)"
    return f"{f.numerator}/{f.denominator} ({fmt_pct(float(f))})"


def _ratio_text(trait: dict, genos: dict[str, Fraction]) -> str:
    parts = [(g, int(genos[g] * 4)) for g in _all_genotypes(trait) if genos.get(g)]
    if len(parts) == 1:
        return f"All {parts[0][0]}"
    divisor = math.gcd(*(n for _, n in parts))
    return " : ".join(f"{n // divisor} {g}" for g, n in parts)


def _var(env: dict) -> str:
    return env["variable"].split(" (")[0].lower()


def _level(env: dict, level: float) -> str:
    return f"{level:g}{env['unit_suffix']}"


def _binomial(rng: Rng, n: int, p: float) -> int:
    return sum(1 for _ in range(n) if rng.random() < p)


def _multinomial(rng: Rng, n: int, probs: list[float]) -> list[int]:
    counts = [0] * len(probs)
    for _ in range(n):
        u, acc = rng.random(), 0.0
        for i, p in enumerate(probs):
            acc += p
            if u < acc or i == len(probs) - 1:
                counts[i] += 1
                break
    return counts


def _tv_distance(a: list[float], b: list[float]) -> float:
    return 0.5 * sum(abs(x - y) for x, y in zip(a, b))


PART_A = {"phenotype_probability", "genotypic_ratio", "expected_offspring_count"}
PART_B = {"infer_parent_genotypes"}
PART_C = {"environment_relationship", "environment_prediction", "explain_variation"}


class TraitProbability(QuestionFamily):
    key = "trait-probability"
    version = "1.0.0"
    title = "Trait probability and distribution"
    description = (
        "Monohybrid crosses (complete dominance, incomplete dominance, codominance) with Punnett-square "
        "probabilities, observed offspring distributions compared qualitatively to expected ones, and a "
        "genetically-identical population raised under different environmental conditions."
    )
    stimulus_kind = "trait_distribution"
    bindings = (Binding("SC", "biology-1", "B-LS3-3"),)
    templates = (
        TemplateSpec("phenotype_probability", "Probability of a phenotype", 1, "multiple_choice", "organizing_data", 1),
        TemplateSpec("genotypic_ratio", "Expected genotypic ratio", 1, "multiple_choice", "organizing_data", 0),
        TemplateSpec(
            "expected_offspring_count", "Expected number of offspring", 2, "multiple_choice", "organizing_data", 1
        ),
        TemplateSpec(
            "infer_parent_genotypes",
            "Infer parents from an offspring distribution",
            2,
            "multiple_choice",
            "organizing_data",
            0,
        ),
        TemplateSpec(
            "environment_relationship",
            "Environment and trait expression",
            2,
            "multiple_choice",
            "identifying_relationships",
            0,
        ),
        TemplateSpec(
            "environment_prediction", "Predict a trait distribution", 2, "multiple_choice", "interpreting_data", 0
        ),
        TemplateSpec(
            "explain_variation", "Explain variation in a trait", 3, "constructed_response", "interpreting_data", 1
        ),
    )

    # ---- scenario ---------------------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        trait_key = rng.choice(sorted(TRAITS))
        trait = TRAITS[trait_key]
        crosses = _all_crosses(trait)
        # Part A: any cross that is not trivially uniform (homozygous x same homozygous).
        known = rng.choice([c for c in crosses if not (c[0] == c[1] and c[0][0] == c[0][1])])
        total = rng.choice(OFFSPRING_TOTALS)
        target_phenotype = rng.choice(sorted(cross_distribution(trait, *known)["phenotypes"]))

        # Part B: an informative unknown cross, with a sample whose observed distribution is
        # clearly closer to its own expectation than to any other distinct cross.
        distinct = _distinct_crosses(trait)
        informative = [c for c in distinct if sum(1 for f in _pheno_vector(trait, c) if f) > 1]
        unknown = rng.choice(informative)
        order = _phenotype_order(trait)
        for _ in range(50):
            n_obs = rng.randint(12, 30) * 10
            counts = _multinomial(rng, n_obs, [float(f) for f in _pheno_vector(trait, unknown)])
            obs = [c / n_obs for c in counts]
            d_true = _tv_distance(obs, [float(f) for f in _pheno_vector(trait, unknown)])
            d_other = min(
                _tv_distance(obs, [float(f) for f in _pheno_vector(trait, c)]) for c in distinct if c != unknown
            )
            if d_true < 0.5 * d_other:
                break
        else:
            raise GenerationError("could not draw an unambiguous offspring sample")

        # Part C: environment dataset with a clearly monotonic trend.
        env_key = rng.choice(sorted(ENVIRONMENTS))
        env = ENVIRONMENTS[env_key]
        mid = rng.uniform(*env["midpoint_range"])
        spread = rng.uniform(*env["spread_range"])
        n = env["group_size"]
        for _ in range(50):
            env_rows = []
            for level in env["levels"]:
                p = 1 / (1 + math.exp((level - mid) / spread))
                if not env["decreasing"]:
                    p = 1 - p
                env_rows.append({"level": level, "present": _binomial(rng, n, p), "total": n})
            present = [r["present"] for r in env_rows]
            monotone = (
                all(a >= b for a, b in zip(present, present[1:]))
                if env["decreasing"]
                else all(a <= b for a, b in zip(present, present[1:]))
            )
            if monotone and abs(present[0] - present[-1]) >= 0.7 * n:
                break
        else:
            raise GenerationError("could not draw a clear environmental trend")
        for r in env_rows:
            r["percent"] = round(100 * r["present"] / r["total"])

        return {
            "trait": trait_key,
            "known_cross": list(known),
            "offspring_total": total,
            "target_phenotype": target_phenotype,
            "unknown_cross": list(unknown),
            "observed": {"phenotypes": order, "counts": counts, "total": n_obs},
            "environment": env_key,
            "environment_model": {"midpoint": round(mid, 3), "spread": round(spread, 3)},
            "environment_rows": env_rows,
            "cr_level_index": rng.choice(
                [i for i, r in enumerate(env_rows) if 0 < r["present"] < r["total"]] or list(range(len(env_rows)))
            ),
            "cr_plant_count": rng.choice((30, 40, 60)),
        }

    # ---- stimulus ---------------------------------------------------------------------------

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        trait = TRAITS[params["trait"]]
        env = ENVIRONMENTS[params["environment"]]
        keys = set(template_keys)
        sections, tables = [], []
        note = trait.get("allele_note") or (
            f"{trait['dominant']} = dominant allele ({trait['dominant_phenotype']}); "
            f"{trait['recessive']} = recessive allele ({trait['recessive_phenotype']})."
        )
        if keys & (PART_A | PART_B):
            sections.append(
                {
                    "heading": "Inheritance of " + trait["trait"],
                    "text": f"In {trait['organism']}, {trait['trait']} is controlled by one gene. {note}",
                }
            )
        if keys & PART_A:
            p1, p2 = params["known_cross"]
            sections.append(
                {
                    "heading": "Cross 1",
                    "text": f"A parent with genotype {p1} is crossed with a parent with genotype {p2}.",
                }
            )
        if keys & PART_B:
            obs = params["observed"]
            sections.append(
                {
                    "heading": "Cross 2",
                    "text": (
                        f"Two {trait['organism']} whose genotypes are unknown were crossed several times. "
                        f"Their {obs['total']} offspring are summarized in the table."
                    ),
                    "table_index": len(tables),
                }
            )
            tables.append(
                {
                    "caption": "Cross 2 offspring",
                    "columns": [
                        {"key": "phenotype", "label": "Phenotype"},
                        {"key": "count", "label": "Number of offspring"},
                    ],
                    "rows": [
                        {"phenotype": ph.capitalize(), "count": c} for ph, c in zip(obs["phenotypes"], obs["counts"])
                    ],
                }
            )
        charts = []
        if keys & PART_C:
            sections.append({"heading": "Environment study", "text": env["setup"], "table_index": len(tables)})
            charts.append(
                {
                    "type": "bar",
                    "title": f"Percent that {env['trait_past']}, by {_var(env)}",
                    "x": {"key": "level", "label": env["variable"]},
                    "y": {"label": "Percent (%)", "min": 0, "max": 100},
                    "series": [{"key": "percent", "label": f"% with {env['trait_noun']}"}],
                    "table_index": len(tables),
                }
            )
            tables.append(
                {
                    "caption": f"{env['organism'].capitalize()} raised under different conditions",
                    "columns": [
                        {"key": "level", "label": env["variable"]},
                        {"key": "present", "label": env["count_label"]},
                        {"key": "total", "label": "Total in group"},
                        {"key": "percent", "label": "Percent (%)"},
                    ],
                    "rows": params["environment_rows"],
                }
            )
        title_bits = []
        if keys & (PART_A | PART_B):
            title_bits.append(f"{trait['trait'].capitalize()} in {trait['organism']}")
        if keys & PART_C:
            title_bits.append(f"{env['organism'].capitalize()} and the environment")
        return {"title": "; ".join(title_bits), "intro": "", "sections": sections, "tables": tables, "charts": charts}

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _known(self, params):
        trait = TRAITS[params["trait"]]
        p1, p2 = params["known_cross"]
        return trait, p1, p2, cross_distribution(trait, p1, p2)

    def _punnett_text(self, trait, p1, p2) -> str:
        order = "".join(_alleles(trait))
        boxes = [_genotype(a, b, order) for a in p1 for b in p2]
        return (
            f"Punnett square for {p1} × {p2}: gametes {p1[0]}, {p1[1]} and {p2[0]}, {p2[1]} give the four boxes "
            f"{', '.join(boxes)}."
        )

    def _q_phenotype_probability(self, params, rng: Rng) -> DraftQuestion:
        trait, p1, p2, dist = self._known(params)
        target = params["target_phenotype"]
        p = dist["phenotypes"][target]
        boxes = int(p * 4)
        others = [Fraction(k, 4) for k in range(5) if Fraction(k, 4) != p]
        distractors = rng.sample(others, 3)
        return DraftQuestion(
            stem=f"In Cross 1, what is the probability that an offspring will have {target}?",
            answer=_frac_text(p),
            explanation=(
                f"{self._punnett_text(trait, p1, p2)} {boxes} of the 4 boxes give {target}, so the probability is "
                f"{_frac_text(p)}."
            ),
            choices=[
                DraftChoice(_frac_text(p), True, f"Correct: {boxes} of the 4 Punnett square boxes give {target}."),
                *[
                    DraftChoice(
                        _frac_text(f),
                        False,
                        f"This would mean {int(f * 4)} of 4 boxes give {target}; the square for {p1} × {p2} has {boxes}.",
                    )
                    for f in distractors
                ],
            ],
        )

    def _q_genotypic_ratio(self, params, rng: Rng) -> DraftQuestion:
        trait, p1, p2, dist = self._known(params)
        correct = _ratio_text(trait, dist["genotypes"])
        pool: dict[str, str] = {}
        for c in _all_crosses(trait):
            text = _ratio_text(trait, cross_distribution(trait, *c)["genotypes"])
            if text != correct:
                pool.setdefault(text, f"This is the genotypic ratio for a {c[0]} × {c[1]} cross, not {p1} × {p2}.")
        if trait["mode"] == "complete" and len(dist["phenotypes"]) == 2:
            ph_ratio = " : ".join(
                f"{int(dist['phenotypes'][ph] * 4)} {ph}" for ph in _phenotype_order(trait) if ph in dist["phenotypes"]
            )
            pool[ph_ratio] = "This is a phenotypic ratio (appearance), not a genotypic ratio."
        picks = rng.sample(sorted(pool), 3)
        return DraftQuestion(
            stem="Which genotypic ratio is expected among the offspring of Cross 1?",
            answer=correct,
            explanation=f"{self._punnett_text(trait, p1, p2)} Counting boxes by genotype gives {correct}.",
            choices=[
                DraftChoice(correct, True, "Correct: this counts each genotype in the 4 Punnett square boxes."),
                *[DraftChoice(t, False, pool[t]) for t in picks],
            ],
        )

    def _q_expected_offspring_count(self, params, rng: Rng) -> DraftQuestion:
        trait, p1, p2, dist = self._known(params)
        n = params["offspring_total"]
        target = params["target_phenotype"]
        p = dist["phenotypes"][target]
        correct = int(p * n)
        options: dict[int, str] = {correct: ""}
        for f in rng.shuffled([Fraction(k, 4) for k in range(1, 5)]):
            v = int(f * n)
            if v not in options:
                options[v] = f"This assumes a probability of {_frac_text(f)} instead of {_frac_text(p)}."
        if correct // 2 not in options and correct:
            options[correct // 2] = "This is half of the expected number."
        others = [v for v in options if v != correct][:3]
        if len(others) < 3:
            raise GenerationError("not enough distinct expected-count options")
        return DraftQuestion(
            stem=(
                f"Suppose Cross 1 produces {n} offspring. About how many of them would be expected to have {target}?"
            ),
            answer=str(correct),
            explanation=f"Probability of {target} = {_frac_text(p)}; expected number = {_frac_text(p).split(' ')[0]} × {n} = {correct}.",
            choices=[
                DraftChoice(str(correct), True, f"Correct: {_frac_text(p).split(' ')[0]} × {n} = {correct}."),
                *[DraftChoice(str(v), False, options[v]) for v in others],
            ],
        )

    def _q_infer_parent_genotypes(self, params, rng: Rng) -> DraftQuestion:
        trait = TRAITS[params["trait"]]
        unknown = tuple(params["unknown_cross"])
        obs = params["observed"]
        order = obs["phenotypes"]
        distinct = [c for c in _distinct_crosses(trait) if c != unknown]
        others = rng.sample(distinct, min(3, len(distinct)))
        if len(others) < 3:
            raise GenerationError("not enough distinct crosses")

        def expected_text(c):
            vec = _pheno_vector(trait, c)
            return ", ".join(f"{int(f * 4)}/4 {ph}" for f, ph in zip(vec, order) if f) or "none"

        observed_text = ", ".join(f"{c} {ph}" for c, ph in zip(obs["counts"], order) if c)
        obs_pct = ", ".join(f"about {round(100 * c / obs['total'])}% {ph}" for c, ph in zip(obs["counts"], order) if c)
        return DraftQuestion(
            stem=(
                "Based on the Cross 2 data, which pair of parent genotypes is most likely? "
                "(Compare the observed offspring to the distribution each cross would be expected to produce.)"
            ),
            answer=f"{unknown[0]} × {unknown[1]}",
            explanation=(
                f"Observed: {observed_text} ({obs_pct}). A {unknown[0]} × {unknown[1]} cross is expected to produce "
                f"{expected_text(unknown)}, which is closest to the observed distribution. Observed numbers vary a "
                "little from expected ones because each offspring is a separate chance event."
            ),
            choices=[
                DraftChoice(
                    f"{unknown[0]} × {unknown[1]}",
                    True,
                    f"Correct: expected {expected_text(unknown)}, close to what was observed.",
                ),
                *[
                    DraftChoice(
                        f"{c[0]} × {c[1]}",
                        False,
                        f"This cross is expected to produce {expected_text(c)}, which does not match the observed counts.",
                    )
                    for c in others
                ],
            ],
        )

    def _env(self, params):
        env = ENVIRONMENTS[params["environment"]]
        return env, params["environment_rows"]

    def _q_environment_relationship(self, params, rng: Rng) -> DraftQuestion:
        env, rows = self._env(params)
        var = _var(env)
        first, last = rows[0], rows[-1]
        trend = "fewer" if first["percent"] > last["percent"] else "more"
        correct = (
            f"As {var} increases, {trend} individuals {env['trait_verb']}, even though they are genetically identical."
        )
        return DraftQuestion(
            stem="Which conclusion is best supported by the environment study data?",
            answer=correct,
            explanation=(
                f"At a {var} of {_level(env, first['level'])}, {first['percent']}% {env['trait_past']}; at "
                f"{_level(env, last['level'])}, {last['percent']}% did. The genotype is the same in every group, so the "
                f"difference in expression comes from the environment. {env['mechanism']}."
            ),
            choices=[
                DraftChoice(
                    correct,
                    True,
                    "Correct: the genotype is constant, so the environment explains the change in the trait's distribution.",
                ),
                DraftChoice(
                    f"As {var} increases, more individuals {env['trait_verb']}."
                    if trend == "fewer"
                    else f"As {var} increases, fewer individuals {env['trait_verb']}.",
                    False,
                    f"The data show the opposite trend: {first['percent']}% at {_level(env, first['level'])} vs. "
                    f"{last['percent']}% at {_level(env, last['level'])}.",
                ),
                DraftChoice(
                    f"{env['variable'].split(' (')[0]} changes the individuals' genotypes.",
                    False,
                    "The environment affects how the genes are expressed, not the alleles the individuals inherited.",
                ),
                DraftChoice(
                    "The trait is controlled only by genes, so the differences between groups are due to chance.",
                    False,
                    "The groups are genetically identical and the pattern is consistent across every level, so it is not chance alone.",
                ),
            ],
        )

    def _q_environment_prediction(self, params, rng: Rng) -> DraftQuestion:
        env, rows = self._env(params)
        gaps = [
            (rows[i], rows[i + 1])
            for i in range(len(rows) - 1)
            if abs(rows[i]["percent"] - rows[i + 1]["percent"]) >= 25
        ]
        if not gaps:
            raise GenerationError("no interval with a large enough change to predict within")
        a, b = rng.choice(gaps)
        mid = (a["level"] + b["level"]) / 2
        lo, hi = sorted((a["percent"], b["percent"]))
        return DraftQuestion(
            stem=(
                f"Predict the percent of {env['organism']} that would {env['trait_verb']} if a new group were raised "
                f"at a {_var(env)} of {_level(env, mid)}."
            ),
            answer=f"Between {lo}% and {hi}%",
            explanation=(
                f"{_level(env, mid)} lies between the tested levels {_level(env, a['level'])} ({a['percent']}%) and "
                f"{_level(env, b['level'])} ({b['percent']}%). Because the trend is consistent, the percent should fall "
                "between those values."
            ),
            choices=[
                DraftChoice(
                    f"Between {lo}% and {hi}%",
                    True,
                    "Correct: the new level lies between two tested levels, so the result should too.",
                ),
                *self._out_of_range_choices(env, rows, lo, hi),
            ],
        )

    def _out_of_range_choices(self, env, rows, lo: int, hi: int) -> list[DraftChoice]:
        broken = "This would break the consistent trend shown in the data."
        out = []
        if hi < 100:
            out.append(DraftChoice(f"Greater than {hi}%", False, broken))
        if lo > 0:
            out.append(DraftChoice(f"Less than {lo}%", False, broken))
        out.append(
            DraftChoice(
                "Exactly 50%, because the trait depends on chance alone",
                False,
                "The data show a consistent pattern with the environmental variable, not a fixed 50% chance.",
            )
        )
        for row in (rows[0], rows[-1]):
            if len(out) >= 3:
                break
            if not lo <= row["percent"] <= hi:
                out.append(
                    DraftChoice(
                        f"About {row['percent']}%, the same as at {_level(env, row['level'])}",
                        False,
                        f"{_level(env, row['level'])} is far from the new level; the result should fall between the two nearest tested levels.",
                    )
                )
        if len(out) < 3:
            raise GenerationError("not enough out-of-range options")
        return out[:3]

    def _q_explain_variation(self, params, rng: Rng) -> DraftQuestion:
        env, rows = self._env(params)
        row = rows[params["cr_level_index"]]
        n = params["cr_plant_count"]
        expected = round(n * row["present"] / row["total"])
        var = _var(env)
        return DraftQuestion(
            stem=(
                f"A new group of {n} genetically identical {env['organism']} is raised at a {var} of "
                f"{_level(env, row['level'])}. (a) Using the data, predict how many will {env['trait_verb']}. "
                "(b) Explain why this trait varies among individuals that all have the same genotype."
            ),
            answer=(
                f"(a) At {_level(env, row['level'])}, {row['present']} of {row['total']} ({row['percent']}%) "
                f"{env['trait_past']}, so about {row['present']}/{row['total']} × {n} ≈ {expected}. "
                "(b) Because the genotype is the same, the variation is caused by the environment affecting how the "
                f"gene is expressed. {env['mechanism']}."
            ),
            explanation=(
                "Scoring guide (3 points): (1) uses the observed proportion at the stated level to predict a number near "
                f"{expected}; (2) states that the genotype is the same, so the environment causes the variation; "
                f"(3) describes how {var} affects expression of the trait."
            ),
        )
