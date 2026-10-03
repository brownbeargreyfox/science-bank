"""Natural selection and adaptation (B-LS4-4): trait counts over generations after an environmental change.

Curated, fictional cases only. Each displayed generation is exactly 100 sampled individuals, and every key is computed
from the counts the student sees. The Biology 1 boundary excludes allele frequency calculations, so items speak only of
the fraction of the population with a trait, and always at the level of the population across generations (never
individuals changing because they need to). Resistance cases are fictional lab cultures with no health claim.
"""

from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily

SAMPLE = 100
MAX_DRAWS = 300
SIZES = tuple(range(40, 90, 5))

# Each case: two heritable variants of one trait and two environments, each favouring one variant. Sentences are
# complete: `is` describes the state, `became` the change into it, `returns` the change back into it later.
CASES: dict[str, dict[str, Any]] = {
    "beetles": {
        "organism": "ground beetles",
        "trait": "shell color",
        "intro": (
            "A population of ground beetles lives on a hillside. Shell color varies among the beetles, and parents pass "
            "their shell color to their offspring. Birds that eat beetles find it harder to see beetles that match the soil."
        ),
        "variants": {
            "a": {"label": "Dark-shelled beetles", "noun": "dark-shelled beetles"},
            "b": {"label": "Light-shelled beetles", "noun": "light-shelled beetles"},
        },
        "envs": {
            "dark_soil": {
                "favors": "a",
                "is": "The hillside soil is dark.",
                "became": "The hillside soil became dark.",
                "returns": "The hillside soil becomes dark again.",
            },
            "light_soil": {
                "favors": "b",
                "is": "The hillside soil is light.",
                "became": "The hillside soil became light.",
                "returns": "The hillside soil becomes light again.",
            },
        },
    },
    "bacteria": {
        "organism": "soil bacteria",
        "trait": "resistance to Compound Zeta",
        "intro": (
            "A lab culture contains a fictional soil bacterium. Some of the bacteria are resistant to Compound Zeta, a "
            "fictional chemical that stops the growth of bacteria that are not resistant. Resistance is passed from parent "
            "cells to the cells they produce. When Compound Zeta is absent, resistant bacteria grow more slowly than "
            "bacteria that are not resistant."
        ),
        "variants": {
            "a": {"label": "Resistant bacteria", "noun": "resistant bacteria"},
            "b": {"label": "Non-resistant bacteria", "noun": "non-resistant bacteria"},
        },
        "envs": {
            "with_zeta": {
                "favors": "a",
                "is": "Compound Zeta is in the culture.",
                "became": "Compound Zeta was added to the culture.",
                "returns": "Compound Zeta is added to the culture again.",
            },
            "without_zeta": {
                "favors": "b",
                "is": "There is no Compound Zeta in the culture.",
                "became": "Compound Zeta was removed from the culture.",
                "returns": "Compound Zeta is removed from the culture again.",
            },
        },
    },
    "finches": {
        "organism": "finches",
        "trait": "beak thickness",
        "intro": (
            "A population of finches lives on an island. Beak thickness varies among the finches, and parents pass their "
            "beak thickness to their offspring. Finches with thick beaks crack hard seeds more easily, and finches with "
            "thin beaks eat soft seeds more easily."
        ),
        "variants": {
            "a": {"label": "Thick-beaked finches", "noun": "thick-beaked finches"},
            "b": {"label": "Thin-beaked finches", "noun": "thin-beaked finches"},
        },
        "envs": {
            "hard_seeds": {
                "favors": "a",
                "is": "Most of the seeds on the island are hard.",
                "became": "Most of the seeds on the island became hard.",
                "returns": "Most of the seeds on the island become hard again.",
            },
            "soft_seeds": {
                "favors": "b",
                "is": "Most of the seeds on the island are soft.",
                "became": "Most of the seeds on the island became soft.",
                "returns": "Most of the seeds on the island become soft again.",
            },
        },
    },
    "hares": {
        "organism": "marsh hares",
        "trait": "winter fur color",
        "intro": (
            "A population of marsh hares lives in a cold region. Winter fur color varies among the hares, and parents pass "
            "their fur color to their offspring. Predators find it harder to see hares that match the ground."
        ),
        "variants": {
            "a": {"label": "White-furred hares", "noun": "white-furred hares"},
            "b": {"label": "Brown-furred hares", "noun": "brown-furred hares"},
        },
        "envs": {
            "snow": {
                "favors": "a",
                "is": "Snow covers the ground all winter.",
                "became": "Snow began to cover the ground all winter.",
                "returns": "Snow covers the ground all winter again.",
            },
            "bare": {
                "favors": "b",
                "is": "The ground stays bare all winter.",
                "became": "The ground began to stay bare all winter.",
                "returns": "The ground stays bare all winter again.",
            },
        },
    },
    "minnows": {
        "organism": "pond minnows",
        "trait": "reaction speed",
        "intro": (
            "A population of minnows lives in a pond. Some minnows react quickly to danger and others react slowly, and "
            "parents pass their reaction speed to their offspring. Reacting quickly uses extra energy."
        ),
        "variants": {
            "a": {"label": "Quick-reacting minnows", "noun": "quick-reacting minnows"},
            "b": {"label": "Slow-reacting minnows", "noun": "slow-reacting minnows"},
        },
        "envs": {
            "predators": {
                "favors": "a",
                "is": "Predatory fish live in the pond.",
                "became": "Predatory fish were added to the pond.",
                "returns": "Predatory fish are added to the pond again.",
            },
            "no_predators": {
                "favors": "b",
                "is": "There are no predatory fish in the pond.",
                "became": "The predatory fish were removed from the pond.",
                "returns": "The predatory fish are removed from the pond again.",
            },
        },
    },
    "shrubs": {
        "organism": "desert shrubs",
        "trait": "root depth",
        "intro": (
            "A population of desert shrubs grows on a plain. Root depth varies among the shrubs, and parents pass their "
            "root depth to their offspring. Deep roots reach water far below the surface, and shallow roots take up "
            "surface water quickly after rain."
        ),
        "variants": {
            "a": {"label": "Deep-rooted shrubs", "noun": "deep-rooted shrubs"},
            "b": {"label": "Shallow-rooted shrubs", "noun": "shallow-rooted shrubs"},
        },
        "envs": {
            "dry": {
                "favors": "a",
                "is": "Rain is rare on the plain.",
                "became": "Rain became rare on the plain.",
                "returns": "Rain becomes rare on the plain again.",
            },
            "wet": {
                "favors": "b",
                "is": "Rain is frequent on the plain.",
                "became": "Rain became frequent on the plain.",
                "returns": "Rain becomes frequent on the plain again.",
            },
        },
    },
}


