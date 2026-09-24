from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Course,
    GenerationRun,
    Question,
    QuestionStatusEvent,
    QuestionVersion,
    Standard,
    Stimulus,
)
from app.schemas import FamilyRef, QuestionEdit, StandardSummary
from app.services.engine.core import CHOICE_LABELS
from app.services.engine.family import QuestionFamily
from app.services.families.registry import FAMILIES, families_for_standard

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "generated": ("reviewed", "approved", "rejected", "archived"),
    "reviewed": ("approved", "rejected", "archived"),
    "approved": ("reviewed", "archived"),
    "rejected": ("reviewed", "archived"),
    "archived": ("reviewed",),
}
ASSESSABLE = ("generated", "reviewed", "approved")


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


def get_standard(db: Session, standard_id: int) -> Standard:
    std = db.scalar(
        select(Standard)
        .options(selectinload(Standard.course).selectinload(Course.source_document), selectinload(Standard.topics))
        .where(Standard.id == standard_id)
    )
    if std is None:
        raise not_found("Standard")
    return std


def standard_summary(std: Standard) -> StandardSummary:
    return StandardSummary(
        id=std.id,
        course_id=std.course_id,
        course_name=std.course.name,
        course_slug=std.course.slug,
        use_year=std.course.use_year,
        code=std.code,
        domain_code=std.domain_code,
        domain_name=std.domain_name,
        performance_expectation=std.performance_expectation,
        topics=[t.name for t in std.topics],
        question_family_candidate=std.question_family_candidate,
        repeat_of_biology_1=std.repeat_of_biology_1,
        families=[FamilyRef(key=f.key, title=f.title, version=f.version) for f in families_for_standard(std)],
    )


def resolve_family(std: Standard, family_key: str) -> QuestionFamily:
    family = FAMILIES.get(family_key)
    if family is None:
        raise not_found("Question family")
    if family not in families_for_standard(std):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{family.title} is not aligned to {std.code} ({std.course.name} {std.course.use_year})",
        )
    return family


def observable_text(std: Standard, category: str, index: int) -> str | None:
    bullets = std.observable_performances.get(category) or []
    return bullets[index] if index < len(bullets) else None


def build_provenance(std: Standard, family: QuestionFamily, generated: dict, group: dict, question: dict) -> dict:
    src = std.course.source_document
    template = family.template(question["template_key"])
    return {
        "standard": {
            "id": std.id,
            "code": std.code,
            "course": std.course.name,
            "state": std.course.state,
            "use_year": std.course.use_year,
            "performance_expectation": std.performance_expectation,
            "state_assessment_boundary": std.state_assessment_boundary,
            "content_sha256": std.content_sha256,
        },
        "source_document": {
            "title": src.title,
            "authority": src.authority,
            "published": src.published,
            "data_file": src.data_file,
            "content_sha256": src.content_sha256,
            "url": src.url,
        },
        "family": {"key": family.key, "version": family.version, "title": family.title},
        "template": {"key": template.key, "title": template.title, "dok": template.dok},
        "observable_performance": {
            "category": template.observable_category,
            "index": template.observable_index,
            "text": observable_text(std, template.observable_category, template.observable_index),
        },
        "seed": generated["seed"],
        "options": generated["options"],
        "group_index": group["index"],
        "attempt": question["attempt"],
        "generated_at": datetime.now(UTC).isoformat(),
    }


def save_generated(
    db: Session, std: Standard, family: QuestionFamily, generated: dict, *, owner_id: int
) -> tuple[GenerationRun, list[int]]:
    run = GenerationRun(
        created_by=owner_id,
        family_key=family.key,
        family_version=family.version,
        standard_id=std.id,
        seed=generated["seed"],
        options=generated["options"],
        parameters={"groups": [g["parameters"] for g in generated["groups"]]},
    )
    db.add(run)
    db.flush()
    ids: list[int] = []
    for group in generated["groups"]:
        stim = group["stimulus"]
        stimulus = Stimulus(run_id=run.id, kind=stim["kind"], title=stim.get("title") or "", body=stim)
        db.add(stimulus)
        db.flush()
        for q in group["questions"]:
            question = Question(
                standard_id=std.id,
                run_id=run.id,
                stimulus_id=stimulus.id,
                family_key=family.key,
                template_key=q["template_key"],
                status="generated",
                provenance=build_provenance(std, family, generated, group, q),
                current_version_no=1,
                owner_id=owner_id,
            )
            question.versions.append(
                QuestionVersion(
                    version_no=1,
                    origin="engine",
                    question_type=q["question_type"],
                    dok=q["dok"],
                    stem=q["stem"],
                    choices=q["choices"],
                    answer=q["answer"],
                    explanation=q["explanation"],
                    change_note=None,
                    created_by=owner_id,
                )
            )
            question.status_events.append(
                QuestionStatusEvent(from_status=None, to_status="generated", note=None, actor_id=owner_id)
            )
            db.add(question)
            db.flush()
            ids.append(question.id)
    return run, ids


def add_version(question: Question, edit: QuestionEdit, *, actor_id: int) -> QuestionVersion:
    current = question.current_version
    if current.question_type == "multiple_choice":
        if not 2 <= len(edit.choices) <= len(CHOICE_LABELS):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Multiple choice needs 2-5 choices")
        if sum(1 for c in edit.choices if c.correct) != 1:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mark exactly one choice as correct")
        texts = [" ".join(c.text.split()) for c in edit.choices]
        if len(set(texts)) != len(texts):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choices must be different from each other")
        choices = [
            {"label": CHOICE_LABELS[i], "text": c.text.strip(), "correct": c.correct, "rationale": c.rationale.strip()}
            for i, c in enumerate(edit.choices)
        ]
        key = next(c for c in choices if c["correct"])
        answer = f"{key['label']}. {key['text']}"
    else:
        if edit.choices:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Constructed-response items have no choices")
        if not edit.answer or not edit.answer.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide an exemplar answer")
        choices, answer = [], edit.answer.strip()

    unchanged = (
        edit.stem.strip() == current.stem
        and edit.dok == current.dok
        and choices == current.choices
        and answer == current.answer
        and edit.explanation.strip() == current.explanation
    )
    if unchanged:
        raise HTTPException(status.HTTP_409_CONFLICT, "No changes to save")

    version = QuestionVersion(
        version_no=max(v.version_no for v in question.versions) + 1,
        origin="teacher_edit",
        question_type=current.question_type,
        dok=edit.dok,
        stem=edit.stem.strip(),
        choices=choices,
        answer=answer,
        explanation=edit.explanation.strip(),
        change_note=(edit.change_note or "").strip() or None,
        created_by=actor_id,
    )
    question.versions.append(version)
    question.current_version_no = version.version_no
    return version


def change_status(question: Question, to_status: str, note: str | None, *, actor_id: int) -> None:
    allowed = TRANSITIONS[question.status]
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move a question from {question.status} to {to_status} (allowed: {', '.join(allowed)})",
        )
    question.status_events.append(
        QuestionStatusEvent(
            from_status=question.status,
            to_status=to_status,
            note=(note or "").strip() or None,
            actor_id=actor_id,
        )
    )
    question.status = to_status
