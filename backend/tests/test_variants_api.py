"""Linked variants: preview persists nothing, save re-derives from signed tokens, distinctness and locking."""

import json
import time
from types import SimpleNamespace

from sqlalchemy import func, select, update

from app.models import AuditEvent, GenerationRun, Question, Stimulus
from tests.conftest import login_as
from tests.test_api import _generate
from tests.test_permissions import _edit_body, make_question

FAMILY = "population-carrying-capacity"


def preview(anon, ids):
    return anon.post("/api/questions/variants/preview", json={"question_ids": ids})


def candidates(anon, ids):
    r = preview(anon, ids)
    assert r.status_code == 200, r.text
    return r.json()["records"]


def save(anon, tokens):
    return anon.post("/api/questions/variants/save", json={"tokens": tokens})


def counts(db):
    db.expire_all()
    return (
        db.scalar(select(func.count()).select_from(Question)),
        db.scalar(select(func.count()).select_from(GenerationRun)),
    )


def make_variant(anon, parent_id):
    rec = candidates(anon, [parent_id])[0]
    r = save(anon, [rec["candidate_token"]])
    assert r.status_code == 201, r.text
    return r.json()["question_ids"][0], rec


def crafted_token(anon, parent_id, seed, *, family_version=None):
    from app.services.families.registry import FAMILIES
    from app.services.variants import issue_token

    me = anon.get("/api/auth/me").json()
    return issue_token(
        user_id=me["id"],
        parent_id=parent_id,
        parent_version_id=1,
        seed=seed,
        family_key=FAMILY,
        family_version=family_version or FAMILIES[FAMILY].version,
    )


# ---- preview -----------------------------------------------------------------------------------


def test_preview_persists_nothing_and_returns_candidates_with_tokens(anon, db):
    qid = make_question(anon, "regular")
    before = counts(db)
    rec = candidates(anon, [qid])[0]
    assert rec["status"] == "candidate" and rec["candidate_token"] and rec["reason"] is None
    cand = rec["candidate"]
    assert cand["stem"] and cand["question_type"] and cand["answer"] and cand["explanation"] is not None
    assert counts(db) == before


def test_preview_batch_rules(anon):
    qid = make_question(anon, "regular")
    assert len(candidates(anon, [qid, qid])) == 1  # duplicates collapse
    assert preview(anon, list(range(1, 22))).status_code == 422  # more than 20 distinct ids
    assert preview(anon, []).status_code == 422
    assert preview(anon, [qid, 999999]).status_code == 404  # a missing id fails the whole request


def test_mixed_selection_returns_candidates_plus_inline_reasons(anon, db):
    bad, good = make_question(anon, "regular"), make_question(anon, "regular")
    db.execute(update(Question).where(Question.id == bad).values(family_key="retired-family"))
    db.commit()
    recs = candidates(anon, [bad, good])
    assert [r["status"] for r in recs] == ["unavailable", "candidate"]
    assert "no longer available" in recs[0]["reason"] and recs[0]["candidate_token"] is None
    single = preview(anon, [bad])
    assert (
        single.status_code == 200 and single.json()["records"][0]["status"] == "unavailable"
    )  # never 422 by batch size


def test_unavailable_reasons_for_bundle_family_and_family_less_parents():
    from app.services.families.registry import FAMILIES
    from app.services.variant_generation import unavailable_reason

    bundle = FAMILIES["chemical-system-stability"]
    parent = SimpleNamespace(family_key=bundle.key, template_key=bundle.templates[0].key, standard=None)
    assert "bundle" in unavailable_reason(parent)
    assert unavailable_reason(SimpleNamespace(family_key=None, template_key=None, standard=None))
    gone = SimpleNamespace(family_key="trait-probability", template_key="no-such-template", standard=None)
    assert "template" in unavailable_reason(gone).lower()


def test_teacher_edited_parent_still_gets_a_candidate_from_the_family_template(anon):
    qid = make_question(anon, "regular")
    assert anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid)).status_code == 201
    assert candidates(anon, [qid])[0]["status"] == "candidate"


# ---- save --------------------------------------------------------------------------------------


