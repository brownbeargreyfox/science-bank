"""Coverage grid: access parity, school-year boundaries, null versus zero, bundle placement, question counts.

Tests that record administrations use their own calendar years (2018 to 2022) so data left by other tests in the
shared test database cannot interfere; question counts are checked as deltas.
"""

from datetime import date

import pytest

from tests.conftest import login_as
from tests.test_administrations_api import build_assessment, put, record
from tests.test_permissions import make_question

BIO1 = "biology-1"
CODE = "B-LS2-1"  # every helper-made question is for this standard


def course_id(anon, slug=BIO1) -> int:
    return next(c["id"] for c in anon.get("/api/courses").json() if c["slug"] == slug)


def coverage(anon, slug=BIO1, **params):
    r = anon.get("/api/coverage", params={"course_id": course_id(anon, slug), **params})
    assert r.status_code == 200, r.text
    return r.json()


def rows_for(page, code=CODE):
    """Every appearance of a standard across the groups: [(group_name, row)]."""
    return [(g["name"], s) for g in page["groups"] for s in g["standards"] if s["code"] == code]


def row(page, code=CODE):
    return rows_for(page, code)[0][1]


# ---- scope and validation ----------------------------------------------------------------------


def test_requires_login(anon):
    assert anon.get("/api/coverage", params={"course_id": 1}).status_code == 401


def test_unknown_course_is_404_and_missing_course_is_422(client):
    assert client.get("/api/coverage", params={"course_id": 999999}).status_code == 404
    assert client.get("/api/coverage").status_code == 422


@pytest.mark.parametrize("bad", ["abc", "1999", "ALL", "2026-27", ""])
def test_invalid_year_is_422(client, bad):
    r = client.get("/api/coverage", params={"course_id": course_id(client), "year": bad})
    assert r.status_code == 422


def test_scope_for_a_school_year_and_for_all_time(client):
    page = coverage(client, year="2020")
    assert page["scope"] == {
        "kind": "school_year",
        "year": 2020,
        "label": "2020-21 school year",
        "start": "2020-08-01",
        "end": "2021-07-31",
    }
    assert 2020 in page["available_years"]  # the resolved year is always offered
    page = coverage(client, year="all")
    assert page["scope"] == {"kind": "all_time", "year": None, "label": "All time", "start": None, "end": None}


def test_default_year_follows_the_server_clock(client, monkeypatch):
    monkeypatch.setattr("app.api.coverage.today", lambda: date(2040, 3, 1))
    page = coverage(client)
    assert page["scope"]["year"] == 2039 and page["scope"]["label"] == "2039-40 school year"
    assert 2039 in page["available_years"]
    monkeypatch.setattr("app.api.coverage.today", lambda: date(2040, 8, 1))
    assert coverage(client)["scope"]["year"] == 2040


# ---- school-year boundaries -------------------------------------------------------------------


