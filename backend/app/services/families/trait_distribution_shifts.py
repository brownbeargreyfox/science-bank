"""B-LS4-3: statistical analysis of changing distributions of heritable traits (Biology 2).

Every count, percentage and rate shown to students is stored in the scenario. Each multiple-choice item is built from
claims whose truth is computed from that stored data, and the builder requires exactly one true claim, so a distractor
that happens to be true redraws the item instead of reaching a student. Only basic proportion arithmetic is used; the
family never calculates an allele frequency.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from itertools import combinations
from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily

MAX_DRAWS = 400
TOTAL_CHOICES = tuple(t for t in range(80, 145, 5) if t != 100)
ROUNDING_NOTE = "Percentages are rounded to the nearest whole number; a half rounds up."

CASES: dict[str, dict[str, Any]] = {
    "beetles": {
        "organism": "ground beetles",
        "trait": "shell color",
        "trait_type": "anatomical",
        "place": "on the dark hillside soil",
        "intro": "Parents pass shell color to their offspring. Birds that eat the beetles find dark-shelled beetles harder to see against dark soil.",
        "condition": "The soil on the hillside is dark.",
        "favored": "a",
        "variants": {
            "a": {"label": "Dark-shelled beetles", "noun": "dark-shelled beetles"},
            "b": {"label": "Light-shelled beetles", "noun": "light-shelled beetles"},
        },
    },
    "finches": {
        "organism": "finches",
        "trait": "beak thickness",
        "trait_type": "anatomical",
        "place": "on the island where most seeds are soft",
        "intro": "Parents pass beak thickness to their offspring. Finches with thin beaks eat soft seeds more easily than finches with thick beaks do.",
        "condition": "Most seeds on the island are soft.",
        "favored": "b",
        "variants": {
            "a": {"label": "Thick-beaked finches", "noun": "thick-beaked finches"},
            "b": {"label": "Thin-beaked finches", "noun": "thin-beaked finches"},
        },
    },
    "minnows": {
        "organism": "pond minnows",
        "trait": "reaction speed",
        "trait_type": "behavioral",
        "place": "in the pond with predatory fish",
        "intro": "Parents pass reaction speed to their offspring. Minnows that react quickly escape predatory fish more often than slow-reacting minnows do.",
        "condition": "Predatory fish live in the pond.",
        "favored": "a",
        "variants": {
            "a": {"label": "Quick-reacting minnows", "noun": "quick-reacting minnows"},
            "b": {"label": "Slow-reacting minnows", "noun": "slow-reacting minnows"},
        },
    },
    "shrubs": {
        "organism": "desert shrubs",
        "trait": "root depth",
        "trait_type": "anatomical",
        "place": "on the plain where rain wets only the top layer of soil",
        "intro": "Parents pass root depth to their offspring. Shallow roots take up water from the top layer of soil before it dries.",
        "condition": "Rain falls often but wets only the top layer of the soil.",
        "favored": "b",
        "variants": {
            "a": {"label": "Deep-rooted shrubs", "noun": "deep-rooted shrubs"},
            "b": {"label": "Shallow-rooted shrubs", "noun": "shallow-rooted shrubs"},
        },
    },
    "marsh_grass": {
        "organism": "marsh grass plants",
        "trait": "salt tolerance",
        "trait_type": "physiological",
        "place": "in the salty marsh soil",
        "intro": "Parents pass salt tolerance to their offspring. Salt-tolerant plants keep growing in salty soil.",
        "condition": "Salt water reaches the marsh soil at high tide.",
        "favored": "a",
        "variants": {
            "a": {"label": "Salt-tolerant marsh grass plants", "noun": "salt-tolerant marsh grass plants"},
            "b": {"label": "Less salt-tolerant marsh grass plants", "noun": "less salt-tolerant marsh grass plants"},
        },
    },
    "lizards": {
        "organism": "desert lizards",
        "trait": "water conservation",
        "trait_type": "physiological",
        "place": "in the dry desert valley",
        "intro": "Parents pass water-conservation ability to their offspring. Lizards that conserve more water lose less of it on dry days.",
        "condition": "Rain is rare, and the water holes dry up early in the season.",
        "favored": "a",
        "variants": {
            "a": {"label": "High-conservation lizards", "noun": "high-conservation lizards"},
            "b": {"label": "Low-conservation lizards", "noun": "low-conservation lizards"},
        },
    },
}


# Distractor patterns for the support item (every one has a need-based distractor): (heritability clause, evidence clause); P = passed on, X = not passed on,
# N = changed because it was needed, D = the groups differed, E = they did equally well. The key is (P, D). Every pattern
# keeps the key from being the only choice with its value in either clause.
SUPPORT_PATTERNS = (
    (("P", "E"), ("N", "D"), ("X", "D")),
    (("P", "E"), ("N", "D"), ("N", "E")),
    (("P", "E"), ("N", "D"), ("X", "E")),
    (("P", "E"), ("X", "D"), ("N", "E")),
)


def _other(variant: str) -> str:
    return "b" if variant == "a" else "a"


def _pct(count: int, total: int) -> int:
    """Whole-number percentage, half up (students round .5 up; Python's round() does not)."""
    return int((Decimal(100 * count) / Decimal(total)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _article(trait_type: str) -> str:
    return "an" if trait_type[0] in "aeiou" else "a"


def next_proportion(proportion: float, favored_rate: float, other_rate: float) -> float:
    """Relative-fitness update for the proportion of the favored variant."""
    return proportion * favored_rate / (proportion * favored_rate + (1 - proportion) * other_rate)


def draw_distribution(rng: Rng, favored: str) -> tuple[list[dict[str, int]], list[int]]:
    """Four unequal samples with a clear proportional trend and a window where the raw count falls but the share rises."""
    for _ in range(MAX_DRAWS):
        totals = rng.sample(list(TOTAL_CHOICES), 4)
        proportion = rng.uniform(0.20, 0.30)
        own, other = round(rng.uniform(0.66, 0.78), 2), round(rng.uniform(0.46, 0.56), 2)
        proportions = [proportion]
        for _ in range(3):
            proportions.append(next_proportion(proportions[-1], own, other))
        rows = []
        for time, (total, p) in enumerate(zip(totals, proportions, strict=True), start=1):
            count = round(total * p)
            values = {favored: count, _other(favored): total - count}
            rows.append({"time": time, "total": total, "a": values["a"], "b": values["b"]})
        if any(not 2 <= row[v] <= row["total"] - 2 for row in rows for v in ("a", "b")):
            continue
        pcts = [_pct(row[favored], row["total"]) for row in rows]
        if pcts[-1] - pcts[0] < 15 or min(b - a for a, b in zip(pcts, pcts[1:])) < 3:
            continue
        windows = [i for i in range(3) if rows[i + 1][favored] < rows[i][favored]]
        if not windows:
            continue
        window = rng.choice(windows)
        return rows, [window, window + 1]
    raise GenerationError("trait-distribution-shifts: no valid distribution after redraw limit")


def pooled_errors(
    rows: list[dict[str, int]], first: int, second: int, variant: str
) -> tuple[int, list[tuple[int, str]]]:
    """The pooled percentage of `variant` over two samples, and the classic wrong answers (value, rationale)."""
    r1, r2, other = rows[first], rows[second], _other(variant)
    count_sum, total_sum = r1[variant] + r2[variant], r1["total"] + r2["total"]
    key = _pct(count_sum, total_sum)
    p1, p2 = _pct(r1[variant], r1["total"]), _pct(r2[variant], r2["total"])
    mean = int(
        ((Decimal(100 * r1[variant]) / r1["total"] + Decimal(100 * r2[variant]) / r2["total"]) / 2).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    errors = [
        (
            mean,
            f"This averages the two percentages ({p1}% and {p2}%). The samples have different totals, so the combined percentage comes from the combined counts, which give {key}%.",
        ),
        (count_sum, f"{count_sum} is the combined count, not a percentage; the combined percentage is {key}%."),
        (p1, f"{p1}% is the percentage for sample time {r1['time']} alone; the combined percentage is {key}%."),
        (p2, f"{p2}% is the percentage for sample time {r2['time']} alone; the combined percentage is {key}%."),
        (
            _pct(r1[other] + r2[other], total_sum),
            f"{_pct(r1[other] + r2[other], total_sum)}% is the combined percentage of the other variant; the combined percentage of this variant is {key}%.",
        ),
    ]
    return key, errors


def usable_errors(key: int, errors: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Wrong answers that are distinct, below 100 (a larger percent would cue the key) and 3 or more points from the key."""
    seen: set[int] = {key}
    usable = []
    for value, why in errors:
        if value not in seen and value <= 99 and abs(value - key) >= 3:
            seen.add(value)
            usable.append((value, why))
    return usable


def spaced_triples(key: int, errors: list[tuple[int, str]]) -> list[tuple[tuple[int, str], ...]]:
    """Every choice of three wrong answers that are also 3 or more points from each other."""
    return [
        triple
        for triple in combinations(usable_errors(key, errors), 3)
        if all(abs(a[0] - b[0]) >= 3 for a, b in combinations(triple, 2))
    ]


def choose_pooled(rng: Rng, rows: list[dict[str, int]]) -> dict[str, Any] | None:
    """A pair of samples and a variant whose pooled percentage is shown nowhere and has three usable wrong answers."""
    options = [(i, j, v) for i in range(4) for j in range(i + 1, 4) for v in ("a", "b")]
    for first, second, variant in rng.shuffled(options):
        key, errors = pooled_errors(rows, first, second, variant)
        if key in {_pct(row[variant], row["total"]) for row in rows} or not spaced_triples(key, errors):
            continue
        return {"first": first, "second": second, "variant": variant}
    return None


def draw_fitness(rng: Rng, favored: str) -> dict[str, Any]:
    """Survival and offspring for one interval; about half the draws give the favored variant fewer raw survivors."""
    trap = rng.choice([True, False])
    for _ in range(MAX_DRAWS):
        big, small = 5 * rng.randint(14, 18), 5 * rng.randint(8, 11)
        favored_big = rng.choice([True, False])
        starts = {favored: big if favored_big else small, _other(favored): small if favored_big else big}
        favored_survival, other_survival = round(rng.uniform(0.72, 0.84), 2), round(rng.uniform(0.42, 0.54), 2)
        favored_offspring, other_offspring = round(rng.uniform(0.70, 0.84), 2), round(rng.uniform(0.30, 0.46), 2)
        survived = {v: round(starts[v] * (favored_survival if v == favored else other_survival)) for v in starts}
        offspring = {v: round(starts[v] * (favored_offspring if v == favored else other_offspring)) for v in starts}
        other = _other(favored)
        if (survived[favored] < survived[other]) != trap:
            continue
        if Fraction(survived[favored], starts[favored]) - Fraction(survived[other], starts[other]) < Fraction(15, 100):
            continue
        if Fraction(offspring[favored], starts[favored]) - Fraction(offspring[other], starts[other]) < Fraction(
            20, 100
        ):
            continue
        return {
            "trap": trap,
            "rows": [
                {"variant": v, "started": starts[v], "survived": survived[v], "offspring": offspring[v]}
                for v in ("a", "b")
            ],
        }
    raise GenerationError("trait-distribution-shifts: no valid fitness comparison after redraw limit")


def draw_scenario(rng: Rng) -> dict[str, Any]:
    case_key = rng.choice(sorted(CASES))
    favored = CASES[case_key]["favored"]
    for _ in range(MAX_DRAWS):
        rows, window = draw_distribution(rng, favored)
        pooled = choose_pooled(rng, rows)
        if pooled is not None:
            return {
                "case": case_key,
                "favored": favored,
                "swap": rng.choice([True, False]),
                "rows": rows,
                "window": window,
                "pooled": pooled,
                "fitness": draw_fitness(rng, favored),
            }
    raise GenerationError("trait-distribution-shifts: no scenario with a hidden pooled proportion")


@dataclass
class Claim:
    text: str
    holds: bool
    why: str


class TraitDistributionShifts(QuestionFamily):
    key = "trait-distribution-shifts"
    version = "1.1.0"
    title = "Trait distribution shifts"
    description = (
        "Analyze proportions and fitness rates to explain shifts in a heritable trait's distribution over time."
    )
    stimulus_kind = "trait_distribution_shifts"
    bindings = (Binding("SC", "biology-2", "B-LS4-3"),)
    templates = (
        TemplateSpec("represent_distribution", "Read a trait distribution", 1, "multiple_choice", "organizing_data", 0),
        TemplateSpec(
            "calculate_proportion",
            "Calculate a pooled trait proportion",
            1,
            "multiple_choice",
            "identifying_relationships",
            0,
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

    # ---- helpers ----------------------------------------------------------------------------

    @staticmethod
    def _order(params: dict[str, Any]) -> list[str]:
        return ["b", "a"] if params["swap"] else ["a", "b"]

    @staticmethod
    def _variants(params: dict[str, Any]) -> dict[str, dict[str, str]]:
        return CASES[params["case"]]["variants"]

    @staticmethod
    def _fitness(params: dict[str, Any]) -> dict[str, dict[str, int]]:
        return {row["variant"]: row for row in params["fitness"]["rows"]}

    @staticmethod
    def _mc(stem: str, claims: list[Claim]) -> DraftQuestion:
        if sum(c.holds for c in claims) != 1:
            raise GenerationError("trait-distribution-shifts: not exactly one true claim")
        key = next(c for c in claims if c.holds)
        return DraftQuestion(
            stem=stem,
            answer=key.text,
            explanation=key.why,
            choices=[DraftChoice(c.text, c.holds, c.why) for c in claims],
        )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        case, labels, order = CASES[params["case"]], self._variants(params), self._order(params)
        keys = set(template_keys)
        chart_items = {
            "represent_distribution",
            "analyze_distribution_shift",
            "support_selection_claim",
            "explain_shift_with_data",
        }
        needs_distribution = keys & (chart_items | {"calculate_proportion"})
        with_chart = bool(keys & chart_items)
        tables: list[dict[str, Any]] = []
        charts: list[dict[str, Any]] = []
        intro = [case["intro"], case["condition"]]
        if needs_distribution:
            columns = [{"key": "time", "label": "Sample time"}, {"key": "total", "label": "Total sampled"}]
            columns += [{"key": v, "label": labels[v]["label"]} for v in order]
            rows = [dict(row) for row in params["rows"]]
            if with_chart:
                columns += [{"key": f"{v}_pct", "label": f"{labels[v]['label']} (percent of sample)"} for v in order]
                for row in rows:
                    for v in ("a", "b"):
                        row[f"{v}_pct"] = _pct(row[v], row["total"])
            intro.append(ROUNDING_NOTE)
            tables.append(
                {"caption": f"Trait distribution in sampled {case['organism']}", "columns": columns, "rows": rows}
            )
            if with_chart:
                charts.append(
                    {
                        "type": "line",
                        "title": f"Percentage of sampled {case['organism']} with each variant",
                        "x": {"key": "time", "label": "Sample time"},
                        "y": {"label": "Percentage of sample", "min": 0},
                        "series": [{"key": f"{v}_pct", "label": labels[v]["label"]} for v in order],
                        "table_index": 0,
                    }
                )
        if keys & {"interpret_fitness_rate", "support_selection_claim", "explain_shift_with_data"}:
            fitness = self._fitness(params)
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
                            "variant": labels[v]["label"],
                            "started": fitness[v]["started"],
                            "survived": fitness[v]["survived"],
                            "offspring": fitness[v]["offspring"],
                        }
                        for v in order
                    ],
                }
            )
        return {
            "title": "Trait distributions in a population",
            "intro": " ".join(intro),
            "sections": [],
            "tables": tables,
            "charts": charts,
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_represent_distribution(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, row = self._variants(params), rng.choice(params["rows"])
        variant = rng.choice(["a", "b"])
        noun = labels[variant]["noun"]
        actual = _pct(row[variant], row["total"])
        other = _pct(row[_other(variant)], row["total"])

        def pct_claim(number: int, why: str) -> Claim:
            return Claim(f"About {number}% of the sample had {noun}.", _pct(row[variant], row["total"]) == number, why)

        claims = [
            pct_claim(actual, f"{row[variant]} of {row['total']} is about {actual}%."),
            pct_claim(
                row[variant],
                f"{row[variant]} is the count of {noun}, not a percentage; {row[variant]} of {row['total']} is about {actual}%.",
            ),
            pct_claim(
                other,
                f"{other}% is the share of the other variant ({row[_other(variant)]} of {row['total']}); {noun} were about {actual}%.",
            ),
            Claim(
                "The table does not show the total sampled, so the proportion cannot be found.",
                False,
                f"The table shows the total sampled at each time ({row['total']} at time {row['time']}), so the proportion can be found.",
            ),
        ]
        pooled = params["pooled"]
        pooled_key = pooled_errors(params["rows"], pooled["first"], pooled["second"], pooled["variant"])[0]
        shown = [actual, row[variant], other]
        if (
            row[variant] > 99
            or any(abs(a - b) < 3 for a, b in combinations(shown, 2))
            or any(re.search(rf"(?<!\d){pooled_key}%", claim.text) for claim in claims)
        ):
            raise GenerationError(
                "trait-distribution-shifts: represent choices too close, over 99, or repeat the pooled key"
            )
        return self._mc(
            f"At sample time {row['time']}, which statement accurately represents the distribution?", claims
        )

    def _q_calculate_proportion(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, rows, pooled = self._variants(params), params["rows"], params["pooled"]
        first, second, variant = pooled["first"], pooled["second"], pooled["variant"]
        r1, r2 = rows[first], rows[second]
        key, errors = pooled_errors(rows, first, second, variant)
        noun = labels[variant]["noun"]
        chosen = rng.choice(spaced_triples(key, errors))
        claims = [
            Claim(
                f"{key}%",
                True,
                f"Combine the counts first: ({r1[variant]} + {r2[variant]}) divided by ({r1['total']} + {r2['total']}) is about {key}%.",
            )
        ] + [Claim(f"{value}%", False, why) for value, why in chosen]
        return self._mc(
            f"What percentage of all the individuals sampled at sample times {r1['time']} and {r2['time']} "
            f"combined were {noun}, to the nearest whole percent? Combine the counts from the two samples first.",
            claims,
        )

    def _q_analyze_distribution_shift(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._variants(params), params["favored"]
        other = _other(favored)
        first, second = params["window"]
        r1, r2 = params["rows"][first], params["rows"][second]

        def change(variant: str) -> int:
            return _pct(r2[variant], r2["total"]) - _pct(r1[variant], r1["total"])

        shift = change(favored)

        def claim(variant: str, direction: str, amount: int, why: str) -> Claim:
            actual = change(variant)
            holds = (
                (direction == "rose" and actual == amount and amount > 0)
                or (direction == "fell" and actual == -amount and amount > 0)
                or (direction == "did not change" and actual == 0 and amount == 0)
            )
            what = (
                "did not change (by about 0 percentage points)"
                if direction == "did not change"
                else f"{direction} by about {amount} percentage points"
            )
            text = (
                f"The share of {labels[variant]['noun']} in the sample {what} from sample time {r1['time']} "
                f"to sample time {r2['time']}, and the count of {labels[variant]['noun']} went from {r1[variant]} to {r2[variant]}."
            )
            return Claim(text, holds, why)

        favored_noun = labels[favored]["noun"]
        claims = [
            claim(
                favored,
                "rose",
                shift,
                f"The share of {favored_noun} was about {_pct(r1[favored], r1['total'])}% and then about {_pct(r2[favored], r2['total'])}%, a rise of {shift} points, even though the count went from {r1[favored]} to {r2[favored]}.",
            ),
            claim(
                favored,
                "fell",
                shift,
                f"The count of {favored_noun} went from {r1[favored]} to {r2[favored]}, but the totals sampled were different ({r1['total']} and {r2['total']}), so the share rose by {shift} points.",
            ),
            claim(
                other,
                "rose",
                shift,
                f"The share of {labels[other]['noun']} went from about {_pct(r1[other], r1['total'])}% to about {_pct(r2[other], r2['total'])}%, so it fell, not rose.",
            ),
            claim(
                favored,
                "did not change",
                0,
                f"A different total sampled does not mean the share stayed the same; the share of {favored_noun} changed by {shift} points.",
            ),
        ]
        return self._mc(
            f"Which statement about the share of each variant from sample time {r1['time']} to sample time "
            f"{r2['time']} is supported by the table and graph?",
            claims,
        )

    def _q_interpret_fitness_rate(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        labels, favored = self._variants(params), params["favored"]
        other = _other(favored)
        rows = self._fitness(params)
        measure = rng.choice(["survived", "offspring"])
        rate = {v: Fraction(rows[v][measure], rows[v]["started"]) for v in rows}
        per = {v: _pct(rows[v][measure], rows[v]["started"]) for v in rows}
        word = "survival rate" if measure == "survived" else "number of offspring per starting individual"

        def higher(variant: str) -> str:
            label = labels[variant]["label"]
            return (
                f"{label} had the higher survival rate."
                if measure == "survived"
                else f"{label} produced more offspring per starting individual."
            )

        def numbers(variant: str) -> str:
            row = rows[variant]
            if measure == "survived":
                return f"{row['survived']} of {row['started']} survived ({per[variant]} per 100 starters)"
            return (
                f"{row['started']} started and produced {row['offspring']} offspring ({per[variant]} per 100 starters)"
            )

        def lower_note(variant: str, rival: str) -> str:
            more = rows[variant][measure] > rows[rival][measure]
            lead = (
                f"{labels[variant]['label']} had a larger count ({rows[variant][measure]}) but started with more individuals. "
                if more
                else ""
            )
            return f"{lead}{numbers(variant)} compared with {numbers(rival)}."

        claims = [
            Claim(
                higher(favored),
                rate[favored] > rate[other],
                f"Compare rates, not counts: {numbers(favored)}, compared with {numbers(other)}.",
            ),
            Claim(
                higher(other),
                rate[other] > rate[favored],
                f"Not supported. {lower_note(other, favored)} Their rate is lower.",
            ),
            Claim(
                f"The two variants had the same {word}."
                if measure == "survived"
                else "The two variants produced the same number of offspring per starting individual.",
                rate[favored] == rate[other],
                f"Not supported. The rates are {per[favored]} and {per[other]} per 100 starters.",
            ),
            Claim(
                f"The {word}s cannot be compared because the two groups started with different numbers."
                if measure == "survived"
                else "The offspring rates cannot be compared because the two groups started with different numbers.",
                False,
                "Not supported. Dividing by the number that started puts the groups on the same scale, so the rates can be compared.",
            ),
        ]
        return self._mc(
            f"Which statement about the {word} of the two variants is supported by the survival and offspring table?",
            claims,
        )

    def _q_support_selection_claim(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case, labels, favored = CASES[params["case"]], self._variants(params), params["favored"]
        other = _other(favored)
        rows = self._fitness(params)
        fav_noun, other_noun = labels[favored]["noun"], labels[other]["noun"]
        trait = case["trait"]
        groups = (
            f"the {fav_noun} (started with {rows[favored]['started']}) and the {other_noun} "
            f"(started with {rows[other]['started']})"
        )
        survival_same = Fraction(rows[favored]["survived"], rows[favored]["started"]) == Fraction(
            rows[other]["survived"], rows[other]["started"]
        )
        conclusion = f"the change in the distribution of {trait} is evidence of natural selection"
        heritage = {
            "P": f"{trait.capitalize()} is passed from parents to offspring",
            "X": f"{trait.capitalize()} is not passed from parents to offspring",
            "N": f"Individual {case['organism']} changed their {trait} because they needed it",
        }
        evidence = {
            "D": "differed in how well they survived and reproduced",
            "E": "survived and reproduced equally well",
        }
        heritage_why = {
            "X": f"The stimulus states that parents pass {trait} to their offspring, and selection acts only on heritable traits.",
            "N": "Individuals do not change a heritable trait because they need it; the share of a variant changes when its members survive and reproduce more.",
        }
        evidence_why = "The survival table shows the two groups did not survive and reproduce at the same rates."

        def claim(heritage_key: str, evidence_key: str) -> Claim:
            text = f"{heritage[heritage_key]}, and {case['place']}, {groups} {evidence[evidence_key]}, so {conclusion}."
            holds = heritage_key == "P" and (evidence_key == "D") == (not survival_same)
            if holds:
                why = "Correct: the trait is inherited and the two groups survived and reproduced at different rates, so a change in the share of one variant can be evidence of natural selection."
            else:
                reasons = []
                if heritage_key != "P":
                    reasons.append(heritage_why[heritage_key])
                if evidence_key == "E":
                    reasons.append(evidence_why)
                why = "Not supported. " + " ".join(reasons)
            return Claim(text, holds, why)

        # The key differs from each distractor in one or two clauses, and the pattern varies, so no clause majority points to it.
        claims = [claim("P", "D")] + [claim(h, e) for h, e in rng.choice(SUPPORT_PATTERNS)]
        return self._mc(
            f"Which explanation of the change in the distribution of {trait} is best supported by the data?", claims
        )

    def _q_explain_shift_with_data(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        case, labels, favored = CASES[params["case"]], self._variants(params), params["favored"]
        other = _other(favored)
        rows = params["rows"]
        first, last = rows[0], rows[-1]
        fit = self._fitness(params)
        p_first, p_last = _pct(first[favored], first["total"]), _pct(last[favored], last["total"])
        survival = {v: _pct(fit[v]["survived"], fit[v]["started"]) for v in fit}
        offspring = {v: _pct(fit[v]["offspring"], fit[v]["started"]) for v in fit}
        fav_label, fav_noun, other_noun = labels[favored]["label"], labels[favored]["noun"], labels[other]["noun"]
        kind = case["trait_type"]
        answer = (
            f"The share of {fav_noun} rose from about {p_first}% at sample time {first['time']} to about {p_last}% at "
            f"sample time {last['time']}. {case['trait'].capitalize()} is {_article(kind)} {kind} trait that parents pass "
            f"to their offspring. In the survival table, {fav_noun} had a survival rate of {survival[favored]}% and "
            f"produced {offspring[favored]} offspring per 100 starting individuals, compared with {survival[other]}% and "
            f"{offspring[other]} for {other_noun}. Because the trait is inherited and {fav_noun} survived and reproduced at "
            f"higher rates, their share of the population increased. The change did not happen because individual "
            f"organisms changed to meet a need."
        )
        return DraftQuestion(
            stem=(
                f"Use both tables and the graph to explain the change in the distribution of {case['trait']} in these "
                f"{case['organism']}. Include data from the tables, and say what type of trait it is."
            ),
            answer=answer,
            explanation=(
                "Scoring guide (4 points): (1) identify the trait type (anatomical, behavioral or physiological) and the "
                f"variant whose share changed ({fav_label}); (2) cite two percentages from the table or graph; (3) cite "
                "the survival or offspring rates, computed from the starting numbers, as the evidence for the fitness "
                "difference; (4) explain that the trait is passed from parents to offspring, so higher survival and "
                "reproduction can increase the variant's share over time. Do not give credit for an explanation in which "
                "individual organisms change because they need to."
            ),
        )
