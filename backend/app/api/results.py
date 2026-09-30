"""Review surfaces: the question summary across visible administrations, and per-question usage."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Administration,
    AdministrationItem,
    Assessment,
    ItemResult,
    Question,
    QuestionVersion,
    Standard,
    User,
)
from app.schemas import QuestionRef, ResultsSummaryPage, SummaryRow, UsageEntry, UsagePage
from app.services.administrations import visible_clauses
from app.services.bank import not_found
from app.services.results import accuracy, limited_responses

router = APIRouter(tags=["results"])


@router.get("/results/summary", response_model=ResultsSummaryPage)
def results_summary(
    course_id: int | None = None,
    standard_id: int | None = None,
    family_key: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResultsSummaryPage:
    """Questions appearing in at least one visible, non-deleted administration. Aggregate figures only."""
    stmt = (
        select(
            AdministrationItem.question_id.label("question_id"),
            func.count(func.distinct(Administration.id)).label("times_used"),
            func.max(Administration.administered_on).label("last_used"),
            func.coalesce(func.sum(ItemResult.correct), 0).label("correct"),
            func.coalesce(func.sum(ItemResult.attempted), 0).label("attempted"),
        )
        .select_from(AdministrationItem)
        .join(Administration, Administration.id == AdministrationItem.administration_id)
        .join(Question, Question.id == AdministrationItem.question_id)
        .join(Standard, Standard.id == Question.standard_id)
        .outerjoin(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
        .where(*visible_clauses(user))
        .group_by(AdministrationItem.question_id)
    )
    if standard_id is not None:
        stmt = stmt.where(Question.standard_id == standard_id)
    if course_id is not None:
        stmt = stmt.where(Standard.course_id == course_id)
    if family_key is not None:
        stmt = stmt.where(Question.family_key == family_key)
    grouped = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(grouped)) or 0
    ratio = cast(grouped.c.correct, Numeric) / func.nullif(grouped.c.attempted, 0)
    ordered = (
        select(grouped)
        .order_by(case((grouped.c.attempted == 0, 1), else_=0), ratio, grouped.c.question_id)
        .limit(limit)
        .offset(offset)
    )
    page = db.execute(ordered).all()
    questions = {
        q.id: q
        for q in db.scalars(
            select(Question)
            .where(Question.id.in_([r.question_id for r in page]))
            .options(selectinload(Question.versions), selectinload(Question.standard).selectinload(Standard.course))
        )
    }
    items = []
    for r in page:
        q = questions[r.question_id]
        v = q.current_version
        items.append(
            SummaryRow(
                question_id=q.id,
                standard_id=q.standard_id,
                standard_code=q.standard.code,
                course_name=q.standard.course.name,
                family_key=q.family_key,
                template_key=q.template_key,
                stem=v.stem,
                dok=v.dok,
                question_type=v.question_type,
                times_used=r.times_used,
                last_used=r.last_used,
                correct=r.correct,
                attempted=r.attempted,
                accuracy=accuracy(r.correct, r.attempted),
                limited_responses=limited_responses(r.attempted),
            )
        )
    return ResultsSummaryPage(items=items, total=total, limit=limit, offset=offset)


def _ref(q: Question) -> QuestionRef:
    return QuestionRef(id=q.id, status=q.status, standard_code=q.standard.code)


@router.get("/questions/{question_id}/usage", response_model=UsagePage)
def question_usage(
    question_id: int,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UsagePage:
    """Every visible, non-deleted administration a question appeared in, with the pinned version used."""
    question = db.scalar(select(Question).options(selectinload(Question.standard)).where(Question.id == question_id))
    if question is None:
        raise not_found("Question")
    stmt = (
        select(
            Administration.id.label("administration_id"),
            Administration.label.label("label"),
            Administration.administered_on.label("administered_on"),
            Assessment.id.label("assessment_id"),
            Assessment.title.label("assessment_title"),
            QuestionVersion.version_no.label("version_no"),
            func.coalesce(func.sum(ItemResult.correct), 0).label("correct"),
            func.coalesce(func.sum(ItemResult.attempted), 0).label("attempted"),
        )
        .select_from(AdministrationItem)
        .join(Administration, Administration.id == AdministrationItem.administration_id)
        .join(Assessment, Assessment.id == Administration.assessment_id)
        .join(QuestionVersion, QuestionVersion.id == AdministrationItem.question_version_id)
        .outerjoin(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
        .where(AdministrationItem.question_id == question_id, *visible_clauses(user))
        .group_by(Administration.id, Assessment.id, QuestionVersion.id, AdministrationItem.id)
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Administration.administered_on.desc(), Administration.id.desc()).limit(limit).offset(offset)
    ).all()
    parent = None
    if question.variant_of_id is not None:
        parent_row = db.scalar(
            select(Question).options(selectinload(Question.standard)).where(Question.id == question.variant_of_id)
        )
        parent = _ref(parent_row) if parent_row else None
    variants = db.scalars(
        select(Question)
        .options(selectinload(Question.standard))
        .where(Question.variant_of_id == question_id)
        .order_by(Question.id)
    ).all()
    return UsagePage(
        items=[
            UsageEntry(
                administration_id=r.administration_id,
                label=r.label,
                administered_on=r.administered_on,
                assessment_id=r.assessment_id,
                assessment_title=r.assessment_title,
                pinned_version_no=r.version_no,
                is_current_version=r.version_no == question.current_version_no,
                correct=r.correct,
                attempted=r.attempted,
                accuracy=accuracy(r.correct, r.attempted),
                limited_responses=limited_responses(r.attempted),
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
        parent=parent,
        variants=[_ref(v) for v in variants],
    )
