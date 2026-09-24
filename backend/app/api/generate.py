import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import Actor, get_actor
from app.schemas import GeneratePreviewOut, GenerateRequest, GenerateSaveOut
from app.services.audit import record_audit
from app.services.bank import get_standard, observable_text, resolve_family, save_generated, standard_summary
from app.services.engine.core import GenerationError
from app.services.engine.family import generate_set

router = APIRouter(prefix="/generate", tags=["generate"])


def _generate(db: Session, req: GenerateRequest, seed: str):
    std = get_standard(db, req.standard_id)
    if req.generation_mode == "eocep" and (std.course.slug != "biology-1" or not std.eocep_constraints):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "EOCEP mode is available only for Biology 1 standards with imported EOCEP constraints",
        )
    family = resolve_family(std, req.family_key)
    unknown = set(req.template_keys) - {t.key for t in family.templates}
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
        for q in group["questions"]:
            q["observable"]["text"] = observable_text(std, q["observable"]["category"], q["observable"]["index"])
    out["options"]["generation_mode"] = req.generation_mode
    if req.generation_mode == "eocep":
        out["eocep_constraints"] = std.eocep_constraints
    return std, family, out


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
