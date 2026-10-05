"""B-LS4-3: statistical analysis of changing distributions of heritable traits.

All counts, percentages, and fitness measures shown to students are stored in the scenario. The
family uses only basic proportion and graphical analysis; it never calculates allele frequency.
"""

from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily

MAX_DRAWS = 300
TOTALS = (140, 80, 120, 100)

CASES: dict[str, dict[str, Any]] = {
    "beetles": {
        "organism": "ground beetles",
        "trait": "shell color",
        "trait_type": "anatomical",
        "condition": "The soil on the hillside is dark.",
        "intro": "Parents pass shell color to their offspring. Birds find beetles that match the dark soil less easily.",
        "favors": "a",
        "variants": {
            "a": {"label": "Dark-shelled beetles", "noun": "dark-shelled beetles"},
            "b": {"label": "Light-shelled beetles", "noun": "light-shelled beetles"},
        },
    },
    "finches": {
        "organism": "finches",
        "trait": "beak thickness",
        "trait_type": "anatomical",
        "condition": "Most seeds on the island are soft.",
        "intro": "Parents pass beak thickness to their offspring. Thin beaks eat the soft seeds more easily.",
        "favors": "b",
        "variants": {
            "a": {"label": "Thick-beaked finches", "noun": "thick-beaked finches"},
            "b": {"label": "Thin-beaked finches", "noun": "thin-beaked finches"},
        },
    },
    "minnows": {
        "organism": "pond minnows",
        "trait": "reaction speed",
        "trait_type": "behavioral",
        "condition": "Predatory fish live in the pond.",
        "intro": "Parents pass reaction speed to their offspring. Minnows that react quickly are more likely to escape predators.",
        "favors": "a",
        "variants": {
            "a": {"label": "Quick-reacting minnows", "noun": "quick-reacting minnows"},
            "b": {"label": "Slow-reacting minnows", "noun": "slow-reacting minnows"},
        },
    },
    "shrubs": {
        "organism": "desert shrubs",
        "trait": "root depth",
        "trait_type": "anatomical",
        "condition": "Rain is frequent on the plain.",
        "intro": "Parents pass root depth to their offspring. Shallow roots take up surface water quickly after rain.",
        "favors": "b",
        "variants": {
            "a": {"label": "Deep-rooted shrubs", "noun": "deep-rooted shrubs"},
            "b": {"label": "Shallow-rooted shrubs", "noun": "shallow-rooted shrubs"},
        },
    },
    "marsh_grass": {
        "organism": "marsh grass plants",
        "trait": "salt tolerance",
        "trait_type": "physiological",
        "condition": "Salt water reaches the marsh soil during high tides.",
        "intro": "Parents pass salt tolerance to their offspring. Salt-tolerant plants keep functioning in the salty soil.",
        "favors": "a",
        "variants": {
            "a": {"label": "Salt-tolerant marsh grass", "noun": "salt-tolerant marsh grass"},
            "b": {"label": "Less salt-tolerant marsh grass", "noun": "less salt-tolerant marsh grass"},
        },
    },
    "lizards": {
        "organism": "desert lizards",
        "trait": "water conservation",
        "trait_type": "physiological",
        "condition": "Rainwater pools remain in the desert valley.",
        "intro": "Parents pass water-conservation ability to their offspring. Lizards that conserve less water can spend more time feeding near the pools.",
        "favors": "b",
        "variants": {
            "a": {"label": "High-conservation lizards", "noun": "high-conservation lizards"},
            "b": {"label": "Low-conservation lizards", "noun": "low-conservation lizards"},
        },
    },
}


def _other(variant: str) -> str:
    return "b" if variant == "a" else "a"


def _pct(count: int, total: int) -> int:
    return round(100 * count / total)


def next_proportion(proportion: float, favored_rate: float, other_rate: float) -> float:
    """Relative-fitness update for the proportion of the favored variant."""
    return proportion * favored_rate / (proportion * favored_rate + (1 - proportion) * other_rate)


