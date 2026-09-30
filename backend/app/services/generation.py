"""Shared server-side generation for one standard, used by the generate and variant routes."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Standard
from app.schemas import GenerateRequest
from app.services.bank import get_standard, observable_text, resolve_family
from app.services.engine.core import GenerationError
from app.services.engine.family import generate_set


def eocep_blocked_templates(std: Standard, family) -> set[str]:
    """Templates that may never appear in EOCEP practice: constructed-response items (the EOCEP is
    entirely selected-response) plus any standard-specific exclusions from the imported constraints
    (e.g. a future template that constructs a pedigree or dihybrid cross)."""
    declared = set((std.eocep_constraints or {}).get("excluded_templates", {}).get(family.key, []))
    constructed_response = {t.key for t in family.templates if t.question_type == "constructed_response"}
    return declared | constructed_response


def generate_for_request(db: Session, req: GenerateRequest, seed: str):
    std = get_standard(db, req.standard_id)
    eocep = req.generation_mode == "eocep"
    if eocep and (std.course.slug != "biology-1" or not std.eocep_constraints):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "EOCEP mode is available only for Biology 1 standards with imported EOCEP constraints",
        )
    family = resolve_family(std, req.family_key)
    unknown = set(req.template_keys) - {t.key for t in family.templates}
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown templates: {', '.join(sorted(unknown))}")

    template_keys = list(req.template_keys)
    question_types = list(req.question_types)
    if eocep:
        if "constructed_response" in question_types:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "EOCEP practice mode is selected-response only; it does not include constructed-response items",
            )
        blocked = eocep_blocked_templates(std, family)
        if template_keys:
            disallowed = sorted(set(template_keys) & blocked)
            if disallowed:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Not permitted in EOCEP practice mode for this standard: {', '.join(disallowed)}",
                )
        else:
            template_keys = [t.key for t in family.templates if t.key not in blocked]
            if not template_keys:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "No templates in this family are permitted in EOCEP practice mode for this standard",
                )

    try:
        out = generate_set(
            family,
            seed,
            req.quantity,
            doks=req.doks or None,
            question_types=question_types or None,
            template_keys=template_keys or None,
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
