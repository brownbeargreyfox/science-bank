from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.models import Assessment, AssessmentItem, Course, Question, Standard
from app.schemas import (
    AddItems,
    AddItemsOut,
    AssessmentCreate,
    AssessmentDetail,
    AssessmentItemOut,
    AssessmentSummary,
    AssessmentUpdate,
    PrintBlock,
    PrintChoice,
    PrintOut,
    PrintQuestion,
    ReorderItems,
)
from app.services.bank import ASSESSABLE, not_found

router = APIRouter(prefix="/assessments", tags=["assessments"])


def _load(db: Session, assessment_id: int) -> Assessment:
    a = db.scalar(
        select(Assessment)
        .options(
            selectinload(Assessment.course),
            selectinload(Assessment.items).selectinload(AssessmentItem.question_version),
            selectinload(Assessment.items)
            .selectinload(AssessmentItem.question)
            .options(
                selectinload(Question.stimulus),
                selectinload(Question.standard).selectinload(Standard.course),
            ),
        )
        .where(Assessment.id == assessment_id)
    )
    if a is None:
        raise not_found("Assessment")
    return a


def _check_course(db: Session, course_id: int | None) -> None:
    if course_id is not None and db.get(Course, course_id) is None:
        raise not_found("Course")


def _summary(a: Assessment) -> AssessmentSummary:
    return AssessmentSummary(
        id=a.id,
        title=a.title,
        course_id=a.course_id,
        course_name=a.course.name if a.course else None,
        instructions=a.instructions,
        item_count=len(a.items),
        updated_at=a.updated_at,
    )


def _detail(a: Assessment) -> AssessmentDetail:
    items = []
    for it in a.items:
        q, v = it.question, it.question_version
        items.append(
            AssessmentItemOut(
                id=it.id,
                position=it.position,
                question_id=q.id,
                question_status=q.status,
                pinned_version_no=v.version_no,
                latest_version_no=q.current_version_no,
                standard_code=q.standard.code,
                course_name=q.standard.course.name,
                stimulus_id=q.stimulus_id,
                stimulus_title=q.stimulus.title if q.stimulus else None,
                dok=v.dok,
                question_type=v.question_type,
                stem=v.stem,
            )
        )
    coverage: dict[int, dict] = {}
    for it in a.items:
        std = it.question.standard
        entry = coverage.setdefault(
            std.id,
            {
                "standard_id": std.id,
                "code": std.code,
                "course": std.course.name,
                "count": 0,
                "performance_expectation": std.performance_expectation,
            },
        )
        entry["count"] += 1
    return AssessmentDetail(
        **_summary(a).model_dump(),
        items=items,
        dok_distribution={str(k): v for k, v in sorted(Counter(i.dok for i in items).items())},
        standards_coverage=sorted(coverage.values(), key=lambda e: e["code"]),
        question_type_counts=dict(Counter(i.question_type for i in items)),
    )


def _renumber(a: Assessment) -> None:
    for i, it in enumerate(sorted(a.items, key=lambda x: x.position), start=1):
        it.position = i


@router.get("", response_model=list[AssessmentSummary])
def list_assessments(db: Session = Depends(get_db)) -> list[AssessmentSummary]:
    rows = db.execute(
        select(Assessment, func.count(AssessmentItem.id))
        .outerjoin(AssessmentItem, AssessmentItem.assessment_id == Assessment.id)
        .options(selectinload(Assessment.course))
        .group_by(Assessment.id)
        .order_by(Assessment.updated_at.desc())
    ).all()
    return [
        AssessmentSummary(
            id=a.id,
            title=a.title,
            course_id=a.course_id,
            course_name=a.course.name if a.course else None,
            instructions=a.instructions,
            item_count=count,
            updated_at=a.updated_at,
        )
        for a, count in rows
    ]


@router.post("", response_model=AssessmentDetail, status_code=status.HTTP_201_CREATED)
def create_assessment(body: AssessmentCreate, db: Session = Depends(get_db)) -> AssessmentDetail:
    _check_course(db, body.course_id)
    a = Assessment(title=body.title.strip(), course_id=body.course_id, instructions=body.instructions.strip())
    db.add(a)
    db.commit()
    return _detail(_load(db, a.id))


@router.get("/{assessment_id}", response_model=AssessmentDetail)
def get_assessment(assessment_id: int, db: Session = Depends(get_db)) -> AssessmentDetail:
    return _detail(_load(db, assessment_id))


@router.patch("/{assessment_id}", response_model=AssessmentDetail)
def update_assessment(assessment_id: int, body: AssessmentUpdate, db: Session = Depends(get_db)) -> AssessmentDetail:
    a = _load(db, assessment_id)
    fields = body.model_fields_set
    if "title" in fields and body.title is not None:
        a.title = body.title.strip()
    if "instructions" in fields and body.instructions is not None:
        a.instructions = body.instructions.strip()
    if "course_id" in fields:
        _check_course(db, body.course_id)
        a.course_id = body.course_id
    db.commit()
    return _detail(_load(db, assessment_id))


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(assessment_id: int, db: Session = Depends(get_db)) -> Response:
    a = _load(db, assessment_id)
    db.delete(a)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{assessment_id}/items", response_model=AddItemsOut)