def draw_distribution(rng: Rng, favored: str) -> list[dict[str, int]]:
    """Return four unequal survey samples with a clear proportional trend and a raw-count trap."""
    for _ in range(MAX_DRAWS):
        proportion = rng.uniform(0.22, 0.32)
        own, other = round(rng.uniform(0.66, 0.76), 2), round(rng.uniform(0.48, 0.56), 2)
        proportions = [proportion]
        for _ in range(3):
            proportions.append(next_proportion(proportions[-1], own, other))
        rows = []
        for time, (total, p) in enumerate(zip(TOTALS, proportions, strict=True), start=1):
            count = round(total * p)
            values = {favored: count, _other(favored): total - count}
            rows.append({"time": time, "total": total, "a": values["a"], "b": values["b"]})
        favored_pcts = [_pct(row[favored], row["total"]) for row in rows]
        raw_counts = [row[favored] for row in rows]
        if any(not 2 <= row[v] <= row["total"] - 2 for row in rows for v in ("a", "b")):
            continue
        if favored_pcts[-1] - favored_pcts[0] < 15:
            continue
        if min(b - a for a, b in zip(favored_pcts, favored_pcts[1:])) < 3:
            continue
        if not any(b < a for a, b in zip(raw_counts, raw_counts[1:])):
            continue
        return rows
    raise GenerationError("trait-distribution-shifts: no valid distribution after redraw limit")


def draw_fitness(rng: Rng, favored: str) -> dict[str, Any]:
    """Draw rate data; half of scenarios make raw survivor count favor the wrong variant."""
    trap = rng.choice([True, False])
    for _ in range(MAX_DRAWS):
        favored_started, other_started = (40, 85) if trap else (85, 40)
        favored_started += 5 * rng.randint(0, 1)
        other_started += 5 * rng.randint(0, 1)
        favored_survival = round(rng.uniform(0.72, 0.82), 2)
        other_survival = round(rng.uniform(0.42, 0.54), 2)
        favored_offspring = round(rng.uniform(0.70, 0.84), 2)
        other_offspring = round(rng.uniform(0.30, 0.46), 2)
        starts = {favored: favored_started, _other(favored): other_started}
        survived = {v: round(starts[v] * (favored_survival if v == favored else other_survival)) for v in starts}
        offspring = {v: round(starts[v] * (favored_offspring if v == favored else other_offspring)) for v in starts}
        survival_rates = {v: survived[v] / starts[v] for v in starts}
        offspring_rates = {v: offspring[v] / starts[v] for v in starts}
        raw_trap = survived[favored] < survived[_other(favored)]
        if raw_trap != trap:
            continue
        if survival_rates[favored] - survival_rates[_other(favored)] < 0.15:
            continue
        if offspring_rates[favored] - offspring_rates[_other(favored)] < 0.20:
            continue
        return {
            "trap": trap,
            "rows": [
                {
                    "variant": variant,
                    "started": starts[variant],
                    "survived": survived[variant],
                    "offspring": offspring[variant],
                }
                for variant in ("a", "b")
            ],
        }
    raise GenerationError("trait-distribution-shifts: no valid fitness comparison after redraw limit")


def draw_scenario(rng: Rng) -> dict[str, Any]:
    case_key = rng.choice(sorted(CASES))
    case = CASES[case_key]
    favored = case["favors"]
    return {
        "case": case_key,
        "favored": favored,
        "rows": draw_distribution(rng, favored),
        "fitness": draw_fitness(rng, favored),
    }


