# Coverage Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/coverage` page and `GET /api/coverage` endpoint showing, per standard in a course and grouped by bundle, the bank's question counts and what the teacher has **assessed** in a chosen school year.

**Architecture:** A pure `services/coverage.py` resolves the school-year scope (Aug 1 to Jul 31, or all time). A new read-only router joins `AdministrationItem` to `Administration` using the same `visible_clauses(user)` as `/api/results/summary`, groups by the question's standard, and assembles bundle groups. The React page renders the server's scope verbatim and never computes dates.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest on Postgres; React 19, react-router, TanStack Query, openapi-fetch, Tailwind tokens already in `index.css`.

**Spec:** `docs/superpowers/specs/2026-10-02-coverage-grid-design.md`

## Global Constraints

- Default scope is the current school year, **Aug 1 to Jul 31**; "All time" is an explicit `year=all`, never a fallback.
- Administration figures use `visible_clauses(user)` (`backend/app/services/administrations.py`) exactly; no new access rule. Question counts are department-wide and not date-scoped.
- The endpoint returns the resolved scope (`kind`, `year`, `label`, `start`, `end`); the UI never computes or restates it.
- Wording is "assessed", never "covered", "mastered", "gap", or "behind". The page states it shows what was assessed, not what was taught.
- Blank is never zero: `accuracy` is `null` when `attempted = 0`; use `accuracy()` and `limited_responses()` from `app/services/results.py`.
- No migration, no new dependency, no new state library. No `window.confirm`.
- Backend runs from `backend/` with `.venv/bin/ruff check app tests` and `.venv/bin/python -m pytest` against a throwaway Postgres (never production); the acceptance bar is zero skipped DB tests. Frontend checks from `frontend/`: `npx tsc -b`, `npm run lint`, `npm run build`.
- Files are formatted to the repo's prettier width; match surrounding code style.

## Review Focus

- A standard in two bundles: appears under both with the other bundle in `also_in`, counted once in `summary` (Task 2 test).
- A visible administration on Jul 31 versus Aug 1 lands in different school years; year `all` includes both (Task 2 test).
- A teacher with no administrations in range still sees every standard, as "Not assessed in this period", never an error or empty page (Task 2 and Task 3).
- 0 of 30 correct shows `0%`; no results shows `—`; 1 to 9 attempted shows "Limited response count" (Task 2 and Task 3).
- `?year=` junk, `?year=1999`, and `?course=` that is not in the list must not crash the page (Task 3 selectors fall back to server defaults).

## File map

| File | Responsibility |
|---|---|
| `backend/app/services/coverage.py` (create) | Pure scope logic: `Scope`, `school_year_for`, `school_year_range`, `school_year_label`, `resolve_scope`, `today` |
| `backend/app/schemas/__init__.py` (modify, append) | `CoverageScope`, `QuestionCounts`, `CoverageStandard`, `CoverageGroup`, `CoverageSummary`, `CoverageCourse`, `CoveragePage` |
| `backend/app/api/coverage.py` (create) | `GET /coverage` |
| `backend/app/main.py` (modify) | register router |
| `backend/tests/test_coverage_logic.py` (create) | pure tests, no DB |
| `backend/tests/test_coverage_api.py` (create) | DB tests |
| `frontend/openapi.json`, `frontend/src/api/schema.d.ts` (regenerate) | API types |
| `frontend/src/api/queries.ts` (modify) | `useCoveragePage` |
| `frontend/src/pages/Coverage.tsx` (create) | the page |
| `frontend/src/main.tsx`, `src/components/Layout.tsx`, `src/components/navIcons.tsx` (modify) | route, nav, icon |
| `frontend/src/components/dashboard/ResultsWidgets.tsx` (modify) | link from the Overview coverage widget |
| `HANDOFF.md` (modify) | record the feature |

Note: `frontend/src/components/dashboard/data.ts` already exports a different `useCoverage` (the Overview strip). Do not reuse or rename it; the new hook is `useCoveragePage`.

---

### Task 1: School-year scope logic (pure)

**Files:**
- Create: `backend/app/services/coverage.py`
- Test: `backend/tests/test_coverage_logic.py`

