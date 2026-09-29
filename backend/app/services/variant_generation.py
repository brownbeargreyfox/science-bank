"""Database-backed variant preview and save. The pure rules live in app.services.variants."""

import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import Actor
from app.models import Question, QuestionVersion, Standard, Stimulus
from app.schemas import GenerateRequest
from app.services.audit import record_audit
from app.services.bank import not_found, save_generated
from app.services.engine.family import QuestionFamily
from app.services.families.registry import FAMILIES, families_for_standard
from app.services.generation import generate_for_request
from app.services.variants import (
    LINEAGE_CEILING,
    MAX_ATTEMPTS,
    TokenError,
    candidate_seed,
    fingerprint,
    issue_token,
    verify_token,
)


def unavailable_reason(parent: Question) -> str | None:
    """Why a parent cannot have a variant in v1, or None when it can."""
    if parent.family_key is None or parent.template_key is None:
        return "This question was not generated from a question family, so a new item cannot be generated."
    family = FAMILIES.get(parent.family_key)
    if family is None:
        return "The question family that generated this item is no longer available."
    if len(family.bindings) != 1:
        return "Questions from multi-standard bundle families cannot have variants yet."
    if parent.template_key not in {t.key for t in family.templates}:
        return "The template that generated this item no longer exists."
    if family not in families_for_standard(parent.standard):
        return "This family is no longer aligned to the question's standard."
    return None


def lineage_root(db: Session, question: Question) -> Question:
    steps = 0
    while question.variant_of_id is not None and steps < 100:
        question = db.get(Question, question.variant_of_id)
        steps += 1
    return question


def lineage_ids(db: Session, root_id: int) -> list[int]:
    """The root question and every descendant variant."""
    lineage = select(Question.id).where(Question.id == root_id).cte("lineage", recursive=True)
    lineage = lineage.union_all(select(Question.id).join(lineage, Question.variant_of_id == lineage.c.id))
    return list(db.scalars(select(lineage.c.id)))


def lineage_fingerprints(db: Session, ids: list[int]) -> set[str]:
    """Fingerprints of every version of every question in the lineage."""
    rows = db.execute(
        select(
            QuestionVersion.question_type,
            QuestionVersion.stem,
            QuestionVersion.choices,
            QuestionVersion.answer,
            Stimulus.body,
        )
        .join(Question, Question.id == QuestionVersion.question_id)
        .outerjoin(Stimulus, Stimulus.id == Question.stimulus_id)
        .where(QuestionVersion.question_id.in_(ids))
    ).all()
    return {fingerprint(r.question_type, r.stem, r.choices, r.answer, r.body) for r in rows}


@dataclass
class Derived:
    std: Standard
    family: QuestionFamily
    out: dict[str, Any]
    group: dict[str, Any]
    question: dict[str, Any]
    fingerprint: str


def derive(db: Session, parent: Question, seed: str) -> Derived:
    """Generate one question from the parent's family and template with the given seed.

    Uses the current family code and the parent's saved generation mode; never the browser's input.
    """
    options = parent.provenance.get("options") or {}
    req = GenerateRequest(
        standard_id=parent.standard_id,
        family_key=parent.family_key,
        quantity=1,
        template_keys=[parent.template_key],
        generation_mode=options.get("generation_mode", "classroom"),
    )
    std, family, out = generate_for_request(db, req, seed)
    group = out["groups"][0]
    question = group["questions"][0]
    fp = fingerprint(
        question["question_type"], question["stem"], question["choices"], question["answer"], group["stimulus"]
    )
    return Derived(std, family, out, group, question, fp)


def _load_parents(db: Session, ids: list[int]) -> dict[int, Question]:
    found = {
        q.id: q
        for q in db.scalars(
            select(Question)
            .where(Question.id.in_(ids))
            .options(selectinload(Question.versions), selectinload(Question.standard).selectinload(Standard.course))
        )
    }
    for qid in ids:
        if qid not in found:
            raise not_found("Question")
    return found


def _unavailable(parent_id: int, reason: str) -> dict[str, Any]:
    return {
        "parent_id": parent_id,
        "status": "unavailable",
        "reason": reason,
        "candidate": None,
        "candidate_token": None,
    }


