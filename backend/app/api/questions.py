from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Text, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.models import AssessmentItem, Course, Question, QuestionVersion, Standard, Stimulus
from app.schemas import (
    BulkStatusChange,
    BulkStatusOut,
    QuestionDetail,
    QuestionEdit,
    QuestionPage,
    QuestionStatus,
    QuestionSummary,
    QuestionType,
    QuestionVersionOut,
    StatusChange,
    StatusEventOut,
    StimulusOut,
)
from app.services.bank import TRANSITIONS, add_version, change_status, get_standard, not_found, standard_summary

router = APIRouter(prefix="/questions", tags=["questions"])


def _load(db: Session, question_id: int) -> Question:
    q = db.scalar(
        select(Question)
        .options(
            selectinload(Question.versions),
            selectinload(Question.status_events),
            selectinload(Question.stimulus),
        )
        .where(Question.id == question_id)
    )
    if q is None:
        raise not_found("Question")
    return q


def _detail(db: Session, q: Question) -> QuestionDetail:
    std = get_standard(db, q.standard_id)
    assessment_ids = db.scalars(
        select(AssessmentItem.assessment_id).where(AssessmentItem.question_id == q.id).distinct()
    ).all()
    return QuestionDetail(
        id=q.id,
        status=q.status,
        allowed_transitions=list(TRANSITIONS[q.status]),
        standard=standard_summary(std),
        family_key=q.family_key,
        template_key=q.template_key,
        provenance=q.provenance,
        stimulus=StimulusOut.model_validate(q.stimulus) if q.stimulus else None,
        current=QuestionVersionOut.model_validate(q.current_version),
        versions=[QuestionVersionOut.model_validate(v) for v in reversed(q.versions)],
        status_events=[StatusEventOut.model_validate(e) for e in reversed(q.status_events)],
        assessment_ids=list(assessment_ids),
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


@router.get("", response_model=QuestionPage)
def list_questions(
    status_filter: list[QuestionStatus] = Query(default=[], alias="status"),
    course_id: int | None = None,
    standard_id: int | None = None,
    family_key: str | None = None,
    dok: list[int] = Query(default=[]),
    question_type: QuestionType | None = None,
    stimulus_id: int | None = None,
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> QuestionPage:
    base = (
        select(Question, QuestionVersion, Standard, Course, Stimulus)
        .join(
            QuestionVersion,
            (QuestionVersion.question_id == Question.id) & (QuestionVersion.version_no == Question.current_version_no),
        )
        .join(Standard, Standard.id == Question.standard_id)
        .join(Course, Course.id == Standard.course_id)
        .outerjoin(Stimulus, Stimulus.id == Question.stimulus_id)
    )
    filters = []
    if course_id is not None:
        filters.append(Standard.course_id == course_id)
    if standard_id is not None:
        filters.append(Question.standard_id == standard_id)
    if family_key:
        filters.append(Question.family_key == family_key)
    if dok:
        filters.append(QuestionVersion.dok.in_(dok))
    if question_type:
        filters.append(QuestionVersion.question_type == question_type)
    if stimulus_id is not None:
        filters.append(Question.stimulus_id == stimulus_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                QuestionVersion.stem.ilike(like),
                QuestionVersion.choices.cast(Text).ilike(like),
                Standard.code.ilike(like),
                Stimulus.title.ilike(like),
            )
        )
    status_counts = _status_counts(db, base, filters)
    if status_filter:
        filters.append(Question.status.in_(status_filter))
    stmt = base.where(*filters)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Question.updated_at.desc(), Question.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [
        QuestionSummary(
            id=question.id,
            status=question.status,
            standard_id=std.id,
            standard_code=std.code,
            course_name=course.name,
            use_year=course.use_year,
            family_key=question.family_key,
            template_key=question.template_key,
            stimulus_id=question.stimulus_id,
            stimulus_title=stim.title if stim else None,
            current_version_no=question.current_version_no,
            origin=version.origin,
            question_type=version.question_type,
            dok=version.dok,
            stem=version.stem,
            updated_at=question.updated_at,
        )
        for question, version, std, course, stim in rows
    ]
    return QuestionPage(items=items, total=total, page=page, page_size=page_size, status_counts=status_counts)


def _status_counts(db: Session, base, filters) -> dict[str, int]:
    sub = base.where(*filters).with_only_columns(Question.status).subquery()
    return dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())


@router.get("/{question_id}", response_model=QuestionDetail)
def get_question(question_id: int, db: Session = Depends(get_db)) -> QuestionDetail:
    return _detail(db, _load(db, question_id))


@router.post("/{question_id}/versions", response_model=QuestionDetail, status_code=status.HTTP_201_CREATED)
def edit_question(question_id: int, edit: QuestionEdit, db: Session = Depends(get_db)) -> QuestionDetail:
    q = _load(db, question_id)
    add_version(q, edit)
    db.commit()
    return _detail(db, _load(db, question_id))


@router.post("/{question_id}/restore/{version_no}", response_model=QuestionDetail, status_code=status.HTTP_201_CREATED)
def restore_version(question_id: int, version_no: int, db: Session = Depends(get_db)) -> QuestionDetail:
    """Make an older version current again by copying it forward as a new version."""
    q = _load(db, question_id)
    old = next((v for v in q.versions if v.version_no == version_no), None)
    if old is None:
        raise not_found("Version")
    if old.version_no == q.current_version_no:
        raise HTTPException(status.HTTP_409_CONFLICT, "That version is already current")
    new = QuestionVersion(
        version_no=max(v.version_no for v in q.versions) + 1,
        origin=old.origin,
        question_type=old.question_type,
        dok=old.dok,
        stem=old.stem,
        choices=old.choices,
        answer=old.answer,
        explanation=old.explanation,
        change_note=f"Restored version {old.version_no}",
    )
    q.versions.append(new)
    q.current_version_no = new.version_no
    db.commit()
    return _detail(db, _load(db, question_id))


@router.post("/{question_id}/status", response_model=QuestionDetail)
def set_status(question_id: int, change: StatusChange, db: Session = Depends(get_db)) -> QuestionDetail:
    q = _load(db, question_id)
    change_status(q, change.to_status, change.note)
    db.commit()
    return _detail(db, _load(db, question_id))


@router.post("/bulk-status", response_model=BulkStatusOut)
def bulk_status(change: BulkStatusChange, db: Session = Depends(get_db)) -> BulkStatusOut:
    updated, skipped = [], {}
    questions = db.scalars(
        select(Question).options(selectinload(Question.status_events)).where(Question.id.in_(change.question_ids))
    ).all()
    found = {q.id: q for q in questions}
    for qid in change.question_ids:
        q = found.get(qid)
        if q is None:
            skipped[qid] = "not found"
            continue
        try:
            change_status(q, change.to_status, change.note)
            updated.append(qid)
        except HTTPException as exc:
            skipped[qid] = exc.detail
    db.commit()
    return BulkStatusOut(updated=updated, skipped=skipped)