class TraitDistributionShifts(QuestionFamily):
    key = "trait-distribution-shifts"
    version = "1.0.0"
    title = "Trait distribution shifts"
    description = (
        "Analyze proportions and fitness rates to explain shifts in a heritable trait's distribution over time."
    )
    stimulus_kind = "trait_distribution_shifts"
    bindings = (Binding("SC", "biology-2", "B-LS4-3"),)
    templates = (
        TemplateSpec("represent_distribution", "Read a trait distribution", 1, "multiple_choice", "organizing_data", 0),
        TemplateSpec(
            "calculate_proportion", "Calculate a trait proportion", 1, "multiple_choice", "identifying_relationships", 0
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

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        case = CASES[params["case"]]
        labels = case["variants"]
        distribution_keys = {"represent_distribution", "calculate_proportion", "analyze_distribution_shift"}
        both_keys = {"support_selection_claim", "explain_shift_with_data"}
        keys = set(template_keys)
        tables: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        if keys & (distribution_keys | both_keys):
            rows = [
                {**row, "a_pct": _pct(row["a"], row["total"]), "b_pct": _pct(row["b"], row["total"])}
                for row in params["rows"]
            ]
            tables.append(
                {
                    "caption": f"Trait distribution in sampled {case['organism']}",
                    "columns": [
                        {"key": "time", "label": "Sample time"},
                        {"key": "total", "label": "Total sampled"},
                        {"key": "a", "label": labels["a"]["label"]},
                        {"key": "b", "label": labels["b"]["label"]},
                    ],
                    "rows": rows,
                }
            )
            charts.append(
                {
                    "type": "line",
                    "title": f"Percentage of sampled {case['organism']} with each variant",
                    "x": {"key": "time", "label": "Sample time"},
                    "y": {"label": "Percentage of sample", "min": 0},
                    "series": [
                        {"key": "a_pct", "label": labels["a"]["label"]},
                        {"key": "b_pct", "label": labels["b"]["label"]},
                    ],
                    "table_index": 0,
                }
            )
        if "interpret_fitness_rate" in keys or keys & both_keys:
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
                            "variant": labels[row["variant"]]["label"],
                            **{key: row[key] for key in ("started", "survived", "offspring")},
                        }
                        for row in params["fitness"]["rows"]
                    ],
                }
            )
        return {
            "title": "Trait distributions in a population",
            "intro": f"{case['intro']} {case['condition']}",
            "sections": [],
            "tables": tables,
            "charts": charts,
        }

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _labels(self, params: dict[str, Any]) -> dict[str, dict[str, str]]:
        return CASES[params["case"]]["variants"]

    def _q_represent_distribution(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, row = self._labels(params), rng.choice(params["rows"])
        variant = rng.choice(["a", "b"])
        pct = _pct(row[variant], row["total"])
        other = _pct(row[_other(variant)], row["total"])
        texts = [
            f"About {pct}% of the sample had {labels[variant]['noun']}.",
            f"{row[variant]}% of the sample had {labels[variant]['noun']}.",
            f"About {other}% of the sample had {labels[variant]['noun']}.",
            "The table does not show the total sampled, so the proportion cannot be found.",
        ]
        return self._mc(
            f"At sample time {row['time']}, which statement accurately represents the distribution?",
            texts,
            0,
            f"{row[variant]} of {row['total']} is about {pct}%.",
        )

    def _q_calculate_proportion(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, row = self._labels(params), rng.choice(params["rows"])
        variant = rng.choice(["a", "b"])
        pct, other = _pct(row[variant], row["total"]), _pct(row[_other(variant)], row["total"])
        wrong = max(0, min(100, pct + rng.choice([-10, 10])))
        texts = [f"{pct}%", f"{row[variant]}%", f"{other}%", f"{wrong}%"]
        return self._mc(
            f"What percentage of the sample at time {row['time']} was {labels[variant]['noun']}?",
            texts,
            0,
            f"{row[variant]} divided by {row['total']} is about {pct}%.",
        )

    def _q_analyze_distribution_shift(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._labels(params), params["favored"]
        first, last = params["rows"][0], params["rows"][-1]
        first_pct, last_pct = _pct(first[favored], first["total"]), _pct(last[favored], last["total"])
        texts = [
            f"{labels[favored]['label']} changed from about {first_pct}% to about {last_pct}% of the sample.",
            f"{labels[favored]['label']} had {last[favored]} individuals in the last sample, so its proportion increased.",
            f"{labels[_other(favored)]['label']} changed from about {_pct(first[_other(favored)], first['total'])}% to about {_pct(last[_other(favored)], last['total'])}% of the sample.",
            "The distribution stayed the same because each sample contains two variants.",
        ]
        return self._mc(
            "Which comparison best supports that one heritable variant increased in proportion over the study?",
            texts,
            0,
            f"The displayed percentages rise from {first_pct}% to {last_pct}%.",
        )

    def _q_interpret_fitness_rate(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._labels(params), params["favored"]
        rows = {row["variant"]: row for row in params["fitness"]["rows"]}
        other = _other(favored)
        fav_rate, other_rate = (
            _pct(rows[favored]["survived"], rows[favored]["started"]),
            _pct(rows[other]["survived"], rows[other]["started"]),
        )
        texts = [
            f"{labels[favored]['label']} had the higher survival rate.",
            f"{labels[other]['label']} had the higher survival rate.",
            "The variant with more survivors had the higher survival rate.",
            "The two variants had the same survival rate.",
        ]
        return self._mc(
            "Which statement about fitness is supported by the survival table?",
            texts,
            0,
            f"The survival rates are {fav_rate}% and {other_rate}%, respectively.",
        )

    def _q_support_selection_claim(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._labels(params), params["favored"]
        noun = labels[favored]["noun"]
        texts = [
            f"Because {noun} are heritable and had higher survival and offspring rates, their increasing proportion is evidence of natural selection.",
            f"{noun.capitalize()} changed during the study because the organisms needed the trait to survive.",
            "The proportion increased even though reproductive success does not affect natural selection.",
            "A favorable variant increases in every condition, whether or not it is inherited.",
        ]
        return self._mc(
            "Which claim is best supported by both tables?",
            texts,
            0,
            "The tables show a heritable variant with higher rates and a rising proportion.",
        )

    def _q_explain_shift_with_data(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case, labels, favored = CASES[params["case"]], self._labels(params), params["favored"]
        first, last = params["rows"][0], params["rows"][-1]
        fit = {row["variant"]: row for row in params["fitness"]["rows"]}[favored]
        first_pct, last_pct = _pct(first[favored], first["total"]), _pct(last[favored], last["total"])
        survival, offspring = _pct(fit["survived"], fit["started"]), _pct(fit["offspring"], fit["started"])
        answer = (
            f"{labels[favored]['label']} are the {case['trait_type']} variant whose proportion increased from about {first_pct}% "
            f"at sample time {first['time']} to about {last_pct}% at sample time {last['time']}. Their survival rate was "
            f"{survival}% and their offspring-per-starter rate was {offspring}%. Because parents pass this trait to offspring, "
            "higher survival and reproduction can make this variant more common in the population over time."
        )
        return DraftQuestion(
            stem="Use both tables to explain the change in the distribution of the heritable trait. Include data and describe the trait type.",
            answer=answer,
            explanation="Scoring guide (4 points): (1) identify the trait type and changing variant; (2) cite two proportions; (3) cite normalized fitness evidence; (4) connect heritability, survival, and reproduction to the population change.",
        )

    @staticmethod
    def _mc(stem: str, texts: list[str], correct_index: int, explanation: str) -> DraftQuestion:
        return DraftQuestion(
            stem=stem,
            answer=texts[correct_index],
            explanation=explanation,
            choices=[
                DraftChoice(
                    text,
                    index == correct_index,
                    ("Correct: " if index == correct_index else "Not supported: ") + explanation,
                )
                for index, text in enumerate(texts)
            ],
        )
