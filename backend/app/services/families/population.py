"""B-LS2-1 (Biology 1): carrying capacity from population survey data.

Model: logistic growth N(t) = K / (1 + ((K - N0) / N0) e^(-rt)) toward K1, then — after one
environmental change at t_e — logistic relaxation from N(t_e) toward K2. Observed counts carry
small seeded survey noise and are rounded; every answer below is computed from those displayed
counts, not from the continuous model. No item asks students to derive an equation (state
assessment boundary).
"""

import math
from typing import Any

from app.services.engine.core import (
    Binding,
    DraftChoice,
    DraftQuestion,
    GenerationError,
    Rng,
    TemplateSpec,
    fmt_num,
)
from app.services.engine.family import QuestionFamily

# Each scenario: an organism, a habitat of known size, a survey schedule, a factor that does NOT
# change (control), and events that change a limiting factor. Event multipliers are the ratio
# K2/K1. Biotic/abiotic and density-dependence classifications follow standard HS ecology usage.
SCENARIOS: dict[str, dict[str, Any]] = {
    "deer_island": {
        "organism": "white-tailed deer",
        "organism_plural": "deer",
        "habitat": "island wildlife reserve",
        "habitat_size": {"value": 12, "unit": "km²", "measure": "area"},
        "time_unit": "year",
        "step": 2,
        "k_range": (400, 800),
        "k_round": 10,
        "n0_range": (18, 36),
        "r_range": (0.38, 0.52),
        "count_label": "Deer counted",
        "control": {"label": "Mean summer temperature (°C)", "base": 27.0, "jitter": 0.5, "decimals": 1},
        "events": {
            "drought": {
                "column": "Annual rainfall (cm)",
                "before": 96.0,
                "after": 54.0,
                "jitter": 3.0,
                "decimals": 0,
                "k_multiplier": (0.55, 0.68),
                "phrase": "a decrease in annual rainfall",
                "short": "decreased rainfall",
                "biotic": False,
                "density_dependent": False,
                "mechanism": "less rainfall reduces the growth of the plants the deer eat, so the island can support fewer deer",
                "reversal": "annual rainfall returned to about {before} cm",
            },
            "wolves": {
                "column": "Wolves observed",
                "before": 0.0,
                "after": 8.0,
                "jitter": 1.0,
                "decimals": 0,
                "k_multiplier": (0.55, 0.7),
                "phrase": "the arrival of a wolf pack",
                "short": "added predators",
                "biotic": True,
                "density_dependent": True,
                "mechanism": "wolves prey on deer, increasing the death rate, so the island supports fewer deer",
                "reversal": "the wolves left the island",
            },
            "forage_restoration": {
                "column": "Forage available (kg/ha)",
                "before": 820.0,
                "after": 1240.0,
                "jitter": 25.0,
                "decimals": 0,
                "k_multiplier": (1.3, 1.45),
                "phrase": "an increase in available forage after a habitat restoration project",
                "short": "increased food supply",
                "biotic": True,
                "density_dependent": True,
                "mechanism": "more plant food is available, so the island can support more deer",
                "reversal": "forage returned to about {before} kg/ha",
            },
        },
    },
    "bluegill_pond": {
        "organism": "bluegill sunfish",
        "organism_plural": "bluegill",
        "habitat": "farm pond",
        "habitat_size": {"value": 4, "unit": "hectares", "measure": "surface area"},
        "time_unit": "year",
        "step": 1,
        "k_range": (1200, 2600),
        "k_round": 50,
        "n0_range": (60, 120),
        "r_range": (0.6, 0.8),
        "count_label": "Estimated bluegill",
        "control": {"label": "Water pH", "base": 7.3, "jitter": 0.1, "decimals": 1},
        "events": {
            "low_oxygen": {
                "column": "Dissolved oxygen (mg/L)",
                "before": 8.2,
                "after": 4.1,
                "jitter": 0.3,
                "decimals": 1,
                "k_multiplier": (0.5, 0.65),
                "phrase": "a drop in dissolved oxygen in the water",
                "short": "lower dissolved oxygen",
                "biotic": False,
                "density_dependent": False,
                "mechanism": "fish need dissolved oxygen for cellular respiration, so less oxygen means the pond supports fewer fish",
                "reversal": "dissolved oxygen returned to about {before} mg/L",
            },
            "bass_stocked": {
                "column": "Largemouth bass caught per survey",
                "before": 0.0,
                "after": 14.0,
                "jitter": 2.0,
                "decimals": 0,
                "k_multiplier": (0.5, 0.65),
                "phrase": "the introduction of largemouth bass, a predator of bluegill",
                "short": "added predators",
                "biotic": True,
                "density_dependent": True,
                "mechanism": "bass prey on bluegill, so the pond supports fewer bluegill",
                "reversal": "the bass were removed from the pond",
            },
        },
    },
    "paramecium_culture": {
        "organism": "Paramecium caudatum",
        "organism_plural": "Paramecium",
        "habitat": "laboratory culture",
        "habitat_size": {"value": 50, "unit": "mL", "measure": "volume"},
        "time_unit": "day",
        "step": 1,
        "k_range": (300, 520),
        "k_round": 10,
        "n0_range": (4, 10),
        "r_range": (0.85, 1.1),
        "count_label": "Paramecium per mL",
        "control": {"label": "Water temperature (°C)", "base": 22.0, "jitter": 0.2, "decimals": 1},
        "events": {
            "food_reduced": {
                "column": "Bacteria added daily (millions of cells)",
                "before": 40.0,
                "after": 20.0,
                "jitter": 1.0,
                "decimals": 0,
                "k_multiplier": (0.45, 0.6),
                "phrase": "a reduction in the bacteria added as food",
                "short": "reduced food supply",
                "biotic": True,
                "density_dependent": True,
                "mechanism": "Paramecium eat bacteria, so a smaller food supply supports fewer Paramecium",
                "reversal": "the food supply returned to about {before} million bacteria per day",
            },
            "salinity": {
                "column": "Salt concentration (%)",
                "before": 0.0,
                "after": 0.4,
                "jitter": 0.02,
                "decimals": 2,
                "k_multiplier": (0.5, 0.65),
                "phrase": "an increase in the salt concentration of the culture water",
                "short": "increased salinity",
                "biotic": False,
                "density_dependent": False,
                "mechanism": "salty water stresses these freshwater organisms, so the culture supports fewer Paramecium",
                "reversal": "the salt concentration returned to about {before}%",
            },
        },
    },
}