def test_jul_31_and_aug_1_fall_in_different_school_years(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    record(anon, aid, label="Last day", on="2019-07-31")
    record(anon, aid, label="First day", on="2019-08-01")
    prior, this = coverage(anon, year="2018"), coverage(anon, year="2019")
    assert (row(prior)["times_assessed"], row(prior)["last_assessed"]) == (1, "2019-07-31")
    assert (row(this)["times_assessed"], row(this)["last_assessed"]) == (1, "2019-08-01")
    both = coverage(anon, year="all")
    assert row(both)["times_assessed"] >= 2
    assert {2018, 2019} <= set(both["available_years"])
    assert both["available_years"] == sorted(both["available_years"], reverse=True)


def test_a_year_with_no_administrations_still_lists_every_standard(anon):
    login_as(anon, "regular")
    page = coverage(anon, year="2017")
    all_standards = anon.get("/api/standards", params={"course_id": course_id(anon)}).json()
    listed = {s["code"] for g in page["groups"] for s in g["standards"]}
    assert listed == {s["code"] for s in all_standards}
    assert all(
        s["times_assessed"] == 0 and s["accuracy"] is None and s["last_assessed"] is None
        for g in page["groups"]
        for s in g["standards"]
    )
    assert page["summary"]["standards_assessed"] == 0
    assert page["summary"]["standards_total"] == len(all_standards)


# ---- access ------------------------------------------------------------------------------------


def test_administration_figures_follow_the_results_summary_visibility(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid, on="2020-10-10")
    put(anon, d, (0, 0, 7, 10))
    login_as(anon, "regular")
    mine = row(coverage(anon, year="2020"))
    assert (mine["times_assessed"], mine["correct"], mine["attempted"]) == (1, 7, 10)
    login_as(anon, "regular2")
    theirs = row(coverage(anon, year="2020"))
    assert (theirs["times_assessed"], theirs["attempted"], theirs["accuracy"]) == (0, 0, None)
    for who in ("power", "admin"):
        login_as(anon, who)
        seen = row(coverage(anon, year="2020"))
        assert (seen["times_assessed"], seen["correct"], seen["attempted"]) == (1, 7, 10)


@pytest.mark.parametrize("who", ["regular", "regular2", "power", "admin"])
def test_attempted_matches_the_results_summary_for_the_same_user(anon, who):
    aid, _ = build_assessment(anon, who="regular", n=2)
    d = record(anon, aid, ["A", "B"], on="2012-05-05")
    put(anon, d, (0, 0, 3, 10), (1, 1, 4, 8))
    login_as(anon, who)
    page = coverage(anon, year="all")
    summary = anon.get("/api/results/summary", params={"course_id": course_id(anon), "limit": 200}).json()["items"]
    expected: dict[str, int] = {}
    for item in summary:
        expected[item["standard_code"]] = expected.get(item["standard_code"], 0) + item["attempted"]
    for g in page["groups"]:
        for s in g["standards"]:
            assert s["attempted"] == expected.get(s["code"], 0), (who, s["code"])


def test_question_counts_are_department_wide(anon):
    login_as(anon, "regular")
    before = row(coverage(anon, year="2017"))["questions"]
    make_question(anon, "power")  # saves a whole generated set
    seen = []
    for who in ("regular", "regular2", "power", "admin"):
        login_as(anon, who)
        seen.append(row(coverage(anon, year="2017"))["questions"])
    assert seen[0]["generated"] > before["generated"]
    assert all(s == seen[0] for s in seen)


# ---- numbers ----------------------------------------------------------------------------------


def test_zero_is_a_number_and_blank_is_not(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid, on="2013-10-01")
    s = row(coverage(anon, year="2013"))
    assert (s["times_assessed"], s["attempted"], s["accuracy"], s["limited_responses"]) == (1, 0, None, False)
    put(anon, d, (0, 0, 0, 30))
    s = row(coverage(anon, year="2013"))
    assert (s["correct"], s["attempted"], s["accuracy"]) == (0, 30, 0.0)


def test_limited_response_count_is_the_aggregate_across_sections(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid, ["A", "B"], on="2015-11-01")
    put(anon, d, (0, 0, 2, 5), (1, 0, 3, 4))  # 9 attempted in total
    assert row(coverage(anon, year="2015"))["limited_responses"] is True
    put(anon, d, (1, 0, 3, 5))  # 10
    assert row(coverage(anon, year="2015"))["limited_responses"] is False


def test_accuracy_is_summed_not_averaged_and_times_assessed_counts_administrations(anon):
    aid, _ = build_assessment(anon, who="regular", n=2)  # two questions, same standard
    d = record(anon, aid, ["A", "B"], on="2014-12-01")
    put(anon, d, (0, 0, 1, 2), (1, 0, 9, 18), (0, 1, 1, 2))
    s = row(coverage(anon, year="2014"))
    assert s["times_assessed"] >= 1
    assert s["accuracy"] == pytest.approx(s["correct"] / s["attempted"])


def test_soft_deleted_administrations_are_excluded_until_restored(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid, on="2022-09-09")
    put(anon, d, (0, 0, 3, 10))
    assert row(coverage(anon, year="2022"))["times_assessed"] == 1
    anon.delete(f"/api/administrations/{d['id']}")
    assert row(coverage(anon, year="2022"))["times_assessed"] == 0
    anon.post(f"/api/administrations/{d['id']}/restore")
    assert row(coverage(anon, year="2022"))["times_assessed"] == 1


# ---- question counts --------------------------------------------------------------------------


def test_question_counts_include_all_five_statuses_and_ignore_the_date_range(anon):
    qid = make_question(anon, "power")
    for status in ("reviewed", "approved"):
        assert anon.post(f"/api/questions/{qid}/status", json={"to_status": status}).status_code == 200
    a, b = coverage(anon, year="2022"), coverage(anon, year="all")
    assert set(row(a)["questions"]) == {"generated", "reviewed", "approved", "rejected", "archived"}
    assert row(a)["questions"] == row(b)["questions"]
    assert row(a)["questions"]["approved"] >= 1


# ---- bundles ----------------------------------------------------------------------------------


@pytest.mark.parametrize("slug", ["biology-1", "biology-2", "chemistry"])
def test_bundle_placement_matches_the_bundles_endpoint(client, slug):
    cid = course_id(client, slug)
    page = coverage(client, slug, year="2017")
    bundles = client.get("/api/bundles", params={"course_id": cid}).json()
    standards = client.get("/api/standards", params={"course_id": cid}).json()
    by_name = {g["name"]: g for g in page["groups"]}
    in_bundle: dict[str, list[str]] = {}
    for b in bundles:
        for a in b["aligned"]:
            in_bundle.setdefault(a["code"], []).append(b["name"])
        if b["aligned"]:
            g = by_name[b["name"]]
            assert [s["code"] for s in g["standards"]] == [a["code"] for a in b["aligned"]]
            assert (g["total"], g["assessed"]) == (len(b["aligned"]), 0)
            partial = {a["code"]: a["partial"] for a in b["aligned"]}
            assert all(s["partial"] == partial[s["code"]] for s in g["standards"])
    for code, names in in_bundle.items():
        for group_name, s in rows_for(page, code):
            assert s["also_in"] == [n for n in names if n != group_name]
        assert len(rows_for(page, code)) == len(names)
    unbundled = {s["code"] for s in standards} - set(in_bundle)
    other = by_name.get("Other standards")
    if unbundled:
        assert other is not None and {s["code"] for s in other["standards"]} == unbundled
        assert page["groups"][-1]["name"] == "Other standards" and other["bundle_id"] is None
    else:
        assert other is None
    assert page["summary"]["standards_total"] == len(standards)
    assert [g["name"] for g in page["groups"] if g["name"] != "Other standards"] == [
        b["name"] for b in bundles if b["aligned"]
    ]


def test_a_standard_in_two_bundles_is_counted_once_in_the_summary(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    record(anon, aid, on="2016-02-02")
    page = coverage(anon, year="2015")
    appearances = len(rows_for(page))
    assert page["summary"]["standards_assessed"] == 1  # B-LS2-1 once, however many bundles list it
    assert sum(g["assessed"] for g in page["groups"]) == appearances


def test_families_come_from_the_registry(client):
    s = row(coverage(client, year="2017"))
    assert "population-carrying-capacity" in s["families"]
    assert row(coverage(client, year="2017"), "B-LS1-1")["families"] == []