# ---- the data ----------------------------------------------------------------------------------


def next_count(count: int, own: float, other: float) -> int:
    """Count (out of 100) of a variant after one generation, given its survival rate and the other variant's."""
    p = count / SAMPLE
    return round(SAMPLE * p * own / (p * own + (1 - p) * other))


def draw_trajectory(rng: Rng) -> dict[str, Any]:
    """Counts of the variant favoured in the first environment over `l1 + l2` transitions, with the change after `l1`."""
    for _ in range(MAX_DRAWS):
        l1, l2 = rng.randint(3, 4), rng.randint(3, 4)
        fav1, unf1 = round(rng.uniform(0.74, 0.90), 2), round(rng.uniform(0.35, 0.55), 2)
        fav2, unf2 = round(rng.uniform(0.74, 0.90), 2), round(rng.uniform(0.35, 0.55), 2)
        counts = [rng.randint(18, 32)]
        for step in range(l1 + l2):
            if step < l1:
                counts.append(next_count(counts[-1], fav1, unf1))
            else:
                counts.append(next_count(counts[-1], unf2, fav2))
        rises = [b - a for a, b in zip(counts[:l1], counts[1 : l1 + 1])]
        falls = [a - b for a, b in zip(counts[l1:-1], counts[l1 + 1 :])]
        if min(rises) < 3 or min(falls) < 3 or min(counts) < 2 or max(counts) > 98:
            continue
        if counts[l1] - counts[0] < 25 or counts[l1] < 60 or counts[-1] > 45 or counts[l1] - counts[-1] < 20:
            continue
        return {"l1": l1, "l2": l2, "counts": counts, "fav1": fav1, "unf1": unf1}
    raise GenerationError(f"natural-selection-trend: no valid trajectory after {MAX_DRAWS} draws")


