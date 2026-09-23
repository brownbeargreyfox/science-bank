"""Deterministic question-family engine primitives.

Reproducibility rules (see tests/test_engine_determinism.py):
- Sub-seeds come from sha256 over explicit parts, never Python's per-process-salted hash().
- Randomness is drawn only through Rng, which uses nothing but random.Random.random(); CPython
  guarantees that stream across versions, unlike choices()/shuffle()/randint()/sample().
- Answer keys and distractors are computed from exactly the values that are rendered to the student.
"""

import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

T = TypeVar("T")

QuestionType = Literal["multiple_choice", "constructed_response"]
CHOICE_LABELS = "ABCDE"


def derive_seed(*parts: object) -> int:
    digest = hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


class Rng:
    def __init__(self, *seed_parts: object) -> None:
        self._r = random.Random(derive_seed(*seed_parts))

    def random(self) -> float:
        return self._r.random()

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self._r.random()

    def randint(self, low: int, high: int) -> int:
        return low + min(int(self._r.random() * (high - low + 1)), high - low)

    def choice(self, items: Sequence[T]) -> T:
        return items[self.randint(0, len(items) - 1)]

    def shuffled(self, items: Sequence[T]) -> list[T]:
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.randint(0, i)
            out[i], out[j] = out[j], out[i]
        return out

    def sample(self, items: Sequence[T], k: int) -> list[T]:
        return self.shuffled(items)[:k]


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Binding:
    """Which exact standard (state + course + PE code) a family may generate for."""

    state: str
    course_slug: str
    code: str


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    title: str
    dok: int
    question_type: QuestionType
    # Cites the SCDE "observable features of student performance" bullet this template elicits.
    observable_category: str
    observable_index: int


@dataclass
class DraftChoice:
    text: str
    correct: bool
    rationale: str


@dataclass
class DraftQuestion:
    stem: str
    answer: str
    explanation: str
    choices: list[DraftChoice] = field(default_factory=list)


def finalize_choices(rng: Rng, draft: DraftQuestion) -> list[dict[str, Any]]:
    """Validate a multiple-choice draft and assign shuffled letter labels."""
    correct = [c for c in draft.choices if c.correct]
    if len(correct) != 1:
        raise GenerationError(f"expected exactly one correct choice, got {len(correct)}")
    # Case-sensitive on purpose: genotypes such as "BB" and "bb" are different answers.
    normalized = [" ".join(c.text.split()) for c in draft.choices]
    if len(set(normalized)) != len(normalized):
        raise GenerationError(f"duplicate choice text: {[c.text for c in draft.choices]}")
    if not 3 <= len(draft.choices) <= len(CHOICE_LABELS):
        raise GenerationError("multiple choice needs 3-5 options")
    return [
        {"label": CHOICE_LABELS[i], "text": c.text, "correct": c.correct, "rationale": c.rationale}
        for i, c in enumerate(rng.shuffled(draft.choices))
    ]


def fmt_num(value: float, decimals: int = 0) -> str:
    if decimals == 0:
        return f"{round(value):,}"
    return f"{value:,.{decimals}f}"


def fmt_pct(fraction: float) -> str:
    pct = fraction * 100
    return f"{pct:g}%" if abs(pct - round(pct, 1)) < 1e-9 else f"{pct:.1f}%"
