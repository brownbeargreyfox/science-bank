"""Linked variants of a question: preview persists nothing; save accepts signed tokens only."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import Actor, get_actor
from app.schemas import VariantPreviewOut, VariantPreviewRequest, VariantSaveOut, VariantSaveRequest
from app.services.variant_generation import preview_variants, save_variants
from app.services.variants import MAX_BATCH

router = APIRouter(prefix="/questions/variants", tags=["variants"])


@router.post("/preview", response_model=VariantPreviewOut)
def preview(
    body: VariantPreviewRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> VariantPreviewOut:
    ids = list(dict.fromkeys(body.question_ids))
    if len(ids) > MAX_BATCH:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Choose at most {MAX_BATCH} questions at a time")
    return VariantPreviewOut(records=preview_variants(db, actor, ids))


@router.post("/save", response_model=VariantSaveOut, status_code=status.HTTP_201_CREATED)
def save(body: VariantSaveRequest, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)) -> VariantSaveOut:
    if len(body.tokens) > MAX_BATCH:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Save at most {MAX_BATCH} variants at a time")
    created, parents = save_variants(db, actor, body.tokens)
    return VariantSaveOut(question_ids=created, parent_ids=parents)
