"""Administrations: recording that an assessment was given, and per-section results."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import Actor, get_actor, get_current_user
from app.models import (
    Administration,
    AdministrationItem,
    AdministrationSection,
    Assessment,
    AssessmentItem,
    ItemResult,
    Question,
    Standard,
    User,
)
from app.schemas import (
    AccuracyOut,
    AdministrationCreate,
    AdministrationDetail,
    AdministrationItemOut,
    AdministrationSummary,
    AdministrationUpdate,
    OwnerOut,
    ResultOut,
    ResultsBatch,
    SectionName,
    SectionOut,
)
from app.services.administrations import MAX_SECTIONS, get_administration, visible_clauses
from app.services.audit import record_audit
from app.services.bank import not_found
from app.services.results import ResultRow, ResultsError, accuracy, limited_responses, plan_result_changes

router = APIRouter(tags=["administrations"])


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message)


def _accuracy_out(correct: int, attempted: int) -> AccuracyOut:
    return AccuracyOut(
        correct=correct,
        attempted=attempted,
        accuracy=accuracy(correct, attempted),
        limited_responses=limited_responses(attempted),
    )


def _summaries(db: Session, admins: list[Administration]) -> list[AdministrationSummary]:
    ids = [a.id for a in admins]
    if not ids:
        return []
    sections = dict(
        db.execute(
            select(AdministrationSection.administration_id, func.count())
            .where(AdministrationSection.administration_id.in_(ids))
            .group_by(AdministrationSection.administration_id)
        ).all()
    )
    items = dict(
        db.execute(
            select(AdministrationItem.administration_id, func.count())
            .where(AdministrationItem.administration_id.in_(ids))
            .group_by(AdministrationItem.administration_id)
        ).all()
    )
    with_data = dict(
        db.execute(
            select(AdministrationItem.administration_id, func.count(func.distinct(ItemResult.administration_item_id)))
            .join(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
            .where(AdministrationItem.administration_id.in_(ids))
            .group_by(AdministrationItem.administration_id)
        ).all()
    )
    return [
        AdministrationSummary(
            id=a.id,
            assessment_id=a.assessment_id,
            assessment_title=a.assessment.title,
            label=a.label,
            administered_on=a.administered_on,
            owner=OwnerOut.model_validate(a.owner),
            section_count=sections.get(a.id, 0),
            item_count=items.get(a.id, 0),
            items_with_data=with_data.get(a.id, 0),
            created_at=a.created_at,
            deleted_at=a.deleted_at,
        )
        for a in admins
    ]


def _detail(db: Session, admin: Administration) -> AdministrationDetail:
    db.refresh(admin)
    sections = db.scalars(
        select(AdministrationSection)
        .where(AdministrationSection.administration_id == admin.id)
        .order_by(AdministrationSection.id)
    ).all()
    items = db.scalars(
        select(AdministrationItem)
        .where(AdministrationItem.administration_id == admin.id)
        .order_by(AdministrationItem.position)
        .options(
            selectinload(AdministrationItem.question_version),
            selectinload(AdministrationItem.question).options(
                selectinload(Question.standard).selectinload(Standard.course),
                selectinload(Question.stimulus),
            ),
        )
    ).all()
    results = (
        db.scalars(select(ItemResult).where(ItemResult.administration_item_id.in_([i.id for i in items]))).all()
        if items
        else []
    )
    totals: dict[int, list[int]] = {}
    for r in results:
        t = totals.setdefault(r.administration_item_id, [0, 0])
        t[0] += r.correct
        t[1] += r.attempted
    summary = _summaries(db, [admin])[0]
    return AdministrationDetail(
        **summary.model_dump(),
        sections=[SectionOut(id=s.id, name=s.name) for s in sections],
        items=[
            AdministrationItemOut(
                id=i.id,
                position=i.position,
                question_id=i.question_id,
                question_version_id=i.question_version_id,
                pinned_version_no=i.question_version.version_no,
                standard_code=i.question.standard.code,
                course_name=i.question.standard.course.name,
                dok=i.question_version.dok,
                question_type=i.question_version.question_type,
                stem=i.question_version.stem,
                stimulus_title=i.question.stimulus.title if i.question.stimulus else None,
                totals=_accuracy_out(*totals.get(i.id, [0, 0])),
            )
            for i in items
        ],
        results=[
            ResultOut(
                section_id=r.section_id, item_id=r.administration_item_id, correct=r.correct, attempted=r.attempted
            )
            for r in sorted(results, key=lambda r: (r.administration_item_id, r.section_id))
        ],
    )


@router.post(
    "/assessments/{assessment_id}/administrations",
    response_model=AdministrationDetail,
    status_code=status.HTTP_201_CREATED,
)
def record_use(
    assessment_id: int, body: AdministrationCreate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    """Freeze the assessment's current items and record that it was given. Owned by the caller."""
    assessment = db.scalar(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.deleted_at.is_(None)).with_for_update()
    )
    if assessment is None:
        raise not_found("Assessment")
    # One statement, taken after the row lock: the snapshot is a single coherent assessment state.
    items = db.scalars(
        select(AssessmentItem).where(AssessmentItem.assessment_id == assessment_id).order_by(AssessmentItem.position)
    ).all()
    if not items:
        raise _unprocessable("Add at least one question to the assessment before recording a use")
    admin = Administration(
        assessment_id=assessment.id, label=body.label, administered_on=body.administered_on, owner_id=actor.user.id
    )
    admin.sections = [AdministrationSection(name=name) for name in body.sections]
    admin.items = [
        AdministrationItem(
            source_assessment_item_id=it.id,
            question_id=it.question_id,
            question_version_id=it.question_version_id,
            position=it.position,
        )
        for it in items
    ]
    db.add(admin)
    db.flush()
    record_audit(
        db,
        actor,
        "administration.create",
        target_type="administration",
        target_id=admin.id,
        detail={"assessment_id": assessment.id, "sections": len(body.sections), "items": len(items)},
    )
    db.commit()
    return _detail(db, admin)