def test_only_selected_candidates_are_saved_and_linked(anon, db):
    q1, q2 = make_question(anon, "regular"), make_question(anon, "regular")
    recs = candidates(anon, [q1, q2])
    parent_stem = anon.get(f"/api/questions/{q1}").json()["current"]["stem"]
    before = counts(db)
    r = save(anon, [recs[0]["candidate_token"]])  # q2's candidate is not selected
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["parent_ids"] == [q1] and len(body["question_ids"]) == 1
    after = counts(db)
    assert after[0] == before[0] + 1
    vid = body["question_ids"][0]
    detail = anon.get(f"/api/questions/{vid}").json()
    parent = anon.get(f"/api/questions/{q1}").json()
    assert detail["status"] == "generated" and detail["family_key"] == parent["family_key"]
    assert detail["template_key"] == parent["template_key"] and detail["standard"]["id"] == parent["standard"]["id"]
    assert detail["provenance"]["variant"]["of"] == q1
    assert parent["current"]["stem"] == parent_stem  # the parent is untouched
    usage = anon.get(f"/api/questions/{q1}/usage").json()
    assert [v["id"] for v in usage["variants"]] == [vid]
    assert anon.get(f"/api/questions/{vid}/usage").json()["parent"]["id"] == q1


def test_saved_content_matches_the_preview_and_fingerprints_survive_jsonb(anon, db):
    from app.services.variants import fingerprint

    qid = make_question(anon, "regular")
    vid, rec = make_variant(anon, qid)
    cand = rec["candidate"]
    db.expire_all()
    variant = db.get(Question, vid)
    v = variant.current_version
    assert v.stem == cand["stem"] and v.answer == cand["answer"]
    stored = fingerprint(v.question_type, v.stem, v.choices, v.answer, variant.stimulus.body)
    previewed = fingerprint(cand["question_type"], cand["stem"], cand["choices"], cand["answer"], cand["stimulus"])
    assert stored == previewed


def test_variant_is_owned_by_the_person_saving_it(anon):
    qid = make_question(anon, "regular")
    login_as(anon, "regular2")
    vid, _ = make_variant(anon, qid)
    assert anon.get(f"/api/questions/{vid}").json()["owner"]["username"] == "reg2"
    assert anon.get(f"/api/questions/{qid}").json()["owner"]["username"] == "reg"


def test_replayed_token_is_a_conflict_and_creates_nothing(anon, db):
    qid = make_question(anon, "regular")
    rec = candidates(anon, [qid])[0]
    assert save(anon, [rec["candidate_token"]]).status_code == 201
    before = counts(db)
    again = save(anon, [rec["candidate_token"]])
    assert again.status_code == 409 and str(qid) in again.json()["detail"]
    assert counts(db) == before


def test_tampered_other_user_and_expired_tokens_are_rejected(anon, db, monkeypatch):
    qid = make_question(anon, "regular")
    rec = candidates(anon, [qid])[0]
    token = rec["candidate_token"]
    raw, sig = token.split(".")
    flipped = raw[:-1] + ("A" if raw[-1] != "A" else "B")
    before = counts(db)
    assert save(anon, [f"{flipped}.{sig}"]).status_code == 422
    assert save(anon, ["not-a-token"]).status_code == 422
    with monkeypatch.context() as m:
        real = time.time
        m.setattr(time, "time", lambda: real() + 3600)
        expired = save(anon, [token])
    assert expired.status_code == 422 and "expired" in expired.json()["detail"]
    login_as(anon, "regular2")
    other = save(anon, [token])
    assert other.status_code == 422 and "different user" in other.json()["detail"]
    assert counts(db) == before


def test_family_version_change_between_preview_and_save_is_a_conflict(anon):
    qid = make_question(anon, "regular")
    token = crafted_token(anon, qid, "v-stale-1-0", family_version="0.0.0")
    r = save(anon, [token])
    assert r.status_code == 409 and "regenerate" in r.json()["detail"]


def test_sibling_saved_first_is_a_conflict_naming_the_parent(anon, db):
    qid = make_question(anon, "regular")
    vid, _ = make_variant(anon, qid)
    db.expire_all()
    seed = db.get(Question, vid).provenance["variant"]["seed"]
    r = save(anon, [crafted_token(anon, qid, seed)])
    assert r.status_code == 409 and str(qid) in r.json()["detail"]