**Interfaces:**
- Produces: `Scope` (frozen dataclass: `kind: str`, `year: int | None`, `label: str`, `start: date | None`, `end: date | None`); `school_year_for(d: date) -> int`; `school_year_range(year: int) -> tuple[date, date]`; `school_year_label(year: int) -> str`; `resolve_scope(raw: str | None, current: date) -> Scope` (raises `ValueError` with a teacher-readable message); `today() -> date`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_coverage_logic.py`:

```python
"""School-year scope rules for the coverage grid. Pure; no database."""

from datetime import date

import pytest

from app.services.coverage import (
    resolve_scope,
    school_year_for,
    school_year_label,
    school_year_range,
)


@pytest.mark.parametrize(
    ("d", "year"),
    [
        (date(2026, 7, 31), 2025),
        (date(2026, 8, 1), 2026),
        (date(2027, 1, 15), 2026),
        (date(2027, 7, 31), 2026),
        (date(2027, 8, 1), 2027),
        (date(2028, 2, 29), 2027),  # leap day belongs to the year that began the previous August
    ],
)
def test_school_year_for_splits_on_august_first(d, year):
    assert school_year_for(d) == year


def test_school_year_range_is_inclusive_aug_1_to_jul_31():
    assert school_year_range(2026) == (date(2026, 8, 1), date(2027, 7, 31))


def test_school_year_label_uses_two_digit_end_year():
    assert school_year_label(2026) == "2026-27 school year"
    assert school_year_label(2099) == "2099-00 school year"


def test_resolve_scope_defaults_to_the_current_school_year():
    s = resolve_scope(None, date(2027, 3, 1))
    assert (s.kind, s.year, s.label) == ("school_year", 2026, "2026-27 school year")
    assert (s.start, s.end) == (date(2026, 8, 1), date(2027, 7, 31))
    assert resolve_scope(None, date(2027, 8, 1)).year == 2027


def test_resolve_scope_all_is_explicit_and_unbounded():
    s = resolve_scope("all", date(2027, 3, 1))
    assert (s.kind, s.year, s.label, s.start, s.end) == ("all_time", None, "All time", None, None)


def test_resolve_scope_accepts_a_school_year_start():
    s = resolve_scope("2024", date(2027, 3, 1))
    assert (s.year, s.start, s.end) == (2024, date(2024, 8, 1), date(2025, 7, 31))


@pytest.mark.parametrize("raw", ["abc", "", "ALL", "2026-27", "1999", "2101", "-5", "20.5"])
def test_resolve_scope_rejects_anything_else(raw):
    with pytest.raises(ValueError, match="year"):
        resolve_scope(raw, date(2027, 3, 1))
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/bin/python -m pytest tests/test_coverage_logic.py -q`
Expected: FAIL (`ModuleNotFoundError: app.services.coverage`).

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/coverage.py`:

```python
"""Scope rules for the coverage grid: a school year runs Aug 1 to Jul 31, or all time. Pure; no database."""

from dataclasses import dataclass
from datetime import date

SCHOOL_YEAR_START_MONTH = 8
MIN_YEAR, MAX_YEAR = 2000, 2100


@dataclass(frozen=True)
class Scope:
    kind: str  # "school_year" | "all_time"
    year: int | None
    label: str
    start: date | None
    end: date | None


def today() -> date:
    """The server's date. A function so tests can substitute a clock."""
    return date.today()


def school_year_for(d: date) -> int:
    """The calendar year in which the school year containing `d` began."""
    return d.year if d.month >= SCHOOL_YEAR_START_MONTH else d.year - 1


def school_year_range(year: int) -> tuple[date, date]:
    return date(year, SCHOOL_YEAR_START_MONTH, 1), date(year + 1, SCHOOL_YEAR_START_MONTH - 1, 31)


def school_year_label(year: int) -> str:
    return f"{year}-{(year + 1) % 100:02d} school year"


def resolve_scope(raw: str | None, current: date) -> Scope:
    """`None` is the current school year, `"all"` is every date, a four-digit year is that school year's start."""
    if raw is None:
        year = school_year_for(current)
    elif raw == "all":
        return Scope("all_time", None, "All time", None, None)
    elif raw.isascii() and raw.isdigit() and MIN_YEAR <= int(raw) <= MAX_YEAR:
        year = int(raw)
    else:
        raise ValueError(f'year must be "all" or a school-year start between {MIN_YEAR} and {MAX_YEAR}')
    start, end = school_year_range(year)
    return Scope("school_year", year, school_year_label(year), start, end)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_coverage_logic.py -q` and `.venv/bin/ruff check app tests`
