"""Coverage grid: per standard in a course, bank readiness and what the viewer has assessed, grouped by bundle."""

from typing import get_args

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Administration,
    AdministrationItem,
    Bundle,
    Course,
    ItemResult,
    Question,
    Standard,
    User,
)
from app.schemas import (
    CoverageCourse,
    CoverageGroup,
    CoveragePage,
    CoverageScope,
    CoverageStandard,
    CoverageSummary,
    QuestionCounts,
    QuestionStatus,
)
from app.services.administrations import visible_clauses
from app.services.bank import not_found
from app.services.coverage import SCHOOL_YEAR_START_MONTH, resolve_scope, today
from app.services.families.registry import families_for_standard
from app.services.results import accuracy, limited_responses

router = APIRouter(tags=["coverage"])

STATUSES = get_args(QuestionStatus)
OTHER_STANDARDS = "Other standards"


@router.get("/coverage", response_model=CoveragePage)
def coverage(
    course_id: int,
    year: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoveragePage:
    """What the viewer has assessed in a school year (or all time), by standard and bundle. Not what was taught."""
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("Course")
    try:
        scope = resolve_scope(year, today())
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    standards = db.scalars(
        select(Standard)
        .options(selectinload(Standard.course))
        .where(Standard.course_id == course_id)
        .order_by(Standard.sort_order, Standard.id)
    ).all()
    by_id = {s.id: s for s in standards}
    ids = list(by_id)

    counts = {sid: dict.fromkeys(STATUSES, 0) for sid in ids}
    for standard_id, q_status, n in db.execute(
        select(Question.standard_id, Question.status, func.count())
        .where(Question.standard_id.in_(ids))
        .group_by(Question.standard_id, Question.status)
    ):
        counts[standard_id][q_status] = n

    used = (
        select(
            Question.standard_id.label("standard_id"),
            func.count(func.distinct(Administration.id)).label("times"),
            func.max(Administration.administered_on).label("last"),
            func.coalesce(func.sum(ItemResult.correct), 0).label("correct"),
            func.coalesce(func.sum(ItemResult.attempted), 0).label("attempted"),
        )
        .select_from(AdministrationItem)
        .join(Administration, Administration.id == AdministrationItem.administration_id)
        .join(Question, Question.id == AdministrationItem.question_id)
        .outerjoin(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
        .where(Question.standard_id.in_(ids), *visible_clauses(user))
        .group_by(Question.standard_id)
    )
    if scope.start is not None and scope.end is not None:
        used = used.where(Administration.administered_on >= scope.start, Administration.administered_on <= scope.end)
    activity = {r.standard_id: r for r in db.execute(used)}

    def build(s: Standard, partial: bool, also_in: list[str]) -> CoverageStandard:
        a = activity.get(s.id)
        correct, attempted = (a.correct, a.attempted) if a else (0, 0)
        return CoverageStandard(
            standard_id=s.id,
            code=s.code,
            expectation=s.performance_expectation,
            domain_code=s.domain_code,
            partial=partial,
            also_in=also_in,
            families=[f.key for f in families_for_standard(s)],
            questions=QuestionCounts(**counts[s.id]),
            times_assessed=a.times if a else 0,
            last_assessed=a.last if a else None,
            correct=correct,
            attempted=attempted,
            accuracy=accuracy(correct, attempted),
            limited_responses=limited_responses(attempted),
        )

    bundles = db.scalars(
        select(Bundle)
        .options(selectinload(Bundle.aligned))
        .where(Bundle.course_id == course_id)
        .order_by(Bundle.sort_order, Bundle.id)
    ).all()
    membership: dict[int, list[str]] = {}
    for b in bundles:
        for link in b.aligned:
            if link.standard_id in by_id:
                membership.setdefault(link.standard_id, []).append(b.name)

    def group(bundle_id: int | None, name: str, rows: list[CoverageStandard]) -> CoverageGroup:
        return CoverageGroup(
            bundle_id=bundle_id,
            name=name,
            assessed=sum(1 for r in rows if r.times_assessed > 0),
            total=len(rows),
            standards=rows,
        )

    groups = []
    for b in bundles:
        rows = [
            build(by_id[link.standard_id], link.partial, [n for n in membership[link.standard_id] if n != b.name])
            for link in b.aligned
            if link.standard_id in by_id
        ]
        if rows:
            groups.append(group(b.id, b.name, rows))
    unbundled = [build(s, False, []) for s in standards if s.id not in membership]
    if unbundled:
        groups.append(group(None, OTHER_STANDARDS, unbundled))

    on = Administration.administered_on
    start_year = func.extract("year", on) - case((func.extract("month", on) < SCHOOL_YEAR_START_MONTH, 1), else_=0)
    years = {int(y) for y in db.scalars(select(start_year).where(*visible_clauses(user)).distinct())}
    if scope.year is not None:
        years.add(scope.year)

    return CoveragePage(
        scope=CoverageScope(kind=scope.kind, year=scope.year, label=scope.label, start=scope.start, end=scope.end),
        available_years=sorted(years, reverse=True),
        course=CoverageCourse(id=course.id, name=course.name),
        groups=groups,
        summary=CoverageSummary(
            standards_total=len(standards), standards_assessed=sum(1 for s in standards if s.id in activity)
        ),
    )