def draw_survival(rng: Rng, fav1: float, unf1: float, trap: bool) -> dict[str, Any] | None:
    """A one-season experiment in the first environment, or None if these rates cannot make one. A trap is a draw where
    the variant with the higher survival rate has fewer survivors, so comparing counts alone gives the wrong answer."""
    for _ in range(40):
        if trap:
            started_fav, started_other = rng.choice(SIZES[:4]), rng.choice(SIZES[-4:])
        else:
            started_fav, started_other = rng.choice(SIZES), rng.choice(SIZES)
        survived_fav = min(started_fav, max(0, round(started_fav * (fav1 + rng.uniform(-0.03, 0.03)))))
        survived_other = min(started_other, max(0, round(started_other * (unf1 + rng.uniform(-0.03, 0.03)))))
        if survived_fav / started_fav - survived_other / started_other < 0.15 or survived_fav == survived_other:
            continue
        if trap != (survived_fav < survived_other):
            continue
        return {
            "trap": trap,
            "fav": {"started": started_fav, "survived": survived_fav},
            "other": {"started": started_other, "survived": survived_other},
        }
    return None


def draw_scenario(rng: Rng) -> dict[str, Any]:
    case_key = rng.choice(sorted(CASES))
    case = CASES[case_key]
    env_first, env_second = rng.shuffled(sorted(case["envs"]))
    first_favors = case["envs"][env_first]["favors"]
    second_favors = case["envs"][env_second]["favors"]
    trap = rng.random() < 0.5  # about half of the survival experiments are traps
    for _ in range(MAX_DRAWS):
        trajectory = draw_trajectory(rng)
        survival = draw_survival(rng, trajectory["fav1"], trajectory["unf1"], trap)
        if survival is not None:
            break
    else:
        raise GenerationError(f"natural-selection-trend: no valid survival experiment after {MAX_DRAWS} draws")
    rows = []
    for generation, first_count in enumerate(trajectory["counts"]):
        a = first_count if first_favors == "a" else SAMPLE - first_count
        rows.append({"generation": generation, "a": a, "b": SAMPLE - a})
    survival_rows = {first_favors: survival["fav"], second_favors: survival["other"]}
    return {
        "case": case_key,
        "env_first": env_first,
        "env_second": env_second,
        "first_favors": first_favors,
        "second_favors": second_favors,
        "l1": trajectory["l1"],
        "l2": trajectory["l2"],
        "rows": rows,
        "survival": {
            "trap": survival["trap"],
            "rows": [{"variant": v, **survival_rows[v]} for v in ("a", "b")],
        },
    }


# ---- family ------------------------------------------------------------------------------------

_GENERATION_KEYS = {
    "trait_trend",
    "effect_of_change",
    "explain_adaptation",
    "predict_new_change",
    "explain_with_data",
}


def _case(params: dict[str, Any]) -> dict[str, Any]:
    return CASES[params["case"]]


def _other(variant: str) -> str:
    return "b" if variant == "a" else "a"


def _pct(survived: int, started: int) -> str:
    return f"{round(100 * survived / started)}%"


