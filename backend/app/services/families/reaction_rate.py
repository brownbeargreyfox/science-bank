"""C-PS1-5 (Chemistry): effect of temperature and concentration on reaction rate.

Two classroom experiments on one two-reactant reaction (state assessment boundary: simple reactions
with only two reactants): Experiment 1 varies the concentration of the dissolved reactant at constant
temperature; Experiment 2 varies temperature at constant concentration.

Model: rate = k(T) * [A] with k(T) = k_ref * exp(-Ea/R * (1/T - 1/T_ref)) and Ea in a realistic range,
so rate rises with temperature ("usually", per the Performance Target — no enzyme/optimum systems
are included). Displayed measurements carry small seeded noise and are either an amount formed in a
fixed time (proportional to rate) or a time to reach a fixed endpoint (inversely proportional to
rate). Every key is computed from the displayed values, and temperature items stay qualitative.
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
)
from app.services.engine.family import QuestionFamily

R_GAS = 8.314
T_REF = 298.15

REACTIONS: dict[str, dict[str, Any]] = {
    "thiosulfate_hcl": {
        "name": "sodium thiosulfate and hydrochloric acid",
        "equation": "Na₂S₂O₃(aq) + 2HCl(aq) → 2NaCl(aq) + SO₂(g) + S(s) + H₂O(l)",
        "setup": (
            "Students mixed sodium thiosulfate solution with hydrochloric acid in a flask placed over a paper marked "
            "with an X. The solid sulfur produced makes the mixture cloudy. Students timed how long it took for the "
            "X to disappear from view."
        ),
        "varied_reactant": "sodium thiosulfate",
        "fixed_reactant": "hydrochloric acid (1.0 mol/L)",
        "concentrations": [0.05, 0.10, 0.15, 0.20, 0.25],
        "fixed_concentration": 0.10,
        "temperatures": [20, 30, 40, 50],
        "fixed_temperature": 20,
        "measure": "time",
        "measure_label": "Time for X to disappear (s)",
        "measure_short": "time for the X to disappear",
        "unit": "s",
        "decimals": 0,
        # measurement at [A]=fixed_concentration and T_REF: seconds to endpoint
        "ref_range": (38.0, 55.0),
        "ea_range": (48000, 58000),
    },
    "magnesium_hcl": {
        "name": "magnesium and hydrochloric acid",
        "equation": "Mg(s) + 2HCl(aq) → MgCl₂(aq) + H₂(g)",
        "setup": (
            "Students dropped identical 3 cm strips of magnesium ribbon into hydrochloric acid and measured the volume "
            "of hydrogen gas collected in the first 20 seconds using a gas syringe."
        ),
        "varied_reactant": "hydrochloric acid",
        "fixed_reactant": "magnesium ribbon (3 cm strips)",
        "concentrations": [0.50, 0.75, 1.00, 1.25, 1.50],
        "fixed_concentration": 1.00,
        "temperatures": [15, 25, 35, 45],
        "fixed_temperature": 25,
        "measure": "amount",
        "measure_label": "H₂ collected in 20 s (mL)",
        "measure_short": "volume of hydrogen gas collected in 20 s",
        "unit": "mL",
        "decimals": 1,
        "ref_range": (9.0, 13.0),
        "ea_range": (30000, 40000),
    },
    "marble_hcl": {
        "name": "calcium carbonate (marble chips) and hydrochloric acid",
        "equation": "CaCO₃(s) + 2HCl(aq) → CaCl₂(aq) + H₂O(l) + CO₂(g)",
        "setup": (
            "Students added 10 g of same-size marble chips to 50 mL of hydrochloric acid in a flask on a balance and "
            "recorded the mass lost as carbon dioxide gas escaped during the first 60 seconds."
        ),
        "varied_reactant": "hydrochloric acid",
        "fixed_reactant": "marble chips (10 g, same size)",
        "concentrations": [0.50, 1.00, 1.50, 2.00],
        "fixed_concentration": 1.00,
        "temperatures": [20, 30, 40, 50],
        "fixed_temperature": 20,
        "measure": "amount",
        "measure_label": "Mass lost in 60 s (g)",
        "measure_short": "mass lost in 60 s",
        "unit": "g",
        "decimals": 2,
        "ref_range": (0.10, 0.16),
        "ea_range": (35000, 45000),
    },
}


def _k_factor(temp_c: float, ea: float) -> float:
    return math.exp(-ea / R_GAS * (1 / (temp_c + 273.15) - 1 / T_REF))


def _fmt(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}" if decimals else f"{round(value)}"


class ReactionRate(QuestionFamily):
    key = "reaction-rate"
    version = "1.0.0"
    title = "Reaction rate: temperature and concentration"
    description = (
        "Two experiments on a two-reactant reaction — one varying the concentration of a dissolved reactant, one "
        "varying temperature — with items on identifying patterns in rate data, explaining them with collision "
        "theory, and making qualitative predictions."
    )
    stimulus_kind = "rate_experiments"
    bindings = (Binding("SC", "chemistry", "C-PS1-5"),)
    templates = (
        TemplateSpec("concentration_trend", "Pattern: concentration and rate", 1, "multiple_choice", "evidence", 0),
        TemplateSpec("temperature_trend", "Pattern: temperature and rate", 1, "multiple_choice", "evidence", 1),
        TemplateSpec(
            "explain_concentration",
            "Explain the concentration effect",
            2,
            "multiple_choice",
            "articulating_explanation",
            1,
        ),
        TemplateSpec(
            "explain_temperature", "Explain the temperature effect", 2, "multiple_choice", "articulating_explanation", 0
        ),
        TemplateSpec(
            "unsuccessful_collisions",
            "Why not every collision reacts",
            2,
            "multiple_choice",
            "articulating_explanation",
            2,
        ),
        TemplateSpec("predict_temperature_trial", "Predict a new trial", 2, "multiple_choice", "evidence", 1),
        TemplateSpec(
            "explain_with_evidence", "Explain both experiments with evidence", 3, "constructed_response", "reasoning", 0
        ),
    )

    # ---- scenario ---------------------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        key = rng.choice(sorted(REACTIONS))
        rx = REACTIONS[key]
        ref = rng.uniform(*rx["ref_range"])
        ea = round(rng.uniform(*rx["ea_range"]), -2)
        t_fixed = rx["fixed_temperature"]
        c_fixed = rx["fixed_concentration"]

        def measure(conc: float, temp: float) -> float:
            relative_rate = (conc / c_fixed) * _k_factor(temp, ea) / _k_factor(t_fixed, ea)
            noisy = relative_rate * (1 + rng.uniform(-0.03, 0.03))
            value = ref / noisy if rx["measure"] == "time" else ref * noisy
            return round(value, rx["decimals"]) if rx["decimals"] else int(round(value))

        for _ in range(20):
            exp1 = [{"concentration": c, "value": measure(c, t_fixed)} for c in rx["concentrations"]]
            exp2 = [{"temperature": t, "value": measure(c_fixed, t)} for t in rx["temperatures"]]
            if self._monotone(rx, [r["value"] for r in exp1]) and self._monotone(rx, [r["value"] for r in exp2]):
                break
        else:
            raise GenerationError("could not draw monotonic rate data")

        return {
            "reaction": key,
            "model": {"ea_j_per_mol": ea, "reference_measurement": round(ref, 3)},
            "experiment1": exp1,
            "experiment2": exp2,
        }

    @staticmethod
    def _monotone(rx: dict, values: list[float]) -> bool:
        """Faster with each step: strictly decreasing times or strictly increasing amounts."""
        pairs = list(zip(values, values[1:]))
        return all(b < a for a, b in pairs) if rx["measure"] == "time" else all(b > a for a, b in pairs)

    # ---- stimulus ---------------------------------------------------------------------------

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        rx = REACTIONS[params["reaction"]]
        exp1_keys = {"concentration_trend", "explain_concentration", "explain_with_evidence"}
        exp2_keys = {
            "temperature_trend",
            "explain_temperature",
            "unsuccessful_collisions",
            "predict_temperature_trial",
            "explain_with_evidence",
        }
        keys = set(template_keys)
        sections, tables, charts = [], [], []
        if keys & exp1_keys:
            sections.append(
                {
                    "heading": "Experiment 1",
                    "text": (
                        f"The concentration of {rx['varied_reactant']} was changed. The temperature was kept at "
                        f"{rx['fixed_temperature']}°C and {rx['fixed_reactant']} was kept the same in every trial."
                    ),
                    "table_index": len(tables),
                }
            )
            charts.append(
                self._chart(rx, "concentration", "Concentration of " + rx["varied_reactant"] + " (mol/L)", len(tables))
            )
            tables.append(
                {
                    "caption": "Experiment 1: changing concentration",
                    "columns": [
                        {"key": "concentration", "label": f"Concentration of {rx['varied_reactant']} (mol/L)"},
                        {"key": "value", "label": rx["measure_label"]},
                    ],
                    "rows": params["experiment1"],
                }
            )
        if keys & exp2_keys:
            sections.append(
                {
                    "heading": "Experiment 2",
                    "text": (
                        f"The temperature was changed. The concentration of {rx['varied_reactant']} was kept at "
                        f"{rx['fixed_concentration']:.2f} mol/L and {rx['fixed_reactant']} was kept the same in every trial."
                    ),
                    "table_index": len(tables),
                }
            )
            charts.append(self._chart(rx, "temperature", "Temperature (°C)", len(tables)))
            tables.append(
                {
                    "caption": "Experiment 2: changing temperature",
                    "columns": [
                        {"key": "temperature", "label": "Temperature (°C)"},
                        {"key": "value", "label": rx["measure_label"]},
                    ],
                    "rows": params["experiment2"],
                }
            )
        return {
            "title": f"Rate of the reaction between {rx['name']}",
            "intro": f"{rx['setup']} Balanced equation: {rx['equation']}",
            "sections": sections,
            "tables": tables,
            "charts": charts,
        }

    @staticmethod
    def _chart(rx: dict, x_key: str, x_label: str, table_index: int) -> dict:
        return {
            "type": "line",
            "title": f"{rx['measure_label'].split(' (')[0]} vs. {x_label.split(' (')[0].lower()}",
            "x": {"key": x_key, "label": x_label},
            "y": {"label": rx["measure_label"], "min": 0},
            "series": [{"key": "value", "label": rx["measure_label"]}],
            "table_index": table_index,
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _rx(self, params) -> dict:
        return REACTIONS[params["reaction"]]

    def _evidence_phrase(self, rx: dict, rows: list[dict], x_key: str, x_unit: str) -> str:
        first, last = rows[0], rows[-1]
        return (
            f"the {rx['measure_short']} went from {_fmt(first['value'], rx['decimals'])} {rx['unit']} at "
            f"{first[x_key]:g}{x_unit} to {_fmt(last['value'], rx['decimals'])} {rx['unit']} at {last[x_key]:g}{x_unit}"
        )

    def _trend(self, params, rng: Rng, x_key: str, variable: str, x_unit: str, exp: str) -> DraftQuestion:
        rx = self._rx(params)
        rows = params[exp]
        timed = rx["measure"] == "time"
        evidence = self._evidence_phrase(rx, rows, x_key, x_unit)
        correct = f"As {variable} increases, the reaction rate increases."
        misread = (
            f"As {variable} increases, the reaction rate decreases, because the time gets smaller."
            if timed
            else f"As {variable} increases, the reaction rate decreases."
        )
        return DraftQuestion(
            stem=f"Which statement best describes the relationship shown by the {exp.replace('experiment', 'Experiment ')} data?",
            answer=correct,
            explanation=(
                f"As {variable} increased, {evidence}. "
                + (
                    "A shorter time to reach the same endpoint means the reaction is faster, so the rate increased."
                    if timed
                    else "More product formed in the same amount of time, so the rate increased."
                )
            ),
            choices=[
                DraftChoice(
                    correct,
                    True,
                    f"Correct: {evidence}"
                    + (
                        ", and a shorter time means a faster reaction."
                        if timed
                        else ", so more product formed in the same time."
                    ),
                ),
                DraftChoice(
                    misread,
                    False,
                    "A shorter time to reach the same endpoint means a faster reaction, not a slower one."
                    if timed
                    else "The amount formed in the same time increased, which means the rate increased.",
                ),
                DraftChoice(
                    f"Changing {variable} has no effect on the reaction rate.",
                    False,
                    f"The data change consistently: {evidence}.",
                ),
                DraftChoice(
                    f"The reaction rate increases at first and then decreases as {variable} increases.",
                    False,
                    "The data change in the same direction at every step; there is no peak.",
                ),
            ],
        )

    def _q_concentration_trend(self, params, rng: Rng) -> DraftQuestion:
        rx = self._rx(params)
        return self._trend(
            params, rng, "concentration", f"the concentration of {rx['varied_reactant']}", " mol/L", "experiment1"
        )

    def _q_temperature_trend(self, params, rng: Rng) -> DraftQuestion:
        return self._trend(params, rng, "temperature", "temperature", "°C", "experiment2")

    def _q_explain_concentration(self, params, rng: Rng) -> DraftQuestion:
        rx = self._rx(params)
        correct = (
            "A higher concentration puts more reactant particles in the same volume, so particles collide more often "
            "and more collisions happen each second."
        )
        return DraftQuestion(
            stem=(
                f"Which explanation best accounts for the Experiment 1 results when the concentration of "
                f"{rx['varied_reactant']} was increased?"
            ),
            answer=correct,
            explanation=(
                "Collision theory: reactions happen when particles collide with enough energy. Increasing concentration "
                "increases the number of particles per unit volume, so the frequency of collisions (and of successful "
                "collisions) increases. Temperature was constant, so the energy of the particles did not change."
            ),
            choices=[
                DraftChoice(correct, True, "Correct: more particles per volume means more collisions per unit time."),
                DraftChoice(
                    "A higher concentration gives each particle more kinetic energy, so collisions are more energetic.",
                    False,
                    "Temperature, not concentration, determines the particles' average kinetic energy; temperature was kept constant.",
                ),
                DraftChoice(
                    "A higher concentration lowers the activation energy of the reaction.",
                    False,
                    "Concentration does not change the activation energy; it changes how often particles collide.",
                ),
                DraftChoice(
                    "A higher concentration makes every collision between particles produce a reaction.",
                    False,
                    "Even at high concentration, many collisions lack enough energy or the right orientation to react.",
                ),
            ],
        )

    def _q_explain_temperature(self, params, rng: Rng) -> DraftQuestion:
        correct = (
            "At a higher temperature, particles move faster, so they collide more often and a greater fraction of "
            "collisions have enough energy to react."
        )
        return DraftQuestion(
            stem="Which explanation best accounts for the Experiment 2 results when the temperature was increased?",
            answer=correct,
            explanation=(
                "Higher temperature means higher average kinetic energy. Particles collide more frequently, and more of "
                "those collisions have at least the activation energy needed to break bonds, so the rate increases. "
                "The concentration was constant, so the number of particles did not change."
            ),
            choices=[
                DraftChoice(correct, True, "Correct: faster particles collide more often and more energetically."),
                DraftChoice(
                    "At a higher temperature, there are more reactant particles in the solution.",
                    False,
                    "Heating does not add particles; the concentration was kept the same in Experiment 2.",
                ),
                DraftChoice(
                    "At a higher temperature, the activation energy of the reaction becomes smaller.",
                    False,
                    "The activation energy does not change with temperature; more particles have enough energy to exceed it.",
                ),
                DraftChoice(
                    "At a higher temperature, particles collide less often but with more energy.",
                    False,
                    "Faster-moving particles collide more often, not less often.",
                ),
            ],
        )

    def _q_unsuccessful_collisions(self, params, rng: Rng) -> DraftQuestion:
        rx = self._rx(params)
        row = params["experiment2"][0]
        value = f"{_fmt(row['value'], rx['decimals'])} {rx['unit']}"
        observation = (
            f"the X took {value} to disappear"
            if rx["measure"] == "time"
            else f"the {rx['measure_short']} was only {value}"
        )
        correct = (
            "Most collisions do not have enough energy to break the reactants' bonds, so they do not form products."
        )
        return DraftQuestion(
            stem=(
                f"In Experiment 2 at {row['temperature']}°C, {observation}, even though the reactant particles collide "
                "with each other billions of times every second. Which statement best explains why the reaction is not "
                "instantaneous?"
            ),
            answer=correct,
            explanation=(
                "Only collisions with at least the activation energy (and a suitable orientation) lead to a reaction. "
                "At lower temperatures a smaller fraction of collisions has enough kinetic energy, so the reaction "
                "proceeds more slowly."
            ),
            choices=[
                DraftChoice(
                    correct,
                    True,
                    "Correct: not all collisions result in a reaction, because many lack enough kinetic energy.",
                ),
                DraftChoice(
                    "The particles run out of kinetic energy after their first collision.",
                    False,
                    "Particles keep moving and colliding; kinetic energy is transferred, not used up.",
                ),
                DraftChoice(
                    f"The {rx['varied_reactant']} particles repel the other reactant so that they never collide.",
                    False,
                    "The particles do collide; the question is whether each collision has enough energy.",
                ),
                DraftChoice(
                    "The reaction can only happen after the solution has been heated above its boiling point.",
                    False,
                    "The reaction does occur at this temperature, just more slowly.",
                ),
            ],
        )

    def _q_predict_temperature_trial(self, params, rng: Rng) -> DraftQuestion:
        rx = self._rx(params)
        rows = params["experiment2"]
        i = rng.randint(0, len(rows) - 2)
        a, b = rows[i], rows[i + 1]
        t_new = (a["temperature"] + b["temperature"]) / 2
        lo, hi = sorted((a["value"], b["value"]))
        f = lambda v: f"{_fmt(v, rx['decimals'])} {rx['unit']}"  # noqa: E731
        timed = rx["measure"] == "time"
        correct = f"Between {f(lo)} and {f(hi)}"
        far = rows[-1] if i == 0 else rows[0]
        slower_than = f"More than {f(hi)}" if timed else f"Less than {f(lo)}"
        faster_than = f"Less than {f(lo)}" if timed else f"More than {f(hi)}"
        return DraftQuestion(
            stem=(
                f"Students repeat Experiment 2 at {t_new:g}°C with everything else the same. Which result for the "
                f"{rx['measure_short']} is most likely?"
            ),
            answer=correct,
            explanation=(
                f"{t_new:g}°C is between {a['temperature']}°C ({f(a['value'])}) and {b['temperature']}°C ({f(b['value'])}). "
                "The rate increases with temperature, so the reaction should be faster than at the lower temperature and "
                f"slower than at the higher one, giving a {rx['measure_short']} between those values."
            ),
            choices=[
                DraftChoice(
                    correct,
                    True,
                    "Correct: the rate should fall between the rates at the two neighboring temperatures.",
                ),
                DraftChoice(
                    slower_than,
                    False,
                    f"This would mean the reaction is slower than at {a['temperature']}°C, even though it is warmer.",
                ),
                DraftChoice(
                    faster_than,
                    False,
                    f"This would mean the reaction is faster than at {b['temperature']}°C, even though it is cooler.",
                ),
                DraftChoice(
                    f"Exactly {f(far['value'])}, the same as at {far['temperature']}°C",
                    False,
                    f"{far['temperature']}°C is not a neighboring temperature; the data show the rate changes with temperature.",
                ),
            ],
        )

    def _q_explain_with_evidence(self, params, rng: Rng) -> DraftQuestion:
        rx = self._rx(params)
        e1 = self._evidence_phrase(rx, params["experiment1"], "concentration", " mol/L")
        e2 = self._evidence_phrase(rx, params["experiment2"], "temperature", "°C")
        timed = rx["measure"] == "time"
        rate_note = (
            "Because a shorter time to reach the same endpoint means a faster reaction, both changes increased the rate."
            if timed
            else "Because more product formed in the same time, both changes increased the rate."
        )
        return DraftQuestion(
            stem=(
                "Using evidence from both experiments, describe how concentration and temperature each affected the rate "
                "of this reaction. Then explain each effect in terms of the number and energy of collisions between "
                "reactant particles."
            ),
            answer=(
                f"Experiment 1: as concentration increased, {e1}. Experiment 2: as temperature increased, {e2}. "
                f"{rate_note} Higher concentration means more particles per volume, so more collisions per second. "
                "Higher temperature means particles move faster, so they collide more often and a larger fraction of "
                "collisions have enough energy (activation energy) to break bonds and react."
            ),
            explanation=(
                "Scoring guide (4 points): (1) cites data showing the concentration effect; (2) cites data showing the "
                "temperature effect"
                + (" and interprets shorter times as faster rates" if timed else "")
                + "; (3) explains concentration with collision frequency; (4) explains temperature with collision "
                "frequency and energy, noting not all collisions react."
            ),
        )