Expected: all pass, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/coverage.py backend/tests/test_coverage_logic.py
git commit -m "feat: school-year scope rules for the coverage grid"
```

---

### Task 2: Coverage endpoint

**Files:**
- Modify: `backend/app/schemas/__init__.py` (append after `ResultsSummaryPage`, before `QuestionRef`)
- Create: `backend/app/api/coverage.py`
- Modify: `backend/app/main.py:7` area (import) and `:46` (module tuple)
- Test: `backend/tests/test_coverage_api.py`
- Regenerate: `frontend/openapi.json`, `frontend/src/api/schema.d.ts`

**Interfaces:**
- Consumes: Task 1's `resolve_scope`, `today`, `SCHOOL_YEAR_START_MONTH`; `visible_clauses` from `app.services.administrations`; `accuracy`, `limited_responses` from `app.services.results`; `families_for_standard` from `app.services.families.registry`; `not_found` from `app.services.bank`.
- Produces: `GET /api/coverage?course_id=<int>&year=<str|omitted>` returning `CoveragePage` (shape in the spec). Tests monkeypatch `app.api.coverage.today`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_coverage_api.py`. Tests in this file each use their own calendar years (2018 to 2022) for administrations so data left by other tests in the shared test database cannot interfere; question counts are checked as deltas.

```python
"""Coverage grid: access parity, school-year boundaries, null versus zero, bundle placement, question counts."""

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
    page = coverage(anon, year="2022")
    all_standards = anon.get("/api/standards", params={"course_id": course_id(anon)}).json()
    listed = {s["code"] for g in page["groups"] for s in g["standards"]}
    assert listed == {s["code"] for s in all_standards}
    assert all(s["times_assessed"] == 0 and s["accuracy"] is None and s["last_assessed"] is None
               for g in page["groups"] for s in g["standards"])
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
    d = record(anon, aid, ["A", "B"], on="2018-05-05")
    put(anon, d, (0, 0, 3, 10), (1, 1, 4, 8))
    login_as(anon, who)
    page = coverage(anon, year="all")
    summary = anon.get(
        "/api/results/summary", params={"course_id": course_id(anon), "limit": 200}
    ).json()["items"]
    expected: dict[str, int] = {}
    for item in summary:
        expected[item["standard_code"]] = expected.get(item["standard_code"], 0) + item["attempted"]
    for g in page["groups"]:
        for s in g["standards"]:
            assert s["attempted"] == expected.get(s["code"], 0), (who, s["code"])


def test_question_counts_are_department_wide(anon):
    login_as(anon, "regular")
    before = row(coverage(anon, year="2022"))["questions"]
    make_question(anon, "power")
    for who in ("regular", "regular2", "power", "admin"):
        login_as(anon, who)
        after = row(coverage(anon, year="2022"))["questions"]
        assert after["generated"] == before["generated"] + 1


# ---- numbers ----------------------------------------------------------------------------------


def test_zero_is_a_number_and_blank_is_not(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid, on="2021-10-01")
    s = row(coverage(anon, year="2021"))
    assert (s["times_assessed"], s["attempted"], s["accuracy"], s["limited_responses"]) == (1, 0, None, False)
    put(anon, d, (0, 0, 0, 30))
    s = row(coverage(anon, year="2021"))
    assert (s["correct"], s["attempted"], s["accuracy"]) == (0, 30, 0.0)


def test_limited_response_count_is_the_aggregate_across_sections(anon):
    aid, _ = build_assessment(anon, who="regular", n=1)
    d = record(anon, aid, ["A", "B"], on="2021-11-01")
    put(anon, d, (0, 0, 2, 5), (1, 0, 3, 4))  # 9 attempted in total
    assert row(coverage(anon, year="2021"))["limited_responses"] is True
    put(anon, d, (1, 0, 3, 5))  # 10
    assert row(coverage(anon, year="2021"))["limited_responses"] is False


def test_accuracy_is_summed_not_averaged_and_times_assessed_counts_administrations(anon):
    aid, _ = build_assessment(anon, who="regular", n=2)  # two questions, same standard
    d = record(anon, aid, ["A", "B"], on="2021-12-01")
    put(anon, d, (0, 0, 1, 2), (1, 0, 9, 18), (0, 1, 1, 2))
    s = row(coverage(anon, year="2021"))
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
    page = coverage(client, slug, year="2022")
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
    record(anon, aid, on="2022-02-02")
    page = coverage(anon, year="2022")
    appearances = len(rows_for(page))
    assert page["summary"]["standards_assessed"] == 1  # B-LS2-1 once, however many bundles list it
    assert sum(g["assessed"] for g in page["groups"]) == appearances


def test_families_come_from_the_registry(client):
    s = row(coverage(client, year="2022"))
    assert "population-carrying-capacity" in s["families"]
    assert row(coverage(client, year="2022"), "B-LS1-1")["families"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Start a throwaway Postgres (port 54332 per the working agreement; check `docker ps` first and never stop a container you did not start):

```bash
docker run -d --rm --name sb-testdb -p 127.0.0.1:54332:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
cd backend && TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test \
  .venv/bin/python -m pytest tests/test_coverage_api.py -q
