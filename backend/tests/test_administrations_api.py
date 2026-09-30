"""Recording that an assessment was given, per-section results, access rules, and locking."""

import threading
import time

import pytest
from sqlalchemy import select

from tests.conftest import login_as
from tests.test_permissions import make_assessment, make_question


def build_assessment(anon, who="regular", n=2, title="Unit quiz"):
    """An assessment with n questions, owned by `who` (questions come from a power user)."""
    qids = [make_question(anon, "power") for _ in range(n)]
    aid = make_assessment(anon, who, title)
    assert anon.post(f"/api/assessments/{aid}/items", json={"question_ids": qids}).status_code == 200
    return aid, qids


def record(anon, aid, sections=("Period 2",), label="Quiz 1", on="2026-09-29"):
    r = anon.post(
        f"/api/assessments/{aid}/administrations",
        json={"label": label, "administered_on": on, "sections": list(sections)},
    )
    assert r.status_code == 201, r.text
    return r.json()


def rows(detail, *cells):
    """cells: (section_index, item_index, correct, attempted) -> PUT body rows."""
    return [
        {
            "section_id": detail["sections"][s]["id"],
            "item_id": detail["items"][i]["id"],
            "correct": c,
            "attempted": a,
        }
        for s, i, c, a in cells
    ]


def put(anon, detail, *cells):
    return anon.put(f"/api/administrations/{detail['id']}/results", json={"rows": rows(detail, *cells)})


# ---- recording and the snapshot ------------------------------------------------------------------


def test_record_use_snapshots_exact_items_in_order(anon):
    aid, qids = build_assessment(anon)
    before = anon.get(f"/api/assessments/{aid}").json()["items"]
    d = record(anon, aid, ["Period 2", "Period 4"])
    assert d["label"] == "Quiz 1" and d["owner"]["username"] == "reg"
    assert [s["name"] for s in d["sections"]] == ["Period 2", "Period 4"]
    assert [i["question_id"] for i in d["items"]] == [i["question_id"] for i in before]
    assert [i["position"] for i in d["items"]] == [1, 2]
    assert all(i["pinned_version_no"] == 1 for i in d["items"])
    assert d["items_with_data"] == 0 and d["item_count"] == 2


def test_snapshot_survives_later_assessment_changes(anon):
    aid, qids = build_assessment(anon)
    d = record(anon, aid)
    items = anon.get(f"/api/assessments/{aid}").json()["items"]
    anon.put(f"/api/assessments/{aid}/items/order", json={"item_ids": [items[1]["id"], items[0]["id"]]})
    anon.delete(f"/api/assessments/{aid}/items/{items[0]['id']}")
    again = anon.get(f"/api/administrations/{d['id']}").json()
    assert [i["id"] for i in again["items"]] == [i["id"] for i in d["items"]]
    assert [i["question_id"] for i in again["items"]] == [i["question_id"] for i in d["items"]]


def test_empty_assessment_cannot_be_recorded(anon):
    aid = make_assessment(anon, "regular")
    r = anon.post(
        f"/api/assessments/{aid}/administrations",
        json={"label": "x", "administered_on": "2026-09-29", "sections": ["A"]},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"label": "x", "administered_on": "2026-09-29", "sections": []},
        {"label": "x", "administered_on": "2026-09-29", "sections": ["A", "a"]},
        {"label": "x", "administered_on": "2026-09-29", "sections": ["  "]},
        {"label": " ", "administered_on": "2026-09-29", "sections": ["A"]},
        {"label": "x", "administered_on": "not-a-date", "sections": ["A"]},
    ],
)
def test_invalid_record_use_bodies_are_rejected(anon, body):
    aid, _ = build_assessment(anon)
    assert anon.post(f"/api/assessments/{aid}/administrations", json=body).status_code == 422


def test_another_teacher_can_record_use_of_a_colleagues_assessment(anon):
    aid, _ = build_assessment(anon, who="regular")
    login_as(anon, "regular2")
    d = record(anon, aid)
    assert d["owner"]["username"] == "reg2"


def test_missing_or_deleted_assessment_is_404(anon):
    aid, _ = build_assessment(anon)
    anon.delete(f"/api/assessments/{aid}")
    body = {"label": "x", "administered_on": "2026-09-29", "sections": ["A"]}
    assert anon.post(f"/api/assessments/{aid}/administrations", json=body).status_code == 404
    assert anon.post("/api/assessments/999999/administrations", json=body).status_code == 404


# ---- results -----------------------------------------------------------------------------------


def test_results_save_and_compute_accuracy_across_sections(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid, ["Period 2", "Period 4"])
    r = put(anon, d, (0, 0, 5, 10), (1, 0, 7, 20), (0, 1, 0, 30))
    assert r.status_code == 200, r.text
    out = r.json()
    first, second = out["items"]
    assert first["totals"] == {"correct": 12, "attempted": 30, "accuracy": 0.4, "limited_responses": False}
    assert second["totals"]["accuracy"] == 0.0 and second["totals"]["attempted"] == 30  # 0 of 30 is 0%, not no data
    assert out["items_with_data"] == 2