def _candidate(derived: Derived) -> dict[str, Any]:
    q = derived.question
    return {
        "question_type": q["question_type"],
        "dok": q["dok"],
        "stem": q["stem"],
        "choices": q["choices"],
        "answer": q["answer"],
        "explanation": q["explanation"],
        "stimulus": derived.group["stimulus"],
    }


def preview_variants(db: Session, actor: Actor, ids: list[int]) -> list[dict[str, Any]]:
    """One record per parent, in order. Persists nothing."""
    parents = _load_parents(db, ids)
    nonce = secrets.token_hex(8)
    accepted: set[str] = set()
    records: list[dict[str, Any]] = []
    for pid in ids:
        parent = parents[pid]
        reason = unavailable_reason(parent)
        lineage: list[int] = []
        if reason is None:
            lineage = lineage_ids(db, lineage_root(db, parent).id)
            if len(lineage) - 1 >= LINEAGE_CEILING:
                reason = "This question already has the maximum number of variants."
        if reason is not None:
            records.append(_unavailable(pid, reason))
            continue
        known = lineage_fingerprints(db, lineage)
        record = None
        for attempt in range(MAX_ATTEMPTS):
            seed = candidate_seed(nonce, pid, attempt)
            try:
                derived = derive(db, parent, seed)
            except HTTPException as exc:
                record = _unavailable(pid, str(exc.detail))
                break
            if derived.fingerprint in known or derived.fingerprint in accepted:
                continue
            accepted.add(derived.fingerprint)
            record = {
                "parent_id": pid,
                "status": "candidate",
                "reason": None,
                "candidate": _candidate(derived),
                "candidate_token": issue_token(
                    user_id=actor.user.id,
                    parent_id=pid,
                    parent_version_id=parent.current_version.id,
                    seed=seed,
                    family_key=derived.family.key,
                    family_version=derived.family.version,
                ),
            }
            break
        records.append(record or _unavailable(pid, "No distinct variant is available for this question."))
    return records


def save_variants(db: Session, actor: Actor, tokens: list[str]) -> tuple[list[int], list[int]]:
    """Verify, re-derive, and persist the selected candidates in one transaction. Nothing is trusted from the client."""
    parsed = []
    for token in tokens:
        try:
            parsed.append(verify_token(token, user_id=actor.user.id))
        except TokenError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    parents = _load_parents(db, list(dict.fromkeys(t.parent_id for t in parsed)))
    roots = {pid: lineage_root(db, parent).id for pid, parent in parents.items()}
    created: list[int] = []
    created_parents: list[int] = []
    batch: set[str] = set()
    for tok in sorted(parsed, key=lambda t: (roots[t.parent_id], t.parent_id)):  # stable lock order
        parent = parents[tok.parent_id]
        reason = unavailable_reason(parent)
        if reason is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Question {parent.id}: {reason}")
        # Serialise sibling saves: lock the lineage root before reading the lineage.
        db.execute(select(Question.id).where(Question.id == roots[parent.id]).with_for_update())
        lineage = lineage_ids(db, roots[parent.id])
        if len(lineage) - 1 >= LINEAGE_CEILING:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Question {parent.id} already has the maximum number of variants",
            )
        family = FAMILIES[parent.family_key]
        if family.key != tok.family_key or family.version != tok.family_version:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"The question family changed since this preview; regenerate the candidate for question {parent.id}",
            )
        derived = derive(db, parent, tok.seed)
        if derived.fingerprint in lineage_fingerprints(db, lineage) or derived.fingerprint in batch:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"A matching variant of question {parent.id} already exists; regenerate this candidate",
            )
        batch.add(derived.fingerprint)
        _run, question_ids = save_generated(db, derived.std, derived.family, derived.out, owner_id=actor.user.id)
        variant = db.get(Question, question_ids[0])
        variant.variant_of_id = parent.id
        variant.provenance = {
            **variant.provenance,
            "variant": {
                "of": parent.id,
                "parent_version_id": tok.parent_version_id,
                "seed": tok.seed,
                "family_version": family.version,
            },
        }
        created.append(variant.id)
        created_parents.append(parent.id)
    record_audit(
        db,
        actor,
        "question.variants",
        target_type="question",
        target_id=created[0] if created else None,
        detail={"parents": created_parents, "created": created, "count": len(created)},
    )
    db.commit()
    return created, created_parents
