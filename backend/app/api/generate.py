import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import Actor, get_actor
from app.models import Bundle, BundleStandard, Standard
from app.schemas import (
    BundleGeneratePreviewOut,
    BundleGenerateRequest,
    BundleOut,
    BundleStandardOut,
    GeneratePreviewOut,
    GenerateRequest,
    GenerateSaveOut,
)
from app.services.audit import record_audit
from app.services.bank import observable_text, save_generated, standard_summary
from app.services.engine.core import GenerationError
from app.services.engine.family import generate_set
from app.services.families.registry import FAMILIES
from app.services.generation import generate_for_request as _generate

router = APIRouter(prefix="/generate", tags=["generate"])


def _get_bundle(db: Session, bundle_id: int) -> Bundle:
    bundle = db.scalar(
        select(Bundle)
        .options(
            selectinload(Bundle.course),
            selectinload(Bundle.source_document),
            selectinload(Bundle.aligned).selectinload(BundleStandard.standard).selectinload(Standard.course),
            selectinload(Bundle.aligned).selectinload(BundleStandard.standard).selectinload(Standard.topics),
        )
        .where(Bundle.id == bundle_id)
    )
    if bundle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bundle not found")
    return bundle


def _bundle_out(bundle: Bundle) -> BundleOut:
    return BundleOut(
        id=bundle.id,
        course_id=bundle.course_id,
        course_name=bundle.course.name,
        name=bundle.name,
        narrative=bundle.narrative,
        aligned=[
            BundleStandardOut(
                standard_id=aligned.standard_id,
                code=aligned.standard.code,
                partial=aligned.partial,
                performance_expectation=aligned.standard.performance_expectation,
            )
            for aligned in bundle.aligned
        ],
        connected_pes=bundle.connected_pes,
        example_anchoring_phenomena=bundle.example_anchoring_phenomena,
        source_document_title=bundle.source_document.title,
    )


def _generate_bundle(db: Session, req: BundleGenerateRequest, seed: str):
    bundle = _get_bundle(db, req.bundle_id)
    family = FAMILIES.get(req.family_key)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question family not found")
    standards_by_code = {aligned.standard.code: aligned.standard for aligned in bundle.aligned if not aligned.partial}
    required = {binding.code for binding in family.bindings}
    if bundle.course.slug != family.bindings[0].course_slug or not required <= set(standards_by_code):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{family.title} is not supported by the {bundle.name} bundle",
        )
    unknown = set(req.template_keys) - {template.key for template in family.templates}
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown templates: {', '.join(sorted(unknown))}")
    try:
        out = generate_set(
            family,
            seed,
            req.quantity,
            doks=req.doks or None,
            question_types=list(req.question_types) or None,
            template_keys=req.template_keys or None,
        )
    except GenerationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    for group in out["groups"]:
        for question in group["questions"]:
            question_standard = standards_by_code[question["standard_code"]]
            question["observable"]["text"] = observable_text(
                question_standard, question["observable"]["category"], question["observable"]["index"]
            )
    out["options"]["bundle_id"] = bundle.id
    out["options"]["generation_mode"] = "classroom"
    anchor_standard = standards_by_code[family.bindings[0].code]
    return bundle, anchor_standard, standards_by_code, family, out


@router.post("/preview", response_model=GeneratePreviewOut)
def preview(req: GenerateRequest, db: Session = Depends(get_db)) -> GeneratePreviewOut:
    """Generate without saving. Omit `seed` for a fresh one; the returned seed reproduces this exact set."""
    seed = req.seed or secrets.token_hex(4)
    std, _, out = _generate(db, req, seed)
    return GeneratePreviewOut(**out, standard=standard_summary(std))


@router.post("/save", response_model=GenerateSaveOut, status_code=status.HTTP_201_CREATED)
def save(req: GenerateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> GenerateSaveOut:
    """Regenerate server-side from the seed (never trusting client-edited content) and store in the bank."""
    if not req.seed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A seed is required to save; preview first")
    std, family, out = _generate(db, req, req.seed)
    run, ids = save_generated(db, std, family, out, owner_id=actor.user.id)
    record_audit(
        db,
        actor,
        "question.generate",
        target_type="generation_run",
        target_id=run.id,
        detail={"question_ids": ids, "family": family.key, "seed": req.seed},
    )
    db.commit()
    return GenerateSaveOut(run_id=run.id, seed=req.seed, question_ids=ids)


@router.post("/bundle/preview", response_model=BundleGeneratePreviewOut)
def preview_bundle(req: BundleGenerateRequest, db: Session = Depends(get_db)) -> BundleGeneratePreviewOut:
    """Preview one shared, classroom-only stimulus aligned to a complete imported SCDE bundle."""
    seed = req.seed or secrets.token_hex(4)
    bundle, _, standards_by_code, family, out = _generate_bundle(db, req, seed)
    return BundleGeneratePreviewOut(
        **out,
        bundle=_bundle_out(bundle),
        standards=[standard_summary(standards_by_code[binding.code]) for binding in family.bindings],
    )


@router.post("/bundle/save", response_model=GenerateSaveOut, status_code=status.HTTP_201_CREATED)
def save_bundle(
    req: BundleGenerateRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> GenerateSaveOut:
    """Regenerate and persist one shared bundle stimulus, never trusting preview payload content."""
    if not req.seed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A seed is required to save; preview first")
    bundle, anchor_standard, standards_by_code, family, out = _generate_bundle(db, req, req.seed)
    run, ids = save_generated(
        db,
        anchor_standard,
        family,
        out,
        owner_id=actor.user.id,
        bundle=bundle,
        standards_by_code=standards_by_code,
    )
    record_audit(
        db,
        actor,
        "question.generate",
        target_type="generation_run",
        target_id=run.id,
        detail={"question_ids": ids, "family": family.key, "bundle_id": bundle.id, "seed": req.seed},
    )
    db.commit()
    return GenerateSaveOut(run_id=run.id, seed=req.seed, question_ids=ids)