@router.get("/assessments/{assessment_id}/administrations", response_model=list[AdministrationSummary])
def list_administrations(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AdministrationSummary]:
    if db.scalar(select(Assessment.id).where(Assessment.id == assessment_id, Assessment.deleted_at.is_(None))) is None:
        raise not_found("Assessment")
    admins = db.scalars(
        select(Administration)
        .where(Administration.assessment_id == assessment_id, *visible_clauses(user))
        .options(selectinload(Administration.assessment), selectinload(Administration.owner))
        .order_by(Administration.administered_on.desc(), Administration.id.desc())
    ).all()
    return _summaries(db, list(admins))


@router.get("/administrations/{administration_id}", response_model=AdministrationDetail)
def get_detail(
    administration_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AdministrationDetail:
    return _detail(db, get_administration(db, user, administration_id))


@router.patch("/administrations/{administration_id}", response_model=AdministrationDetail)
def update_administration(
    administration_id: int,
    body: AdministrationUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    fields = body.model_fields_set
    if "label" in fields and body.label is not None:
        admin.label = body.label
    if "administered_on" in fields and body.administered_on is not None:
        admin.administered_on = body.administered_on
    record_audit(
        db,
        actor,
        "administration.update",
        target_type="administration",
        target_id=admin.id,
        detail={"fields": sorted(fields)},
    )
    db.commit()
    return _detail(db, admin)


@router.delete("/administrations/{administration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_administration(
    administration_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> Response:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    admin.deleted_at = datetime.now(UTC)
    record_audit(db, actor, "administration.delete", target_type="administration", target_id=admin.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/administrations/{administration_id}/restore", response_model=AdministrationDetail)
def restore_administration(
    administration_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True, include_deleted=True)
    admin.deleted_at = None
    record_audit(db, actor, "administration.restore", target_type="administration", target_id=admin.id)
    db.commit()
    return _detail(db, admin)


def _section(admin: Administration, section_id: int) -> AdministrationSection:
    section = next((s for s in admin.sections if s.id == section_id), None)
    if section is None:
        raise not_found("Section")
    return section


@router.post(
    "/administrations/{administration_id}/sections",
    response_model=AdministrationDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_section(
    administration_id: int, body: SectionName, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    if len(admin.sections) >= MAX_SECTIONS:
        raise _unprocessable(f"An administration can have at most {MAX_SECTIONS} sections")
    if body.name.lower() in {s.name.lower() for s in admin.sections}:
        raise _unprocessable("There is already a section with that name")
    admin.sections.append(AdministrationSection(name=body.name))
    record_audit(
        db, actor, "administration.sections", target_type="administration", target_id=admin.id, detail={"op": "add"}
    )
    db.commit()
    return _detail(db, admin)


@router.patch("/administrations/{administration_id}/sections/{section_id}", response_model=AdministrationDetail)
def rename_section(
    administration_id: int,
    section_id: int,
    body: SectionName,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    section = _section(admin, section_id)
    if body.name.lower() in {s.name.lower() for s in admin.sections if s.id != section.id}:
        raise _unprocessable("There is already a section with that name")
    section.name = body.name
    record_audit(
        db, actor, "administration.sections", target_type="administration", target_id=admin.id, detail={"op": "rename"}
    )
    db.commit()
    return _detail(db, admin)


@router.delete("/administrations/{administration_id}/sections/{section_id}", response_model=AdministrationDetail)
def delete_section(
    administration_id: int, section_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    section = _section(admin, section_id)
    if len(admin.sections) <= 1:
        raise _unprocessable("An administration needs at least one section")
    db.delete(section)  # its results go with it (ON DELETE CASCADE)
    record_audit(
        db, actor, "administration.sections", target_type="administration", target_id=admin.id, detail={"op": "remove"}
    )
    db.commit()
    return _detail(db, admin)


@router.put("/administrations/{administration_id}/results", response_model=AdministrationDetail)
def save_results(
    administration_id: int, body: ResultsBatch, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    """Atomic batch: every row is validated before anything is written. A null pair clears a cell."""
    admin = get_administration(db, actor.user, administration_id, lock=True)
    section_ids = {s.id for s in admin.sections}
    item_ids = {i.id for i in admin.items}
    try:
        upserts, clears = plan_result_changes(
            [ResultRow(r.section_id, r.item_id, r.correct, r.attempted) for r in body.rows], section_ids, item_ids
        )
    except ResultsError as exc:
        raise _unprocessable(str(exc)) from exc
    existing = {
        (r.section_id, r.administration_item_id): r
        for r in db.scalars(select(ItemResult).where(ItemResult.section_id.in_(section_ids)))
    }
    for key in clears:
        if key in existing:
            db.delete(existing[key])
    for section_id, item_id, correct, attempted in upserts:
        row = existing.get((section_id, item_id))
        if row is None:
            db.add(
                ItemResult(section_id=section_id, administration_item_id=item_id, correct=correct, attempted=attempted)
            )
        else:
            row.correct, row.attempted = correct, attempted
    record_audit(
        db,
        actor,
        "administration.results",
        target_type="administration",
        target_id=admin.id,
        detail={"rows": len(upserts), "cleared": len(clears)},
    )
    db.commit()
    return _detail(db, admin)
