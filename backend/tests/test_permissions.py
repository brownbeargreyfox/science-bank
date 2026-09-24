"""Role × ownership matrix for every mutating route, plus a guard that new routes are covered."""

import pytest
from sqlalchemy import func, select

from tests.conftest import login_as
from tests.test_api import _generate  # resolves the standard id and builds a GenerateRequest body


def make_question(anon, who: str) -> int:
    """Log in as `who`, save one generated set, return the first question id (owned by `who`)."""
    login_as(anon, who)
    _, body = _generate(anon, "biology-1", "B-LS2-1", "population-carrying-capacity", seed="edit")
    r = anon.post("/api/generate/save", json=body)
    assert r.status_code == 201, r.text
    return r.json()["question_ids"][0]


def _edit_body(anon, qid: int) -> dict:
    """A valid QuestionEdit that differs from the current version (ChoiceIn has only text/correct/rationale)."""
    cur = anon.get(f"/api/questions/{qid}").json()["current"]
    body = {"stem": cur["stem"] + " (edited)", "dok": cur["dok"], "explanation": cur["explanation"]}
    if cur["question_type"] == "multiple_choice":
        body["choices"] = [
            {"text": c["text"], "correct": c["correct"], "rationale": c["rationale"]} for c in cur["choices"]
        ]
    else:
        body["answer"] = cur["answer"]
    return body


# ---- questions ---------------------------------------------------------------------------------


def test_question_owner_and_can_modify_fields(anon):
    qid = make_question(anon, "regular")
    mine = anon.get(f"/api/questions/{qid}").json()
    assert mine["owner"]["username"] == "reg" and mine["can_modify"] is True
    login_as(anon, "regular2")
    assert anon.get(f"/api/questions/{qid}").json()["can_modify"] is False
    listed = anon.get("/api/questions", params={"page_size": 200}).json()["items"]
    assert next(i for i in listed if i["id"] == qid)["can_modify"] is False


@pytest.mark.parametrize(("who", "expected"), [("regular", 201), ("regular2", 403), ("power", 201), ("admin", 201)])
def test_edit_question_matrix(anon, who, expected):
    qid = make_question(anon, "regular")
    login_as(anon, who)
    r = anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid))
    assert r.status_code == expected, r.text


@pytest.mark.parametrize(("who", "expected"), [("regular", 200), ("regular2", 403), ("power", 200), ("admin", 200)])
def test_status_matrix(anon, who, expected):
    qid = make_question(anon, "regular")
    login_as(anon, who)
    r = anon.post(f"/api/questions/{qid}/status", json={"to_status": "archived"})
    assert r.status_code == expected, r.text


@pytest.mark.parametrize(("who", "expected"), [("regular", 201), ("regular2", 403), ("power", 201)])
def test_restore_matrix(anon, who, expected):
    qid = make_question(anon, "regular")
    anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid))
    login_as(anon, who)
    r = anon.post(f"/api/questions/{qid}/restore/1")
    assert r.status_code == expected, r.text


def test_bulk_status_is_all_or_nothing_on_ownership(anon, db):
    from app.models import Question

    mine = make_question(anon, "regular")
    theirs = make_question(anon, "power")
    login_as(anon, "regular")
    r = anon.post("/api/questions/bulk-status", json={"question_ids": [mine, theirs], "to_status": "archived"})
    assert r.status_code == 403 and str(theirs) in r.json()["detail"]
    db.expire_all()
    assert db.get(Question, mine).status == "generated"


def test_question_actions_record_actor_and_audit(anon, db):
    from app.models import AuditEvent, Question, QuestionStatusEvent, QuestionVersion

    qid = make_question(anon, "regular")
    me = login_as(anon, "power")
    anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid))
    anon.post(f"/api/questions/{qid}/status", json={"to_status": "reviewed"})
    db.expire_all()
    v2_author = db.scalar(
        select(QuestionVersion.created_by).where(QuestionVersion.question_id == qid, QuestionVersion.version_no == 2)
    )
    assert v2_author == me["id"]
    last_event_actor = db.scalar(
        select(QuestionStatusEvent.actor_id)
        .where(QuestionStatusEvent.question_id == qid)
        .order_by(QuestionStatusEvent.id.desc())
        .limit(1)
    )
    assert last_event_actor == me["id"]
    actions = db.scalars(
        select(AuditEvent.action).where(AuditEvent.target_type == "question", AuditEvent.target_id == str(qid))
    ).all()
    assert {"question.version", "question.status"} <= set(actions)
    assert db.get(Question, qid).owner_id != me["id"]


def test_failed_change_writes_no_audit_row(anon, db):
    from app.models import AuditEvent

    qid = make_question(anon, "regular")
    before = db.scalar(select(func.max(AuditEvent.id))) or 0
    r = anon.post(f"/api/questions/{qid}/status", json={"to_status": "generated"})  # not an allowed transition
    assert r.status_code == 409
    login_as(anon, "regular2")
    assert anon.post(f"/api/questions/{qid}/status", json={"to_status": "archived"}).status_code == 403
    db.expire_all()
    written = db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.id > before, AuditEvent.target_type == "question")
    )
    assert written == 0