def test_no_data_is_null_accuracy_never_zero(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    put(anon, d, (0, 0, 3, 9))
    out = anon.get(f"/api/administrations/{d['id']}").json()
    assert out["items"][0]["totals"]["limited_responses"] is True
    assert out["items"][1]["totals"] == {"correct": 0, "attempted": 0, "accuracy": None, "limited_responses": False}


@pytest.mark.parametrize(
    "cells",
    [
        [(0, 0, 1, 0)],
        [(0, 0, 3, 2)],
        [(0, 0, -1, 2)],
        [(0, 0, None, 5)],
        [(0, 0, 5, None)],
        [(0, 0, 1, 2), (0, 0, 2, 3)],
    ],
)
def test_invalid_batches_are_rejected_and_save_nothing(anon, cells):
    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    good = (0, 1, 4, 8)
    assert put(anon, d, good, *cells).status_code == 422
    assert anon.get(f"/api/administrations/{d['id']}").json()["items_with_data"] == 0


def test_boolean_and_float_counts_are_rejected(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    base = rows(d, (0, 0, 1, 2))[0]
    for bad in ({"correct": True}, {"attempted": 2.5}, {"correct": "3"}):
        r = anon.put(f"/api/administrations/{d['id']}/results", json={"rows": [{**base, **bad}]})
        assert r.status_code == 422, bad


def test_rows_must_belong_to_this_administration(anon):
    aid, _ = build_assessment(anon)
    d1, d2 = record(anon, aid), record(anon, aid, label="Quiz 2")
    foreign_section = {**rows(d1, (0, 0, 1, 2))[0], "section_id": d2["sections"][0]["id"]}
    foreign_item = {**rows(d1, (0, 0, 1, 2))[0], "item_id": d2["items"][0]["id"]}
    for row in (foreign_section, foreign_item):
        assert anon.put(f"/api/administrations/{d1['id']}/results", json={"rows": [row]}).status_code == 422


def test_null_pair_clears_a_cell(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    put(anon, d, (0, 0, 5, 10))
    r = put(anon, d, (0, 0, None, None))
    assert r.status_code == 200 and r.json()["items_with_data"] == 0 and r.json()["results"] == []


def test_upsert_replaces_an_existing_value(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    put(anon, d, (0, 0, 5, 10))
    out = put(anon, d, (0, 0, 8, 10)).json()
    assert out["results"] == [
        {"section_id": d["sections"][0]["id"], "item_id": d["items"][0]["id"], "correct": 8, "attempted": 10}
    ]


# ---- sections ----------------------------------------------------------------------------------


def test_sections_can_be_added_renamed_and_removed_with_their_results(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid, ["Period 2", "Period 4"])
    put(anon, d, (0, 0, 5, 10), (1, 0, 6, 10))
    base = f"/api/administrations/{d['id']}/sections"
    added = anon.post(base, json={"name": "Period 6"})
    assert added.status_code == 201 and len(added.json()["sections"]) == 3
    assert anon.post(base, json={"name": "period 6"}).status_code == 422  # duplicate ignoring case
    sid = d["sections"][1]["id"]
    assert anon.patch(f"{base}/{sid}", json={"name": "Period 5"}).json()["sections"][1]["name"] == "Period 5"
    assert anon.patch(f"{base}/{sid}", json={"name": "PERIOD 2"}).status_code == 422
    left = anon.delete(f"{base}/{sid}").json()
    assert [r["correct"] for r in left["results"]] == [5]  # only the removed section's results are gone
    only = left["sections"]
    assert len(only) == 2
    for s in only[:-1]:
        anon.delete(f"{base}/{s['id']}")
    assert anon.delete(f"{base}/{only[-1]['id']}").status_code == 422  # the last section cannot be removed


def test_section_limit(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid, [f"S{i}" for i in range(12)])
    assert anon.post(f"/api/administrations/{d['id']}/sections", json={"name": "S12"}).status_code == 422


# ---- access ------------------------------------------------------------------------------------

ADMIN_CALLS = [
    ("get", lambda a, d: a.get(f"/api/administrations/{d['id']}")),
    ("patch", lambda a, d: a.patch(f"/api/administrations/{d['id']}", json={"label": "Renamed"})),
    ("put_results", lambda a, d: put(a, d, (0, 0, 1, 2))),
    ("add_section", lambda a, d: a.post(f"/api/administrations/{d['id']}/sections", json={"name": "Extra"})),
    ("delete", lambda a, d: a.delete(f"/api/administrations/{d['id']}")),
]


@pytest.mark.parametrize(("who", "allowed"), [("regular", True), ("regular2", False), ("power", True), ("admin", True)])
@pytest.mark.parametrize(("name", "call"), ADMIN_CALLS)
def test_administration_mutation_matrix(anon, who, allowed, name, call):
    aid, _ = build_assessment(anon, who="regular")
    d = record(anon, aid)
    login_as(anon, who)
    r = call(anon, d)
    if allowed:
        assert r.status_code < 400, f"{name} as {who}: {r.status_code} {r.text}"
    else:
        assert r.status_code == 404, f"{name} as {who}: {r.status_code}"  # 404 so colleagues cannot enumerate


def test_list_shows_only_visible_administrations(anon):
    aid, _ = build_assessment(anon, who="regular")
    mine = record(anon, aid, label="Mine")
    login_as(anon, "regular2")
    theirs = record(anon, aid, label="Theirs")
    listed = {a["id"] for a in anon.get(f"/api/assessments/{aid}/administrations").json()}
    assert listed == {theirs["id"]}
    login_as(anon, "power")
    assert {a["id"] for a in anon.get(f"/api/assessments/{aid}/administrations").json()} >= {mine["id"], theirs["id"]}


def test_soft_delete_hides_and_restore_returns(anon):
    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    assert anon.delete(f"/api/administrations/{d['id']}").status_code == 204
    assert anon.get(f"/api/administrations/{d['id']}").status_code == 404
    assert d["id"] not in {a["id"] for a in anon.get(f"/api/assessments/{aid}/administrations").json()}
    assert anon.post(f"/api/administrations/{d['id']}/restore").status_code == 200
    assert anon.get(f"/api/administrations/{d['id']}").status_code == 200
    login_as(anon, "regular2")
    assert anon.post(f"/api/administrations/{d['id']}/restore").status_code == 404


def test_writes_are_audited_without_scores(anon, db):
    from app.models import AuditEvent

    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    put(anon, d, (0, 0, 7, 11))
    db.expire_all()
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.target_type == "administration", AuditEvent.target_id == str(d["id"]))
    ).all()
    assert {"administration.create", "administration.results"} <= {e.action for e in events}
    results_event = next(e for e in events if e.action == "administration.results")
    assert results_event.detail == {"rows": 1, "cleared": 0}  # counts only, never the scores
    assert all("correct" not in e.detail and "attempted" not in e.detail for e in events)


# ---- database constraints (backstop behind the API rules) --------------------------------------


def test_database_rejects_bad_result_rows(anon, db):
    from sqlalchemy.exc import IntegrityError

    from app.models import ItemResult

    aid, _ = build_assessment(anon)
    d = record(anon, aid)
    sid, iid = d["sections"][0]["id"], d["items"][0]["id"]
    for correct, attempted in ((0, 0), (5, 3), (-1, 3)):
        db.add(ItemResult(section_id=sid, administration_item_id=iid, correct=correct, attempted=attempted))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    db.add(ItemResult(section_id=sid, administration_item_id=iid, correct=1, attempted=2))
    db.commit()
    db.add(ItemResult(section_id=sid, administration_item_id=iid, correct=1, attempted=2))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ---- locking ------------------------------------------------------------------------------------


def _blocked_until_released(anon, lock_stmt_factory, request):
    """Hold a row lock in another session; the request must wait for it, then succeed."""
    from app.core.db import SessionLocal

    holder = SessionLocal()
    holder.execute(lock_stmt_factory())
    box = {}
    worker = threading.Thread(target=lambda: box.setdefault("r", request()))
    worker.start()
    time.sleep(0.8)
    still_waiting = worker.is_alive()
    holder.commit()
    holder.close()
    worker.join(15)
    return still_waiting, box.get("r")


def test_snapshot_waits_for_the_assessment_lock(anon):
    from app.models import Assessment

    aid, _ = build_assessment(anon)
    body = {"label": "x", "administered_on": "2026-09-29", "sections": ["A"]}
    waited, r = _blocked_until_released(
        anon,
        lambda: select(Assessment.id).where(Assessment.id == aid).with_for_update(),
        lambda: anon.post(f"/api/assessments/{aid}/administrations", json=body),
    )
    assert waited and r.status_code == 201


def test_assessment_item_changes_wait_for_the_assessment_lock(anon):
    from app.models import Assessment

    aid, _ = build_assessment(anon)
    waited, r = _blocked_until_released(
        anon,
        lambda: select(Assessment.id).where(Assessment.id == aid).with_for_update(),
        lambda: anon.patch(f"/api/assessments/{aid}", json={"title": "Renamed"}),
    )
    assert waited and r.status_code == 200


def test_results_batch_and_section_delete_serialise_on_the_administration_lock(anon):
    from app.models import Administration

    aid, _ = build_assessment(anon)
    d = record(anon, aid, ["A", "B"])
    waited, r = _blocked_until_released(
        anon,
        lambda: select(Administration.id).where(Administration.id == d["id"]).with_for_update(),
        lambda: put(anon, d, (0, 0, 1, 2)),
    )
    assert waited and r.status_code == 200
    waited, r = _blocked_until_released(
        anon,
        lambda: select(Administration.id).where(Administration.id == d["id"]).with_for_update(),
        lambda: anon.delete(f"/api/administrations/{d['id']}/sections/{d['sections'][1]['id']}"),
    )
    assert waited and r.status_code == 200