```

Expected: FAIL (404 on `/api/coverage`, and `monkeypatch` target `app.api.coverage` missing).

- [ ] **Step 3: Add the schemas**

In `backend/app/schemas/__init__.py`, insert after `ResultsSummaryPage` (before `class QuestionRef`):

```python
# ---- coverage ---------------------------------------------------------------------------------


class CoverageScope(BaseModel):
    kind: Literal["school_year", "all_time"]
    year: int | None
    label: str
    start: date | None
    end: date | None


class QuestionCounts(BaseModel):
    generated: int
    reviewed: int
    approved: int
    rejected: int
    archived: int


class CoverageStandard(BaseModel):
    standard_id: int
    code: str
    expectation: str
    domain_code: str
    partial: bool
    also_in: list[str]
    families: list[str]
    questions: QuestionCounts
    times_assessed: int
    last_assessed: date | None
    correct: int
    attempted: int
    accuracy: float | None
    limited_responses: bool


class CoverageGroup(BaseModel):
    bundle_id: int | None
    name: str
    assessed: int
    total: int
    standards: list[CoverageStandard]


class CoverageSummary(BaseModel):
    standards_total: int
    standards_assessed: int


class CoverageCourse(BaseModel):
    id: int
    name: str


class CoveragePage(BaseModel):
    scope: CoverageScope
    available_years: list[int]
    course: CoverageCourse
    groups: list[CoverageGroup]
    summary: CoverageSummary
```

- [ ] **Step 4: Write the endpoint**

Create `backend/app/api/coverage.py`:

```python
"""Coverage grid: per standard in a course, bank readiness and what the viewer has assessed, grouped by bundle."""

from typing import get_args

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Administration,
    AdministrationItem,
    Bundle,
    Course,
    ItemResult,
    Question,
    Standard,
    User,
)
from app.schemas import (
    CoverageCourse,
    CoverageGroup,
    CoveragePage,
    CoverageScope,
    CoverageStandard,
    CoverageSummary,
    QuestionCounts,
    QuestionStatus,
)
from app.services.administrations import visible_clauses
from app.services.bank import not_found
from app.services.coverage import SCHOOL_YEAR_START_MONTH, resolve_scope, today
from app.services.families.registry import families_for_standard
from app.services.results import accuracy, limited_responses

router = APIRouter(tags=["coverage"])

STATUSES = get_args(QuestionStatus)
OTHER_STANDARDS = "Other standards"