SCALE_RATIOS = (0.5, 2, 3, 4)


def _logistic(n0: float, k: float, r: float, t: float) -> float:
    return k / (1 + ((k - n0) / n0) * math.exp(-r * t))


def _a(noun_phrase: str) -> str:
    return ("an " if noun_phrase[0].lower() in "aeiou" else "a ") + noun_phrase


def _lc(label: str) -> str:
    """Lowercase a column label's first letter for use mid-sentence, dropping the unit."""
    name = label.split(" (")[0]
    return name if len(name) > 1 and name[1].isupper() else name[0].lower() + name[1:]


def _rnd(value: float, decimals: int) -> float | int:
    return round(value, decimals) if decimals else int(round(value))


def _round_to(value: float, step: int) -> int:
    return int(step * round(value / step))


class PopulationCarryingCapacity(QuestionFamily):
    key = "population-carrying-capacity"
    version = "1.0.0"
    title = "Carrying capacity: population survey data"
    description = (
        "A population survey table and graph showing logistic growth to a carrying capacity, then a "
        "shift after one limiting factor changes. Items ask students to read trends, estimate carrying "
        "capacity, identify and classify the limiting factor, predict effects of changes, and reason "
        "about scale."
    )
    stimulus_kind = "population_dataset"
    bindings = (Binding("SC", "biology-1", "B-LS2-1"),)
    templates = (
        TemplateSpec("fastest_growth_interval", "Interval of fastest growth", 1, "multiple_choice", "representation", 0),
        TemplateSpec("classify_factor", "Classify the limiting factor", 1, "multiple_choice", "analysis", 0),
        TemplateSpec("estimate_carrying_capacity", "Estimate carrying capacity", 2, "multiple_choice", "representation", 0),
        TemplateSpec("identify_limiting_factor", "Identify the factor with the largest effect", 2, "multiple_choice", "analysis", 2),
        TemplateSpec("predict_factor_reversal", "Predict the effect of a change", 2, "multiple_choice", "analysis", 1),
        TemplateSpec("scale_prediction", "Carrying capacity at a different scale", 2, "multiple_choice", "representation", 1),
        TemplateSpec("explain_with_data", "Explain the change using data", 3, "constructed_response", "analysis", 0),
    )

    # ---- scenario ---------------------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        scenario_key = rng.choice(sorted(SCENARIOS))
        sc = SCENARIOS[scenario_key]
        event_key = rng.choice(sorted(sc["events"]))
        ev = sc["events"][event_key]
        step = sc["step"]

        k1 = _round_to(rng.uniform(*sc["k_range"]), sc["k_round"])
        n0 = rng.randint(*sc["n0_range"])
        r = round(rng.uniform(*sc["r_range"]), 3)
        k2 = _round_to(k1 * rng.uniform(*ev["k_multiplier"]), sc["k_round"])

        # Start the change only after the population has clearly leveled off (>= 97% of K1),
        # leaving at least 3 plateau survey points, then survey until within 3% of K2.
        t97 = math.log(0.97 / 0.03 * (k1 - n0) / n0) / r
        t_event = step * (math.ceil(t97 / step) + 3)
        relax = 0.0
        n_event = _logistic(n0, k1, r, t_event)
        while abs(_logistic(n_event, k2, r, relax) - k2) > 0.03 * k2:
            relax += step
        t_end = t_event + step * (math.ceil(relax / step) + 3)

        for _ in range(50):
            rows = self._survey(rng, sc, ev, n0, k1, k2, r, n_event, t_event, t_end, step)
            increases = sorted((b["n"] - a["n"] for a, b in zip(rows, rows[1:])), reverse=True)
            # The "fastest growth" item needs one clearly largest increase.
            if increases[0] >= 1.05 * increases[1] + 1:
                break
        else:
            raise GenerationError("could not draw survey data with a unique fastest-growth interval")

        plateau1 = [row["n"] for row in rows if t97 <= row["t"] <= t_event]
        plateau2 = rows[-3:]
        k1_est = _round_to(sum(plateau1) / len(plateau1), sc["k_round"])
        k2_est = _round_to(sum(r_["n"] for r_ in plateau2) / 3, sc["k_round"])

        return {
            "scenario": scenario_key,
            "event": event_key,
            "model": {"k1": k1, "k2": k2, "n0": n0, "r": r, "t_event": t_event, "step": step},
            "rows": rows,
            "k1_estimate": k1_est,
            "k2_estimate": k2_est,
            "scale_ratio": rng.choice(SCALE_RATIOS),
        }

    @staticmethod
    def _survey(rng: Rng, sc, ev, n0, k1, k2, r, n_event, t_event, t_end, step) -> list[dict[str, Any]]:
        control = sc["control"]
        rows = []
        t = 0
        while t <= t_end:
            true_n = _logistic(n0, k1, r, t) if t <= t_event else _logistic(n_event, k2, r, t - t_event)
            observed = max(1, round(true_n * (1 + rng.uniform(-0.025, 0.025))))
            # The factor column switches at the first survey after the change began.
            level = ev["before"] if t <= t_event else ev["after"]
            factor = level + rng.uniform(-ev["jitter"], ev["jitter"])
            if ev["before"] == 0 and t <= t_event:
                factor = 0.0
            ctrl = control["base"] + rng.uniform(-control["jitter"], control["jitter"])
            rows.append(
                {
                    "t": t,
                    "n": observed,
                    "factor": _rnd(max(0.0, factor), ev["decimals"]),
                    "control": _rnd(ctrl, control["decimals"]),
                }
            )
            t += step
        return rows

    # ---- stimulus ---------------------------------------------------------------------------

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        sc = SCENARIOS[params["scenario"]]
        ev = sc["events"][params["event"]]
        unit = sc["time_unit"].capitalize()
        size = sc["habitat_size"]
        return {
            "title": f"{sc['organism_plural'].capitalize()} in {_a(sc['habitat'])}",
            "intro": (
                f"Biologists surveyed a population of {sc['organism']} living in {_a(sc['habitat'])} "
                f"({size['measure']}: {size['value']} {size['unit']}). At each survey they also recorded two "
                f"environmental measurements. The data are shown in the table and graph."
            ),
            "tables": [{
                "caption": f"{sc['organism_plural'].capitalize()} survey data",
                "columns": [
                    {"key": "t", "label": unit},
                    {"key": "n", "label": sc["count_label"]},
                    {"key": "factor", "label": ev["column"]},
                    {"key": "control", "label": sc["control"]["label"]},
                ],
                "rows": params["rows"],
            }],
            "charts": [{
                "type": "line",
                "title": f"{sc['count_label']} over time",
                "x": {"key": "t", "label": unit},
                "y": {"label": sc["count_label"], "min": 0},
                "series": [{"key": "n", "label": sc["count_label"]}],
                "table_index": 0,
            }],
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _ctx(self, params):
        sc = SCENARIOS[params["scenario"]]
        return sc, sc["events"][params["event"]], params["rows"]

    def _q_fastest_growth_interval(self, params, rng: Rng) -> DraftQuestion:
        sc, _, rows = self._ctx(params)
        unit = sc["time_unit"]
        intervals = [
            (rows[i]["t"], rows[i + 1]["t"], rows[i + 1]["n"] - rows[i]["n"]) for i in range(len(rows) - 1)
        ]
        best = max(intervals, key=lambda iv: iv[2])
        others = [iv for iv in intervals if iv is not best and iv[2] <= 0.6 * best[2]]
        if len(others) < 3:
            raise GenerationError("not enough clearly slower intervals")
        distractors = rng.sample(others, 3)

        def label(iv):
            return f"{unit.capitalize()} {iv[0]} to {unit} {iv[1]}"

        def change(iv):
            d = iv[2]
            return f"the count changed by {d:+,}" if d else "the count did not change"

        choices = [
            DraftChoice(label(best), True, f"Correct: the count rose by {best[2]:,}, the largest increase between any two surveys."),
            *[
                DraftChoice(label(iv), False, f"In this interval {change(iv)}, less than the {best[2]:,} increase from {unit} {best[0]} to {best[1]}.")
                for iv in distractors
            ],
        ]
        return DraftQuestion(
            stem=f"According to the data, during which interval did the {sc['organism_plural']} population increase the most?",
            answer=label(best),
            explanation=(
                f"Subtract consecutive counts. The largest increase ({best[2]:,}) occurs from {unit} {best[0]} to "
                f"{unit} {best[1]}, during the rapid-growth phase before the population approaches carrying capacity."
            ),
            choices=choices,
        )

    def _q_classify_factor(self, params, rng: Rng) -> DraftQuestion:
        _, ev, _ = self._ctx(params)
        b_true, d_true = ev["biotic"], ev["density_dependent"]
        b_reason = (
            f"{'biotic' if b_true else 'abiotic'}: "
            + ("it involves living organisms" if b_true else "it is a nonliving physical or chemical condition")
        )
        d_reason = f"density-{'dependent' if d_true else 'independent'}: " + (
            "its effect on each individual grows as the population becomes more crowded"
            if d_true
            else "its effect on each individual does not depend on how crowded the population is"
        )

        def text(b, d):
            return f"{'Biotic' if b else 'Abiotic'} and density-{'dependent' if d else 'independent'}"

        choices = []
        for b in (True, False):
            for d in (True, False):
                if (b, d) == (b_true, d_true):
                    choices.append(DraftChoice(text(b, d), True, f"Correct. It is {b_reason}; it is {d_reason}."))
                else:
                    wrong = [x for x, bad in ((b_reason, b != b_true), (d_reason, d != d_true)) if bad]
                    choices.append(DraftChoice(text(b, d), False, "Incorrect. It is " + "; it is ".join(wrong) + "."))
        return DraftQuestion(
            stem=(
                f"The data show that the carrying capacity changed after {ev['phrase']}. "
                "How is this limiting factor best classified?"
            ),
            answer=text(b_true, d_true),
            explanation=f"{ev['short'].capitalize()}: {ev['mechanism']}.",
            choices=choices,
        )

    def _q_estimate_carrying_capacity(self, params, rng: Rng) -> DraftQuestion:
        sc, _, rows = self._ctx(params)
        k1 = params["k1_estimate"]
        k2 = params["k2_estimate"]
        t_event = params["model"]["t_event"]
        unit = sc["time_unit"]
        candidates = {
            "half": (_round_to(k1 / 2, sc["k_round"]), "This is about half the carrying capacity, where growth is fastest, not the level where the population levels off."),
            "later": (k2, f"This is where the population leveled off after {unit} {t_event}, not before the change."),
            "start": (rows[0]["n"], "This is the starting population, not the maximum the habitat supported."),
            "above": (_round_to(k1 * 1.5, sc["k_round"]), "The population never approached this size; the counts leveled off well below it."),
        }
        picked = []
        for name in rng.shuffled(list(candidates)):
            value, why = candidates[name]
            if all(abs(value - v) >= 0.15 * k1 for v, _ in [(k1, ""), *picked]):
                picked.append((value, why))
            if len(picked) == 3:
                break
        if len(picked) < 3:
            raise GenerationError("carrying capacity distractors too close together")
        return DraftQuestion(
            stem=(
                f"Based on the data before {unit} {t_event}, the carrying capacity of the {sc['habitat']} for "
                f"{sc['organism_plural']} was closest to which value?"
            ),
            answer=fmt_num(k1),
            explanation=(
                f"Before {unit} {t_event} the counts stopped rising and fluctuated around {fmt_num(k1)}; "
                "that level is the carrying capacity."
            ),
            choices=[
                DraftChoice(fmt_num(k1), True, f"Correct: the counts leveled off and fluctuated around {fmt_num(k1)}."),
                *[DraftChoice(fmt_num(v), False, why) for v, why in picked],
            ],
        )

    def _q_identify_limiting_factor(self, params, rng: Rng) -> DraftQuestion:
        sc, ev, rows = self._ctx(params)
        t_event = params["model"]["t_event"]
        unit = sc["time_unit"]
        direction = "increased" if params["k2_estimate"] > params["k1_estimate"] else "decreased"
        factor_dir = "increase" if ev["after"] > ev["before"] else "decrease"
        ctrl = _lc(sc["control"]["label"])
        return DraftQuestion(
            stem=(
                f"After {unit} {t_event}, the {sc['organism_plural']} population {direction} and then leveled off "
                "at a new size. Which factor most likely had the largest effect on this change?"
            ),
            answer=f"The {factor_dir} in {_lc(ev['column'])}",
            explanation=(
                f"Only {_lc(ev['column'])} changed at the same time as the population; "
                f"{ctrl} stayed about the same throughout. {ev['mechanism'].capitalize()}."
            ),
            choices=[
                DraftChoice(
                    f"The {factor_dir} in {_lc(ev['column'])}",
                    True,
                    "Correct: this measurement changed at the same time the population shifted to a new level.",
                ),
                DraftChoice(
                    f"A change in {ctrl}",
                    False,
                    f"The table shows {ctrl} stayed nearly constant for the whole study, so it cannot explain the shift.",
                ),
                DraftChoice(
                    "The population had not yet reached its carrying capacity",
                    False,
                    f"The counts had already leveled off before {unit} {t_event}.",
                ),
                DraftChoice(
                    "The population's growth rate increased on its own",
                    False,
                    "Growth rate is an outcome of limiting factors, not an outside factor; the data point to a change in the environment.",
                ),
            ],
        )

    def _q_predict_factor_reversal(self, params, rng: Rng) -> DraftQuestion:
        sc, ev, _ = self._ctx(params)
        k1, k2 = params["k1_estimate"], params["k2_estimate"]
        before = fmt_num(ev["before"], ev["decimals"]) if ev["decimals"] else fmt_num(ev["before"])
        reversal = ev["reversal"].format(before=before)
        toward = "increase" if k1 > k2 else "decrease"
        return DraftQuestion(
            stem=(
                f"Suppose that after the study ended, {reversal}, and all other conditions stayed the same. "
                f"Which prediction about the carrying capacity for {sc['organism_plural']} is best supported by the data?"
            ),
            answer=f"It would {toward} toward about {fmt_num(k1)}",
            explanation=(
                f"When the limiting factor was at that level, the population leveled off near {fmt_num(k1)}; "
                f"after it changed, the population leveled off near {fmt_num(k2)}. Restoring the factor should move "
                f"carrying capacity back toward {fmt_num(k1)}."
            ),
            choices=[
                DraftChoice(f"It would {toward} toward about {fmt_num(k1)}", True, "Correct: the data link that factor level to a carrying capacity near this value."),
                DraftChoice(
                    f"It would stay at about {fmt_num(k2)}",
                    False,
                    "Carrying capacity is not fixed; it changes when limiting factors change, as the data already show.",
                ),
                DraftChoice(
                    "The population would grow without limit",
                    False,
                    "Other limiting factors still apply; the population leveled off earlier even at the original factor level.",
                ),
                DraftChoice(
                    f"It would {'decrease' if toward == 'increase' else 'increase'} further",
                    False,
                    "This is the opposite of the direction the data show for that factor.",
                ),
            ],
        )

    def _q_scale_prediction(self, params, rng: Rng) -> DraftQuestion:
        sc, _, _ = self._ctx(params)
        k1 = params["k1_estimate"]
        ratio = params["scale_ratio"]
        size = sc["habitat_size"]
        other_size = size["value"] * ratio
        other_size_txt = f"{other_size:g} {size['unit']}"
        rnd = sc["k_round"]
        correct = _round_to(k1 * ratio, rnd)
        options = {
            correct: (True, f"Correct: with the same resources per unit of {size['measure']}, carrying capacity scales with {size['measure']} ({ratio:g} × {fmt_num(k1)})."),
            k1: (False, "This ignores scale: a habitat with a different amount of resources supports a different number of individuals."),
            _round_to(k1 / ratio, rnd): (False, "This scales in the wrong direction."),
            _round_to(k1 * ratio * ratio, rnd): (False, f"This multiplies by the ratio twice; carrying capacity scales once with {size['measure']}."),
        }
        if len(options) != 4:
            raise GenerationError("scale options collided after rounding")
        return DraftQuestion(
            stem=(
                f"Before the change, the {sc['habitat']} ({size['measure']}: {size['value']} {size['unit']}) supported about "
                f"{fmt_num(k1)} {sc['organism_plural']}. A second {sc['habitat']} has {_a(size['measure'])} of {other_size_txt}, "
                f"with the same resources and conditions per unit of {size['measure']}. What is the best estimate of its carrying capacity?"
            ),
            answer=fmt_num(correct),
            explanation=(
                f"The second habitat is {ratio:g} times the {size['measure']} with the same resources per unit, so it can "
                f"support about {ratio:g} × {fmt_num(k1)} ≈ {fmt_num(correct)} individuals."
            ),
            choices=[DraftChoice(fmt_num(v), ok, why) for v, (ok, why) in options.items()],
        )

    def _q_explain_with_data(self, params, rng: Rng) -> DraftQuestion:
        sc, ev, rows = self._ctx(params)
        k1, k2 = params["k1_estimate"], params["k2_estimate"]
        t_event = params["model"]["t_event"]
        unit = sc["time_unit"]
        pct = round(abs(k2 - k1) / k1 * 100)
        direction = "decreased" if k2 < k1 else "increased"
        col = _lc(ev["column"])
        before_rows = [r for r in rows if r["t"] <= t_event]
        after_rows = [r for r in rows if r["t"] > t_event]
        fb = before_rows[-1]["factor"]
        fa = after_rows[-1]["factor"]
        return DraftQuestion(
            stem=(
                f"Use numerical evidence from the table or graph to explain how the carrying capacity of the {sc['habitat']} "
                f"for {sc['organism_plural']} changed during the study, and identify which environmental factor most likely "
                "caused the change. Explain how that factor limits the population."
            ),
            answer=(
                f"Before {unit} {t_event}, the population leveled off at about {fmt_num(k1)}. After {unit} {t_event}, "
                f"{col} changed (about {fb:g} → {fa:g}) and the population {direction} to a new level of about {fmt_num(k2)} "
                f"(about {pct}% {'lower' if k2 < k1 else 'higher'}). {ev['mechanism'].capitalize()}. "
                f"{sc['control']['label'].split(' (')[0]} stayed nearly constant, so it does not explain the change."
            ),
            explanation=(
                "Scoring guide (3 points): (1) cites the original carrying capacity and the new level with values from the data; "
                f"(2) identifies {col} as the factor that changed at the same time; "
                "(3) explains the mechanism — how the factor changes resources or survival and so changes carrying capacity."
            ),
        )
