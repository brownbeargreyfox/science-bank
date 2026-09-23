from fastapi import APIRouter, Depends, Query
from sqlalchemy import Text, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.models import Bundle, BundleStandard, Course, Question, SourceDocument, Standard, StandardTopic, Topic
from app.schemas import (
    BundleOut,
    BundleRef,
    BundleStandardOut,
    CourseOut,
    FamilyBindingOut,
    FamilyOut,
    SourceDocumentOut,
    StandardDetail,
    StandardSummary,
    TemplateOut,
)
from app.services.bank import get_standard, observable_text, standard_summary
from app.services.families.registry import FAMILIES

router = APIRouter(tags=["standards"])


@router.get("/courses", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)) -> list[CourseOut]:
    courses = db.scalars(
        select(Course).options(selectinload(Course.source_document)).order_by(Course.use_year.desc(), Course.name)
    ).all()
    std_counts = dict(db.execute(select(Standard.course_id, func.count()).group_by(Standard.course_id)).all())
    bundle_counts = dict(db.execute(select(Bundle.course_id, func.count()).group_by(Bundle.course_id)).all())
    return [
        CourseOut(
            id=c.id,
            state=c.state,
            use_year=c.use_year,
            slug=c.slug,
            name=c.name,
            standards_base=c.standards_base,
            notes=c.notes,
            active=c.active,
            standards_count=std_counts.get(c.id, 0),
            bundles_count=bundle_counts.get(c.id, 0),
            source_document=SourceDocumentOut.model_validate(c.source_document),
        )
        for c in courses
    ]


@router.get("/standards", response_model=list[StandardSummary])
def list_standards(
    course_id: int | None = None,
    q: str | None = Query(default=None, max_length=200),
    domain: str | None = None,
    topic: str | None = None,
    candidate_only: bool = False,
    with_family_only: bool = False,
    db: Session = Depends(get_db),
) -> list[StandardSummary]:
    stmt = (
        select(Standard)
        .join(Course)
        .options(selectinload(Standard.course), selectinload(Standard.topics))
        .order_by(Course.name, Standard.sort_order)
    )
    if course_id is not None:
        stmt = stmt.where(Standard.course_id == course_id)
    if domain:
        stmt = stmt.where(Standard.domain_code == domain)
    if candidate_only:
        stmt = stmt.where(Standard.question_family_candidate.is_(True))
    if topic:
        stmt = stmt.where(Standard.topics.any(Topic.name == topic))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Standard.code.ilike(like),
                Standard.performance_expectation.ilike(like),
                Standard.clarification_statement.ilike(like),
                Standard.domain_name.ilike(like),
                Standard.topics.any(Topic.name.ilike(like)),
                Standard.terminology.cast(Text).ilike(like),
            )
        )
    summaries = [standard_summary(s) for s in db.scalars(stmt).all()]
    if with_family_only:
        summaries = [s for s in summaries if s.families]
    return summaries


@router.get("/standards/{standard_id}", response_model=StandardDetail)
def get_standard_detail(standard_id: int, db: Session = Depends(get_db)) -> StandardDetail:
    std = get_standard(db, standard_id)
    bundles = db.execute(
        select(Bundle.id, Bundle.name, BundleStandard.partial)
        .join(BundleStandard, BundleStandard.bundle_id == Bundle.id)
        .where(BundleStandard.standard_id == std.id)
        .order_by(Bundle.sort_order)
    ).all()
    counts = dict(
        db.execute(
            select(Question.status, func.count()).where(Question.standard_id == std.id).group_by(Question.status)
        ).all()
    )
    return StandardDetail(
        **standard_summary(std).model_dump(),
        clarification_statement=std.clarification_statement,
        state_assessment_boundary=std.state_assessment_boundary,
        sep=std.sep,
        dci=std.dci,
        ccc=std.ccc,
        observable_performances=std.observable_performances,
        terminology=std.terminology,
        question_sentence_stems=std.question_sentence_stems,
        content_sha256=std.content_sha256,
        source_document=SourceDocumentOut.model_validate(std.course.source_document),
        bundles=[BundleRef(id=b.id, name=b.name, partial=b.partial) for b in bundles],
        question_counts=counts,
    )


@router.get("/topics", response_model=list[str])
def list_topics(course_id: int | None = None, db: Session = Depends(get_db)) -> list[str]:
    stmt = select(Topic.name).distinct().order_by(Topic.name)
    if course_id is not None:
        stmt = (
            stmt.join(StandardTopic, StandardTopic.topic_id == Topic.id)
            .join(Standard, Standard.id == StandardTopic.standard_id)
            .where(Standard.course_id == course_id)
        )
    return list(db.scalars(stmt).all())


@router.get("/bundles", response_model=list[BundleOut])
def list_bundles(course_id: int | None = None, db: Session = Depends(get_db)) -> list[BundleOut]:
    stmt = (
        select(Bundle)
        .join(Course)
        .options(
            selectinload(Bundle.course),
            selectinload(Bundle.source_document),
            selectinload(Bundle.aligned).selectinload(BundleStandard.standard),
        )
        .order_by(Course.name, Bundle.sort_order)
    )
    if course_id is not None:
        stmt = stmt.where(Bundle.course_id == course_id)
    return [
        BundleOut(
            id=b.id,
            course_id=b.course_id,
            course_name=b.course.name,
            name=b.name,
            narrative=b.narrative,
            aligned=[
                BundleStandardOut(
                    standard_id=a.standard_id,
                    code=a.standard.code,
                    partial=a.partial,
                    performance_expectation=a.standard.performance_expectation,
                )
                for a in b.aligned
            ],
            connected_pes=b.connected_pes,
            example_anchoring_phenomena=b.example_anchoring_phenomena,
            source_document_title=b.source_document.title,
        )
        for b in db.scalars(stmt).all()
    ]


@router.get("/sources", response_model=list[SourceDocumentOut])
def list_sources(db: Session = Depends(get_db)) -> list[SourceDocumentOut]:
    docs = db.scalars(select(SourceDocument).order_by(SourceDocument.document_key)).all()
    return [SourceDocumentOut.model_validate(d) for d in docs]


@router.get("/families", response_model=list[FamilyOut])
def list_families(db: Session = Depends(get_db)) -> list[FamilyOut]:
    out = []
    for family in FAMILIES.values():
        bindings, first_std = [], None
        for b in family.bindings:
            stds = db.scalars(
                select(Standard)
                .join(Course)
                .where(Course.state == b.state, Course.slug == b.course_slug, Standard.code == b.code)
                .order_by(Course.use_year.desc())
            ).all()
            first_std = first_std or (stds[0] if stds else None)
            bindings.append(
                FamilyBindingOut(
                    state=b.state, course_slug=b.course_slug, code=b.code, standard_ids=[s.id for s in stds]
                )
            )
        out.append(
            FamilyOut(
                key=family.key,
                version=family.version,
                title=family.title,
                description=family.description,
                stimulus_kind=family.stimulus_kind,
                bindings=bindings,
                templates=[
                    TemplateOut(
                        **t.__dict__,
                        observable_text=observable_text(first_std, t.observable_category, t.observable_index)
                        if first_std
                        else None,
                    )
                    for t in family.templates
                ],
            )
        )
    return out
