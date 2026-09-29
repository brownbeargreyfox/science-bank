"""Review summary and per-question usage: universe, access filtering, pagination, pinned versions."""

import pytest

from tests.conftest import login_as
from tests.test_administrations_api import build_assessment, put, record
from tests.test_permissions import _edit_body


def summary(anon, **params):
    r = anon.get("/api/results/summary", params={"limit": 200, **params})
    assert r.status_code == 200, r.text
    return r.json()


def by_question(page):
    return {row["question_id"]: row for row in page["items"]}


def test_summary_lists_only_used_questions_with_aggregate_only_fields(anon):
    aid, qids = build_assessment(anon, n=2)
    d = record(anon, aid, ["A", "B"])
    put(anon, d, (0, 0, 5, 10), (1, 0, 7, 20))
    unused = build_assessment(anon, n=1)[1][0]
    page = summary(anon)
    rows = by_question(page)
    assert unused not in rows
    first = rows[d["items"][0]["question_id"]]
    assert (first["correct"], first["attempted"], first["times_used"]) == (12, 30, 1)
    assert first["accuracy"] == pytest.approx(0.4) and first["limited_responses"] is False
    assert first["last_used"] == "2026-09-29"
    assert "by_administration" not in first
    second = rows[d["items"][1]["question_id"]]
    assert second["accuracy"] is None and second["attempted"] == 0 and second["times_used"] == 1  # used, no data


def test_summary_sorts_lowest_accuracy_first_and_no_data_last(anon):
    aid, _ = build_assessment(anon, n=3)
    d = record(anon, aid)
    put(anon, d, (0, 0, 9, 10), (0, 1, 2, 10))  # third item has no data
    ids = [i["question_id"] for i in summary(anon)["items"]]
    order = [d["items"][1]["question_id"], d["items"][0]["question_id"], d["items"][2]["question_id"]]
    assert [q for q in ids if q in order] == order


def test_summary_limited_response_flag_uses_the_aggregate_across_sections(anon):
    aid, _ = build_assessment(anon, n=1)
    d = record(anon, aid, ["A", "B"])
    put(anon, d, (0, 0, 2, 5), (1, 0, 3, 4))  # 9 attempted in total
    assert by_question(summary(anon))[d["items"][0]["question_id"]]["limited_responses"] is True
    put(anon, d, (1, 0, 3, 5))  # now 10
    assert by_question(summary(anon))[d["items"][0]["question_id"]]["limited_responses"] is False


def test_summary_aggregates_across_administrations_and_counts_times_used(anon):
    aid, _ = build_assessment(anon, n=1)
    d1, d2 = record(anon, aid, label="One", on="2026-09-01"), record(anon, aid, label="Two", on="2026-09-20")
    put(anon, d1, (0, 0, 4, 10))
    put(anon, d2, (0, 0, 6, 10))
    row = by_question(summary(anon))[d1["items"][0]["question_id"]]
    assert (row["times_used"], row["correct"], row["attempted"], row["last_used"]) == (2, 10, 20, "2026-09-20")


def test_summary_and_usage_never_expose_another_teachers_totals(anon):
    aid, qids = build_assessment(anon, who="regular", n=1)
    mine = record(anon, aid)
    put(anon, mine, (0, 0, 3, 10))
    qid = mine["items"][0]["question_id"]
    login_as(anon, "regular2")
    assert qid not in by_question(summary(anon))
    usage = anon.get(f"/api/questions/{qid}/usage").json()
    assert usage["total"] == 0 and usage["items"] == []
    login_as(anon, "power")
    assert by_question(summary(anon))[qid]["attempted"] == 10
    assert anon.get(f"/api/questions/{qid}/usage").json()["total"] == 1


def test_soft_deleted_administrations_leave_summary_and_usage_until_restored(anon):
    aid, _ = build_assessment(anon, n=1)
    d = record(anon, aid)
    put(anon, d, (0, 0, 3, 10))
    qid = d["items"][0]["question_id"]
    anon.delete(f"/api/administrations/{d['id']}")
    assert qid not in by_question(summary(anon))
    assert anon.get(f"/api/questions/{qid}/usage").json()["total"] == 0
    anon.post(f"/api/administrations/{d['id']}/restore")
    assert qid in by_question(summary(anon))
    assert anon.get(f"/api/questions/{qid}/usage").json()["total"] == 1


def test_summary_filters_and_pagination(anon):
    aid, _ = build_assessment(anon, n=3)
    d = record(anon, aid)
    put(anon, d, (0, 0, 1, 10), (0, 1, 2, 10), (0, 2, 3, 10))
    first = summary(anon, limit=1, offset=0)
    second = summary(anon, limit=1, offset=1)
    assert (
        first["total"] >= 3
        and len(first["items"]) == 1
        and first["items"][0]["question_id"] != second["items"][0]["question_id"]
    )
    row = first["items"][0]
    same_standard = summary(anon, standard_id=row["standard_id"])["items"]
    assert same_standard and all(r["standard_id"] == row["standard_id"] for r in same_standard)
    same_family = summary(anon, family_key=row["family_key"])["items"]
    assert same_family and all(r["family_key"] == row["family_key"] for r in same_family)
    assert summary(anon, family_key="no-such-family")["total"] == 0
    assert anon.get("/api/results/summary", params={"limit": 201}).status_code == 422


def test_usage_reports_the_pinned_version_after_the_question_is_edited(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid)
    put(anon, d, (0, 0, 4, 10))
    qid = d["items"][0]["question_id"]
    login_as(anon, "power")
    assert anon.post(f"/api/questions/{qid}/versions", json=_edit_body(anon, qid)).status_code == 201
    login_as(anon, "regular")
    usage = anon.get(f"/api/questions/{qid}/usage").json()
    entry = usage["items"][0]
    assert entry["pinned_version_no"] == 1 and entry["is_current_version"] is False
    assert (entry["correct"], entry["attempted"], entry["label"]) == (4, 10, "Quiz 1")
    assert entry["assessment_id"] == aid


def test_usage_is_paginated_newest_first_and_lists_no_lineage_for_plain_questions(anon):
    aid, _ = build_assessment(anon, n=1)
    ids = [record(anon, aid, label=f"Use {n}", on=f"2026-09-0{n}")["id"] for n in (1, 2, 3)]
    qid = anon.get(f"/api/assessments/{aid}").json()["items"][0]["question_id"]
    page = anon.get(f"/api/questions/{qid}/usage", params={"limit": 2}).json()
    assert page["total"] == 3 and [e["label"] for e in page["items"]] == ["Use 3", "Use 2"]
    assert page["parent"] is None and page["variants"] == []
    assert anon.get(f"/api/questions/{qid}/usage", params={"limit": 101}).status_code == 422
    assert ids


def test_usage_of_a_missing_question_is_404(anon):
    login_as(anon, "regular")
    assert anon.get("/api/questions/999999/usage").status_code == 404