class NaturalSelectionTrend(QuestionFamily):
    key = "natural-selection-trend"
    version = "1.0.0"
    title = "Natural selection and adaptation"
    description = (
        "Use counts of two heritable variants across generations, and an environmental change, to compare survival "
        "rates, read trends in the fraction of a population with a trait, explain how natural selection leads to "
        "adaptation, and predict the direction of change when the environment reverses."
    )
    stimulus_kind = "natural_selection_trend"
    bindings = (Binding("SC", "biology-1", "B-LS4-4"),)
    templates = (
        TemplateSpec("compare_survival", "Compare survival rates", 1, "multiple_choice", "evidence", 1),
        TemplateSpec("trait_trend", "Read a trend in a trait", 2, "multiple_choice", "reasoning", 1),
    )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        keys = set(template_keys)
        case = _case(params)
        first, second = case["envs"][params["env_first"]], case["envs"][params["env_second"]]
        a, b = case["variants"]["a"], case["variants"]["b"]
        intro = f"{case['intro']} {first['is']}"
        tables: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        if keys & _GENERATION_KEYS:
            intro += f" The environment changed after generation {params['l1']}. {second['became']}"
            tables.append(
                {
                    "caption": f"{case['organism'].capitalize()} in each generation, out of {SAMPLE} sampled",
                    "columns": [
                        {"key": "generation", "label": "Generation"},
                        {"key": "a", "label": a["label"]},
                        {"key": "b", "label": b["label"]},
                    ],
                    "rows": params["rows"],
                }
            )
            charts.append(
                {
                    "type": "line",
                    "title": f"{case['organism'].capitalize()} with each {case['trait']} over the generations",
                    "x": {"key": "generation", "label": "Generation"},
                    "y": {"label": f"Individuals out of {SAMPLE}", "min": 0},
                    "series": [{"key": "a", "label": a["label"]}, {"key": "b", "label": b["label"]}],
                    "table_index": 0,
                }
            )
        if "compare_survival" in keys:
            tables.append(
                {
                    "caption": "Survival through one season in the first environment",
                    "columns": [
                        {"key": "variant", "label": "Variant"},
                        {"key": "started", "label": "Started"},
                        {"key": "survived", "label": "Survived"},
                    ],
                    "rows": [
                        {
                            "variant": case["variants"][r["variant"]]["label"],
                            "started": r["started"],
                            "survived": r["survived"],
                        }
                        for r in params["survival"]["rows"]
                    ],
                }
            )
        return {
            "title": "Natural selection in a population",
            "intro": intro,
            "sections": [],
            "tables": tables,
            "charts": charts,
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_compare_survival(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        rows = {r["variant"]: r for r in params["survival"]["rows"]}
        label = {v: case["variants"][v]["label"] for v in ("a", "b")}
        rate = {v: rows[v]["survived"] / rows[v]["started"] for v in rows}
        facts = " ".join(
            f"{label[v]}: {rows[v]['survived']} of {rows[v]['started']} survived ({_pct(rows[v]['survived'], rows[v]['started'])})."
            for v in ("a", "b")
        )
        winner = "a" if rate["a"] > rate["b"] else "b"
        texts = {
            "a": f"{label['a']} had the higher survival rate.",
            "b": f"{label['b']} had the higher survival rate.",
            "same": "The two variants had the same survival rate.",
            "incomparable": "The survival rates cannot be compared, because the groups started with different numbers.",
        }
        why = {
            winner: f"Correct: {facts} A survival rate is the fraction that survived, so {label[winner]} had the higher rate.",
            _other(winner): f"Not supported: {facts} The higher rate belongs to {label[winner]}.",
            "same": f"Not supported: {facts} The two rates are not the same.",
            "incomparable": (
                "Not supported: a survival rate (the number that survived out of the number that started) can be "
                f"compared even when the groups started with different numbers. {facts}"
            ),
        }
        choices = [DraftChoice(texts[name], name == winner, why[name]) for name in texts]
        return DraftQuestion(
            stem=(
                "Scientists counted how many individuals of each variant started a season and how many survived. "
                f"{case['envs'][params['env_first']]['is']} Which statement is supported by the survival table?"
            ),
            answer=texts[winner],
            explanation=f"{facts} {label[winner]} had the higher survival rate.",
            choices=choices,
        )

    def _q_trait_trend(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case = _case(params)
        variant = rng.choice(["a", "b"])
        noun = case["variants"][variant]["noun"]
        l1 = params["l1"]
        start, end = params["rows"][0][variant], params["rows"][l1][variant]
        direction = "increased" if end > start else "decreased"
        texts = {
            "increased": f"The fraction of the population that is {noun} increased.",
            "decreased": f"The fraction of the population that is {noun} decreased.",
            "same": f"The fraction of the population that is {noun} stayed about the same.",
            "unknown": f"The change in the fraction of {noun} cannot be determined from the table.",
        }
        facts = f"{noun.capitalize()} went from {start} out of {SAMPLE} in generation 0 to {end} out of {SAMPLE} in generation {l1}."
        choices = [
            DraftChoice(
                texts[name], name == direction, f"Correct: {facts}" if name == direction else f"Not supported: {facts}"
            )
            for name in texts
        ]
        return DraftQuestion(
            stem=(
                f"Look at the generation table. How did the fraction of the population that is {noun} change from "
                f"generation 0 to generation {l1}?"
            ),
            answer=texts[direction],
            explanation=f"{facts} The fraction {direction}.",
            choices=choices,
        )
