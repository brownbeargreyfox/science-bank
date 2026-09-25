from abc import ABC, abstractmethod
from typing import Any

from app.services.engine.core import (
    Binding,
    DraftQuestion,
    GenerationError,
    Rng,
    TemplateSpec,
    finalize_choices,
)

MAX_ATTEMPTS = 12
MAX_QUANTITY = 40


class QuestionFamily(ABC):
    key: str
    version: str
    title: str
    description: str
    stimulus_kind: str
    bindings: tuple[Binding, ...]
    templates: tuple[TemplateSpec, ...]

    @abstractmethod
    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        """Draw one scientifically valid scenario. Must be JSON-serializable and contain every
        value the stimulus displays, so keys can be computed from exactly what students see."""

    @abstractmethod
    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        """Return {title, intro, sections?, tables, charts} for the web/print renderer, including only
        the parts the chosen templates need. Each chart points at the table holding its data
        (table_index), which doubles as the accessible text alternative."""

    @abstractmethod
    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        """Build one item. Raise GenerationError if this rng draw yields an ambiguous item."""

    def template(self, key: str) -> TemplateSpec:
        for t in self.templates:
            if t.key == key:
                return t
        raise KeyError(key)

    def binding_for_template(self, template: TemplateSpec) -> Binding:
        if template.standard_code is None:
            if len(self.bindings) != 1:
                raise GenerationError(f"{self.key}/{template.key}: multi-standard template needs a standard code")
            return self.bindings[0]
        matches = [binding for binding in self.bindings if binding.code == template.standard_code]
        if len(matches) != 1:
            raise GenerationError(
                f"{self.key}/{template.key}: unknown or ambiguous standard code {template.standard_code}"
            )
        return matches[0]

    def catalog(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "stimulus_kind": self.stimulus_kind,
            "bindings": [b.__dict__ for b in self.bindings],
            "templates": [t.__dict__ for t in self.templates],
        }


def select_templates(
    family: QuestionFamily,
    doks: list[int] | None = None,
    question_types: list[str] | None = None,
    template_keys: list[str] | None = None,
) -> list[TemplateSpec]:
    return [
        t
        for t in family.templates
        if (not doks or t.dok in doks)
        and (not question_types or t.question_type in question_types)
        and (not template_keys or t.key in template_keys)
    ]


def generate_set(
    family: QuestionFamily,
    seed: str,
    quantity: int,
    doks: list[int] | None = None,
    question_types: list[str] | None = None,
    template_keys: list[str] | None = None,
) -> dict[str, Any]:
    if not 1 <= quantity <= MAX_QUANTITY:
        raise GenerationError(f"quantity must be between 1 and {MAX_QUANTITY}")
    eligible = select_templates(family, doks, question_types, template_keys)
    if not eligible:
        raise GenerationError("no question templates in this family match the selected filters")

    groups = []
    remaining = quantity
    group_index = 0
    while remaining > 0:
        base = (family.key, family.version, seed, group_index)
        params = family.build_scenario(Rng(*base, "scenario"))
        take = min(remaining, len(eligible))
        chosen_keys = {t.key for t in Rng(*base, "select").sample(eligible, take)}
        chosen = [t for t in eligible if t.key in chosen_keys]
        questions = [_build_one(family, t, params, base) for t in chosen]
        for question, template in zip(questions, chosen, strict=True):
            if template.standard_code is not None:
                question["standard_code"] = family.binding_for_template(template).code
        groups.append(
            {
                "index": group_index,
                "parameters": params,
                "stimulus": {
                    "kind": family.stimulus_kind,
                    **family.render_stimulus(params, [t.key for t in chosen]),
                },
                "questions": questions,
            }
        )
        remaining -= take
        group_index += 1

    return {
        "family_key": family.key,
        "family_version": family.version,
        "seed": seed,
        "options": {
            "quantity": quantity,
            "doks": doks or [],
            "question_types": question_types or [],
            "template_keys": template_keys or [],
        },
        "groups": groups,
    }


def _build_one(family: QuestionFamily, template: TemplateSpec, params: dict, base: tuple) -> dict[str, Any]:
    last_error: GenerationError | None = None
    for attempt in range(MAX_ATTEMPTS):
        rng = Rng(*base, template.key, attempt)
        try:
            draft = family.build_question(template, params, rng)
            choices = finalize_choices(rng, draft) if template.question_type == "multiple_choice" else []
        except GenerationError as exc:
            last_error = exc
            continue
        if template.question_type == "multiple_choice":
            correct = next(c for c in choices if c["correct"])
            answer = f"{correct['label']}. {correct['text']}"
        else:
            answer = draft.answer
        return {
            "template_key": template.key,
            "title": template.title,
            "dok": template.dok,
            "question_type": template.question_type,
            "stem": draft.stem,
            "choices": choices,
            "answer": answer,
            "explanation": draft.explanation,
            "observable": {"category": template.observable_category, "index": template.observable_index},
            "attempt": attempt,
        }
    raise GenerationError(f"{family.key}/{template.key}: could not build an unambiguous item ({last_error})")