def test_a_failing_token_rolls_back_the_whole_batch(anon, db):
    q1, q2 = make_question(anon, "regular"), make_question(anon, "regular")
    vid2, _ = make_variant(anon, q2)
    db.expire_all()
    seed2 = db.get(Question, vid2).provenance["variant"]["seed"]
    good = candidates(anon, [q1])[0]["candidate_token"]
    before = counts(db)
    r = save(anon, [good, crafted_token(anon, q2, seed2)])
    assert r.status_code == 409
    assert counts(db) == before  # the good candidate was not saved either


def test_lineage_ceiling(anon, monkeypatch):
    monkeypatch.setattr("app.services.variant_generation.LINEAGE_CEILING", 1)
    qid = make_question(anon, "regular")
    make_variant(anon, qid)
    rec = candidates(anon, [qid])[0]
    assert rec["status"] == "unavailable" and "maximum" in rec["reason"]
    assert save(anon, [crafted_token(anon, qid, "v-cap-1-0")]).status_code == 422


def test_saved_variant_stays_valid_after_the_parent_changes(anon):
    qid = make_question(anon, "regular")
    vid, _ = make_variant(anon, qid)
    assert anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid)).status_code == 201
    assert anon.post(f"/api/questions/{qid}/status", json={"to_status": "archived"}).status_code == 200
    assert anon.post(f"/api/questions/{qid}/status", json={"to_status": "reviewed"}).status_code == 200
    assert anon.get(f"/api/questions/{vid}").status_code == 200
    assert anon.get(f"/api/questions/{vid}/usage").json()["parent"]["id"] == qid


def test_eocep_parent_produces_an_eocep_variant(anon, db):
    login_as(anon, "regular")
    _, body = _generate(anon, "biology-1", "B-LS2-1", FAMILY, seed="eocep-parent", generation_mode="eocep", quantity=1)
    parent_id = anon.post("/api/generate/save", json=body).json()["question_ids"][0]
    vid, _ = make_variant(anon, parent_id)
    db.expire_all()
    variant = db.get(Question, vid)
    assert variant.provenance["options"]["generation_mode"] == "eocep"
    assert variant.current_version.question_type == "multiple_choice"


def test_eocep_dna_parent_produces_a_variant_without_strand_ends(anon, db):
    login_as(anon, "regular")
    _, body = _generate(
        anon,
        "biology-1",
        "B-LS1-1",
        "dna-protein-synthesis",
        seed="eocep-dna",
        generation_mode="eocep",
        quantity=1,
        template_keys=["translate_mrna"],
    )
    parent_id = anon.post("/api/generate/save", json=body).json()["question_ids"][0]
    candidate = candidates(anon, [parent_id])[0]["candidate"]
    assert "left to right" in candidate["stem"] and "′" not in candidate["stem"]
    vid, _ = make_variant(anon, parent_id)
    db.expire_all()
    variant = db.get(Question, vid)
    assert variant.provenance["options"]["generation_mode"] == "eocep"
    version = variant.current_version
    stimulus = db.get(Stimulus, variant.stimulus_id)
    everything = json.dumps(
        [version.stem, version.choices, version.answer, version.explanation, stimulus.body], ensure_ascii=False
    )
    assert "′" not in everything and "Codon table (mRNA codons)" in everything


def test_eocep_mutation_parent_produces_a_variant_that_keeps_the_scope_note(anon, db):
    login_as(anon, "regular")
    _, body = _generate(
        anon,
        "biology-1",
        "B-LS3-2",
        "mutation-effects",
        seed="eocep-mutation",
        generation_mode="eocep",
        quantity=1,
        template_keys=["identify_mutation_type"],
    )
    parent_id = anon.post("/api/generate/save", json=body).json()["question_ids"][0]
    vid, _ = make_variant(anon, parent_id)
    db.expire_all()
    options = db.get(Question, vid).provenance["options"]
    assert options["generation_mode"] == "eocep"
    assert (
        options["eocep_scope_note"]
        == "Covers the mutation part of this standard only; meiosis items are not yet available."
    )


def test_audit_event_names_ids_and_counts_but_no_content(anon, db):
    qid = make_question(anon, "regular")
    vid, rec = make_variant(anon, qid)
    db.expire_all()
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.action == "question.variants").order_by(AuditEvent.id.desc())
    ).first()
    assert event.detail == {"parents": [qid], "created": [vid], "count": 1}
    assert rec["candidate"]["stem"] not in str(event.detail)


def test_save_batch_is_capped(anon):
    login_as(anon, "regular")
    assert save(anon, ["x"] * 21).status_code == 422