@router.get("/coverage", response_model=CoveragePage)
def coverage(
    course_id: int,
    year: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoveragePage:
    """What the viewer has assessed in a school year (or all time), by standard and bundle. Not what was taught."""
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("Course")
    try:
        scope = resolve_scope(year, today())
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    standards = db.scalars(
        select(Standard)
        .options(selectinload(Standard.course))
        .where(Standard.course_id == course_id)
        .order_by(Standard.sort_order, Standard.id)
    ).all()
    by_id = {s.id: s for s in standards}
    ids = list(by_id)

    counts = {sid: dict.fromkeys(STATUSES, 0) for sid in ids}
    for standard_id, q_status, n in db.execute(
        select(Question.standard_id, Question.status, func.count())
        .where(Question.standard_id.in_(ids))
        .group_by(Question.standard_id, Question.status)
    ):
        counts[standard_id][q_status] = n

    used = (
        select(
            Question.standard_id.label("standard_id"),
            func.count(func.distinct(Administration.id)).label("times"),
            func.max(Administration.administered_on).label("last"),
            func.coalesce(func.sum(ItemResult.correct), 0).label("correct"),
            func.coalesce(func.sum(ItemResult.attempted), 0).label("attempted"),
        )
        .select_from(AdministrationItem)
        .join(Administration, Administration.id == AdministrationItem.administration_id)
        .join(Question, Question.id == AdministrationItem.question_id)
        .outerjoin(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
        .where(Question.standard_id.in_(ids), *visible_clauses(user))
        .group_by(Question.standard_id)
    )
    if scope.start is not None and scope.end is not None:
        used = used.where(Administration.administered_on >= scope.start, Administration.administered_on <= scope.end)
    activity = {r.standard_id: r for r in db.execute(used)}

    def build(s: Standard, partial: bool, also_in: list[str]) -> CoverageStandard:
        a = activity.get(s.id)
        correct, attempted = (a.correct, a.attempted) if a else (0, 0)
        return CoverageStandard(
            standard_id=s.id,
            code=s.code,
            expectation=s.performance_expectation,
            domain_code=s.domain_code,
            partial=partial,
            also_in=also_in,
            families=[f.key for f in families_for_standard(s)],
            questions=QuestionCounts(**counts[s.id]),
            times_assessed=a.times if a else 0,
            last_assessed=a.last if a else None,
            correct=correct,
            attempted=attempted,
            accuracy=accuracy(correct, attempted),
            limited_responses=limited_responses(attempted),
        )

    bundles = db.scalars(
        select(Bundle)
        .options(selectinload(Bundle.aligned))
        .where(Bundle.course_id == course_id)
        .order_by(Bundle.sort_order, Bundle.id)
    ).all()
    membership: dict[int, list[str]] = {}
    for b in bundles:
        for link in b.aligned:
            if link.standard_id in by_id:
                membership.setdefault(link.standard_id, []).append(b.name)

    def group(bundle_id: int | None, name: str, rows: list[CoverageStandard]) -> CoverageGroup:
        return CoverageGroup(
            bundle_id=bundle_id,
            name=name,
            assessed=sum(1 for r in rows if r.times_assessed > 0),
            total=len(rows),
            standards=rows,
        )

    groups = []
    for b in bundles:
        rows = [
            build(by_id[link.standard_id], link.partial, [n for n in membership[link.standard_id] if n != b.name])
            for link in b.aligned
            if link.standard_id in by_id
        ]
        if rows:
            groups.append(group(b.id, b.name, rows))
    unbundled = [build(s, False, []) for s in standards if s.id not in membership]
    if unbundled:
        groups.append(group(None, OTHER_STANDARDS, unbundled))

    month = Administration.administered_on
    start_year = func.extract("year", month) - case((func.extract("month", month) < SCHOOL_YEAR_START_MONTH, 1), else_=0)
    years = {int(y) for y in db.scalars(select(start_year).where(*visible_clauses(user)).distinct())}
    if scope.year is not None:
        years.add(scope.year)

    return CoveragePage(
        scope=CoverageScope(kind=scope.kind, year=scope.year, label=scope.label, start=scope.start, end=scope.end),
        available_years=sorted(years, reverse=True),
        course=CoverageCourse(id=course.id, name=course.name),
        groups=groups,
        summary=CoverageSummary(
            standards_total=len(standards), standards_assessed=sum(1 for s in standards if s.id in activity)
        ),
    )
```

In `backend/app/main.py`, add `coverage` to the `from app.api import ...` line and to the tuple:

```python
for module in (standards, generate, variants, questions, assessments, administrations, results, coverage, admin):
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests
TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest tests/test_coverage_api.py tests/test_coverage_logic.py -q
```

Expected: all pass. If `test_attempted_matches_the_results_summary...` fails for a user, the join or `visible_clauses` differs from `/api/results/summary`; fix the coverage query, never the test. If `test_bundle_placement...` fails because a bundle lists a standard from another course, keep the `in by_id` guard and adjust the test to the same guard.

- [ ] **Step 6: Run the whole backend suite**

```bash
TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q
```

Expected: zero failures, zero skipped DB tests; `test_every_mutating_route_is_policy_covered` still passes (the route is a GET, so no `POLICY_COVERED` entry).

- [ ] **Step 7: Regenerate the API types**

```bash
cd backend && .venv/bin/python scripts/dump_openapi.py
cd ../frontend && npm run gen:api
git diff --stat openapi.json src/api/schema.d.ts
```

Expected: both files change, and only by the coverage additions (`/api/coverage`, `CoveragePage` and friends).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/__init__.py backend/app/api/coverage.py backend/app/main.py \
  backend/tests/test_coverage_api.py frontend/openapi.json frontend/src/api/schema.d.ts
git commit -m "feat: coverage endpoint grouped by bundle with a school-year scope"
```

---

### Task 3: Coverage page, route, and navigation

**Files:**
- Modify: `frontend/src/api/queries.ts` (append `useCoveragePage`)
- Create: `frontend/src/pages/Coverage.tsx`
- Modify: `frontend/src/main.tsx` (import + route), `frontend/src/components/Layout.tsx:11-18` (NAV), `frontend/src/components/navIcons.tsx`
- Modify: `frontend/src/components/dashboard/ResultsWidgets.tsx` (link in the coverage widget)

**Interfaces:**
- Consumes: `GET /api/coverage` types from Task 2 (`schema.d.ts`); `accuracyText` from `src/lib/results.ts` (signature `(correct: number, attempted: number) => string`, returns `—` when attempted is 0); `useCourses` from `src/api/queries.ts`; `CodeTag`, `Empty`, `ErrorNotice`, `Loading`, `PageHeader` from `src/components/ui.tsx`.
- Produces: route `/coverage` reading `?course=<id>&year=<start-year|all>`.

- [ ] **Step 1: Add the query hook**

Append to `frontend/src/api/queries.ts`:

```ts
/** The coverage grid for a course. `year` is a school-year start, "all", or null for the server's default year. */
export function useCoveragePage(courseId: number | null, year: string | null) {
  return useQuery({
    queryKey: ["coverage", courseId, year],
    queryFn: () =>
      unwrap(
        api.GET("/api/coverage", {
          params: { query: cleanQuery({ course_id: courseId ?? 0, year: year ?? undefined }) },
        }),
      ),
    enabled: courseId !== null,
  });
}
```

- [ ] **Step 2: Add the icon and nav item**

In `navIcons.tsx`, import `TableSimple24Filled, TableSimple24Regular` from `@fluentui/react-icons` (keep the import list sorted as it is) and add to `NAV_ICONS`:

```ts
  "/coverage": { regular: TableSimple24Regular, filled: TableSimple24Filled },
```

In `Layout.tsx`, add to `NAV` between Bundles and Generate:

```ts
  { to: "/coverage", label: "Coverage" },
```

In `main.tsx`, add `import CoveragePage from "./pages/Coverage";` with the other page imports (alphabetical) and the route after `/bundles`:

```tsx
          { path: "/coverage", element: <CoveragePage /> },
```

- [ ] **Step 3: Write the page**

Create `frontend/src/pages/Coverage.tsx`:

```tsx
import { Link, useSearchParams } from "react-router";
import { useCourses, useCoveragePage } from "../api/queries";
import { accuracyText } from "../lib/results";
import { CodeTag, Empty, ErrorNotice, Loading, PageHeader } from "../components/ui";

const STATUS_ORDER = ["generated", "reviewed", "approved", "rejected", "archived"] as const;

export default function CoveragePage() {
  const [params, setParams] = useSearchParams();
  const courses = useCourses();
  const courseId = Number(params.get("course")) || courses.data?.[0]?.id || null;
  const yearParam = params.get("year");
  const coverage = useCoveragePage(courseId, yearParam);
  const data = coverage.data;
  const course = courses.data?.find((c) => c.id === courseId);

  const update = (next: Record<string, string | null>) => {
    const merged = new URLSearchParams(params);
    for (const [key, value] of Object.entries(next)) {
      if (value === null) merged.delete(key);
      else merged.set(key, value);
    }
    setParams(merged, { replace: true });
  };

  return (
    <>
      <PageHeader
        title="Coverage"
        lead="Which standards you have assessed in the period you choose, with the questions available for each. This shows what was assessed, not what has been taught."
      />
      <div className="no-print mb-4 flex flex-wrap gap-4">
        <div className="min-w-[14rem]">
          <label htmlFor="cov-course" className="field-label">
            Course
          </label>
          <select
            id="cov-course"
            className="input"
            value={courseId ?? ""}
            onChange={(e) => update({ course: e.target.value })}
          >
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.use_year})
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[14rem]">
          <label htmlFor="cov-year" className="field-label">
            School year
          </label>
          <select
            id="cov-year"
            className="input"
            value={data ? (data.scope.kind === "all_time" ? "all" : String(data.scope.year)) : (yearParam ?? "")}
            onChange={(e) => update({ year: e.target.value })}
            disabled={!data}
          >
            {data?.available_years.map((y) => (
              <option key={y} value={y}>
                {y}-{String((y + 1) % 100).padStart(2, "0")} school year
              </option>
            ))}
            <option value="all">All time</option>
          </select>
        </div>
      </div>

      <ErrorNotice error={coverage.error} />
      {coverage.isPending ? (
        <Loading />
      ) : data ? (
        <>
          <p className="mb-5 text-sm" data-testid="coverage-scope">
            <strong>{data.scope.label}</strong>
            {data.scope.start && data.scope.end ? (
              <span className="text-muted">
                {" "}
                ({data.scope.start} to {data.scope.end})
              </span>
            ) : null}
            <span className="text-muted">
              {" "}
              · {data.summary.standards_assessed} of {data.summary.standards_total} standards assessed in this period.
              Assessed means recorded in an assessment you can see.
            </span>
          </p>
          {data.groups.length === 0 ? (
            <Empty>{course?.name ?? "This course"} has no standards in the imported data.</Empty>
          ) : (
            <div className="space-y-5">
              {data.groups.map((group) => (
                <section
                  key={group.bundle_id ?? "other"}
                  className="panel p-4 sm:p-5"
                  aria-labelledby={`cov-${group.bundle_id ?? "other"}`}
                >
                  <h2 id={`cov-${group.bundle_id ?? "other"}`} className="text-lg font-bold">
                    {group.name}
                  </h2>
                  <p className="mt-0.5 text-sm text-muted">
                    {group.assessed} of {group.total} standards assessed in this period
                  </p>
                  <ul className="mt-3 divide-y divide-line-soft">
                    {group.standards.map((s) => {
                      const none = STATUS_ORDER.every((k) => s.questions[k] === 0);
                      const query = new URLSearchParams({ standard: String(s.standard_id) });
                      if (group.bundle_id !== null) query.set("bundle", String(group.bundle_id));
                      if (s.families.length === 1) query.set("family", s.families[0]);
                      return (
                        <li key={s.standard_id} className="grid gap-x-4 gap-y-2 py-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_auto]">
                          <div className="min-w-0">
                            <CodeTag code={s.code} course={course?.name} to={`/standards/${s.standard_id}`} />
                            <p className="mt-1 line-clamp-3 text-[0.9375rem]">{s.expectation}</p>
                            <p className="mt-1 flex flex-wrap gap-1.5 text-xs">
                              {s.partial ? (
                                <span className="badge border-line bg-paper text-muted">Partially addressed</span>
                              ) : null}
                              {s.also_in.map((name) => (
                                <span key={name} className="badge border-line bg-paper text-muted">
                                  Also in {name}
                                </span>
                              ))}
                            </p>
                          </div>
                          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
                            <div>
                              <dt className="text-xs text-muted">Times assessed</dt>
                              <dd className="tabular-nums">
                                {s.times_assessed === 0 ? "Not assessed in this period" : s.times_assessed}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-xs text-muted">Last assessed</dt>
                              <dd className="tabular-nums">{s.last_assessed ?? "—"}</dd>
                            </div>
                            <div>
                              <dt className="text-xs text-muted">Accuracy</dt>
                              <dd className="tabular-nums">
                                {s.accuracy === null ? "—" : accuracyText(s.correct, s.attempted)}
                                {s.limited_responses ? (
                                  <span className="block text-xs text-muted">Limited response count</span>
                                ) : null}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-xs text-muted">Questions in bank</dt>
                              <dd>
                                {none ? (
                                  "No questions in bank"
                                ) : (
                                  <ul className="text-xs leading-tight tabular-nums">
                                    {STATUS_ORDER.map((k) => (
                                      <li key={k}>
                                        {s.questions[k]} {k}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </dd>
                            </div>
                          </dl>
                          <div className="no-print md:text-right">
                            {s.families.length ? (
                              <Link to={`/generate?${query}`} className="btn btn-sm btn-primary">
                                Generate<span className="sr-only"> for {s.code}</span>
                              </Link>
                            ) : (
                              <Link to={`/standards/${s.standard_id}`} className="btn btn-sm">
                                View<span className="sr-only"> {s.code} (no question generator yet)</span>
                              </Link>
                            )}
                            {s.families.length === 0 ? (
                              <p className="mt-1 text-xs text-muted">No question generator yet</p>
                            ) : null}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </>
      ) : null}
    </>
  );
}
```

The scope line shows only server values (`label`, `start`, `end`, the summary counts). The year `<option>` text is the one place a label is built client-side from a year number the server listed; if it ever differs from the server's `label`, change the options to come from the server (add `labels` to the API) instead of letting two formats exist.

- [ ] **Step 4: Link from the Overview widget**

In `ResultsWidgets.tsx`, in `StandardsCoverageWidget`'s `actions` prop, replace the span with:

```tsx
      actions={
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          Used means a teacher recorded results for it
          <Link to={`/coverage${courseId ? `?course=${courseId}` : ""}`}>Open the coverage grid</Link>
        </span>
      }
```

(`Link` is already imported in that file.)

- [ ] **Step 5: Run the frontend checks**

```bash
cd frontend && npx tsc -b && npm run lint && npm run build
```

Expected: clean; bundle growth under about 10 kB gzip. Fix type errors from the generated schema (for example `params.query` requiring `course_id: number`) rather than casting.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat: coverage page with course and school-year selectors"
```

---

### Task 4: Verify in a browser and record

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Build a scratch stack and seed data**

Throwaway Postgres on 54332 (reuse the one from Task 2), then from `backend/`: `DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_scratch .venv/bin/alembic upgrade head`, `python -m app.cli bootstrap`, `python -m app.cli set-password --username brandon` then `set-role --role admin`, then run uvicorn on 8791 and `API_PROXY_TARGET=http://127.0.0.1:8791 npm run dev` in `frontend/`. Through the UI or API, create a question, an assessment, and administrations on 2026-07-31 and 2026-08-01 with some results (including a 0-of-30 cell and a 5-attempted cell).

- [ ] **Step 2: Check, and record each result honestly (pass, fail, or not verified)**

At 1440, 1024, 768, and 360px with a headless Chromium script (save it under the scratchpad, not the repo):

- `/coverage` renders for each course; no horizontal overflow; no console errors.
- The scope line text equals the API's `scope.label` and dates; changing the year select changes `?year=` and the data; an unknown `?year=abc` shows the error notice, not a blank page.
- A year with no administrations lists every standard as "Not assessed in this period".
- 0 of 30 shows `0%`; blank shows `—`; 5 attempted shows "Limited response count".
- A standard in two bundles shows "Also in …"; Generate opens `/generate?standard=…&bundle=…`; View opens the standard page.
- Keyboard: tab reaches both selects and every action button; the rail link shows the Filled icon on `/coverage`.
- Print (`emulateMedia print`): rail, top bar, selectors, and action buttons hidden; content intact.
- Regular teacher versus the second teacher: the second sees no administration figures but the same question counts.

- [ ] **Step 3: Update `HANDOFF.md`**

Add a "Coverage grid" section under "Results tracking and linked variants": the endpoint, the scope rules, visibility parity, what was and was not verified, and the spec and plan paths. Update "Last updated" and the Next family work / roadmap notes so Workstream B is marked built. Do not claim deployment until it is deployed.

- [ ] **Step 4: Stop the scratch services, remove the throwaway database container you started, and commit**

```bash
git add HANDOFF.md
git commit -m "docs: record the coverage grid in HANDOFF"
```

Merging and deploying follow the working agreement (Claude merges and deploys, with a tagged rollback image; there is no migration, so no database backup is required beyond the usual habit).

---

## Self-review

- **Spec coverage:** scope object and resolved range (Task 1, 2); default year and explicit all time (Task 1, 2 tests); visibility parity (Task 2 parity test); `available_years` (Task 2); groups, `also_in`, `partial`, Other standards, summary counted once (Task 2); five statuses not date-scoped (Task 2); accuracy null versus zero and limited responses (Task 2, 3); status wording and "assessed, not taught" note (Task 3); Generate and View buttons (Task 3); nav, icon, and Overview link (Task 3); 360px, print, keyboard, and error handling (Task 4); no migration; HANDOFF (Task 4).
- **Placeholders:** none.
- **Type consistency:** `Scope` fields feed `CoverageScope` by keyword; `build(...)` fills every `CoverageStandard` field; `useCoveragePage` is named differently from the existing `useCoverage`; tests monkeypatch `app.api.coverage.today`, which the endpoint imports by that name.