def add_items(assessment_id: int, body: AddItems, db: Session = Depends(get_db)) -> AddItemsOut:
    """Pin each question's current version. Items sharing a stimulus are kept next to each other."""
    a = _load(db, assessment_id)
    present = {it.question_id for it in a.items}
    questions = {
        q.id: q
        for q in db.scalars(
            select(Question).options(selectinload(Question.versions)).where(Question.id.in_(body.question_ids))
        ).all()
    }
    added, skipped = [], {}
    ordered = sorted(a.items, key=lambda x: x.position)
    for qid in dict.fromkeys(body.question_ids):
        q = questions.get(qid)
        if q is None:
            skipped[qid] = "not found"
        elif qid in present:
            skipped[qid] = "already in this assessment"
        elif q.status not in ASSESSABLE:
            skipped[qid] = f"status is {q.status}"
        else:
            item = AssessmentItem(question_id=q.id, question_version_id=q.current_version.id, position=0)
            item.question = q
            same_stim = [
                i for i, it in enumerate(ordered) if q.stimulus_id and it.question.stimulus_id == q.stimulus_id
            ]
            ordered.insert(same_stim[-1] + 1 if same_stim else len(ordered), item)
            a.items.append(item)
            present.add(qid)
            added.append(qid)
    for i, it in enumerate(ordered, start=1):
        it.position = i
    db.commit()
    return AddItemsOut(added=added, skipped=skipped)


@router.delete("/{assessment_id}/items/{item_id}", response_model=AssessmentDetail)
def remove_item(assessment_id: int, item_id: int, db: Session = Depends(get_db)) -> AssessmentDetail:
    a = _load(db, assessment_id)
    item = next((it for it in a.items if it.id == item_id), None)
    if item is None:
        raise not_found("Item")
    a.items.remove(item)
    _renumber(a)
    db.commit()
    return _detail(_load(db, assessment_id))


@router.put("/{assessment_id}/items/order", response_model=AssessmentDetail)
def reorder_items(assessment_id: int, body: ReorderItems, db: Session = Depends(get_db)) -> AssessmentDetail:
    a = _load(db, assessment_id)
    by_id = {it.id: it for it in a.items}
    if sorted(body.item_ids) != sorted(by_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "item_ids must list every item exactly once")
    for i, item_id in enumerate(body.item_ids, start=1):
        by_id[item_id].position = i
    db.commit()
    return _detail(_load(db, assessment_id))


@router.post("/{assessment_id}/items/{item_id}/refresh", response_model=AssessmentDetail)
def refresh_item(assessment_id: int, item_id: int, db: Session = Depends(get_db)) -> AssessmentDetail:
    """Re-pin an item to its question's latest version."""
    a = _load(db, assessment_id)
    item = next((it for it in a.items if it.id == item_id), None)
    if item is None:
        raise not_found("Item")
    q = db.scalar(select(Question).options(selectinload(Question.versions)).where(Question.id == item.question_id))
    item.question_version_id = q.current_version.id
    db.commit()
    return _detail(_load(db, assessment_id))


@router.get("/{assessment_id}/print", response_model=PrintOut, response_model_exclude_none=True)
def print_view(
    assessment_id: int,
    variant: Literal["teacher", "student"] = Query(default="student"),
    db: Session = Depends(get_db),
) -> PrintOut:
    """Printable content. The student variant is built without any key data at all."""
    a = _load(db, assessment_id)
    teacher = variant == "teacher"
    blocks: list[PrintBlock] = []
    number = 0
    for it in sorted(a.items, key=lambda x: x.position):
        q, v = it.question, it.question_version
        number += 1
        choices = [
            PrintChoice(label=c["label"], text=c["text"], correct=c["correct"], rationale=c["rationale"])
            if teacher
            else PrintChoice(label=c["label"], text=c["text"])
            for c in v.choices
        ]
        pq = PrintQuestion(
            number=number,
            question_type=v.question_type,
            dok=v.dok,
            standard_code=q.standard.code,
            stem=v.stem,
            choices=choices,
            answer=v.answer if teacher else None,
            explanation=v.explanation if teacher else None,
            teacher_edited=(v.origin == "teacher_edit") if teacher else None,
        )
        stim = q.stimulus
        if (
            blocks
            and stim is not None
            and blocks[-1].stimulus is not None
            and blocks[-1].stimulus.get("_id") == stim.id
        ):
            blocks[-1].questions.append(pq)
        else:
            body = {**stim.body, "_id": stim.id} if stim else None
            blocks.append(PrintBlock(stimulus=body, stimulus_title=stim.title if stim else None, questions=[pq]))
    standards = None
    if teacher:
        seen: dict[str, dict] = {}
        for it in a.items:
            std = it.question.standard
            seen.setdefault(
                f"{std.course.name}|{std.code}",
                {
                    "code": std.code,
                    "course": std.course.name,
                    "use_year": std.course.use_year,
                    "performance_expectation": std.performance_expectation,
                },
            )
        standards = sorted(seen.values(), key=lambda s: (s["course"], s["code"]))
    return PrintOut(
        variant=variant,
        title=a.title,
        course_name=a.course.name if a.course else None,
        instructions=a.instructions,
        question_count=number,
        blocks=blocks,
        standards=standards,
    )
