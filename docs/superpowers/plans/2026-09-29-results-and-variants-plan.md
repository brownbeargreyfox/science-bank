# Results Tracking and Linked Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a teacher record that an assessment was given, enter per-section correct/attempted totals per question, review which questions were missed, and save newly generated items from the same family and template as linked variants.

**Architecture:** New tables (`administrations`, `administration_items`, `administration_sections`, `item_results`) plus `questions.variant_of_id`, in migration 0005. Pure rule modules (`services/results.py`, `services/variants.py`) hold accuracy, batch validation, content fingerprints and signed tokens, and are unit-tested without a database. New routers (`administrations`, `results`, `variants`) sit behind the existing auth and ownership policy. Variants reuse the deterministic engine through a shared generation service extracted from `api/generate.py`. The React frontend gets a record-use form, a results grid, a review page with "make practice", and a usage panel.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Postgres 16, pytest, ruff; React 19, TypeScript, react-query, openapi-fetch, oxlint.

**Spec:** `docs/superpowers/specs/2026-09-29-results-and-variants-design.md` (read it first; it defines every rule referenced below).

## Global Constraints

- Migration is `0005_results_and_variants`, `down_revision = "0004_bundle_generation_runs"`, with a working downgrade.
- No student names, IDs or rosters; no `students_tested`; no `notes` columns on administrations or results.
- "Correct" means full credit. Partial credit and multipart scoring are not supported.
- No row in `item_results` means no data; accuracy is `null`/`—`, never 0. 0 of 30 is 0%.
- Accuracy is always computed (`correct / attempted`), never stored.
- "Limited response count" (aggregate attempted `1..9`) is a display hint, never a verdict; no mastery level anywhere.
- Access: administrations, results, usage totals and summary are visible and editable only to the owner and to admin/power (`core/policy.can_modify`). Inaccessible or missing administrations return 404. Question text stays broadly viewable.
- An administration is owned by the user who records it.
- Variants: single-standard engine families only; bundle families, retired families/templates and family-less questions are "unavailable". Preview persists nothing; save accepts signed tokens only and regenerates server-side. Token lifetime 30 min, batch cap 20, lineage ceiling 50, up to 25 attempts.
- Variants must never be described as equivalent in difficulty. UI copy: "New generated item from the same family and template."
- Every new mutating `/api` route must be listed in `POLICY_COVERED` in `backend/tests/test_permissions.py`.
- Deterministic engine only; no LLM.

## Review Focus

Failure modes the spec implies that no single happy-path test would catch. Each has an owning test.

1. A results batch validating against a section that is deleted a moment later, or a snapshot taken while items are reordered — Task 4 (lock tests).
2. Hidden totals leaking through `times_used`, `last_used`, summary rows or usage lists for a user without access — Task 5.
3. Token replay, cross-user use, expiry, and a tampered payload — Tasks 2 and 7.
4. Fingerprint mismatches caused by the stimulus passing through Postgres JSONB (generated vs stored content) — Task 7.
5. 0 of 30 shown as "no data" or no data shown as 0% — Tasks 1, 5 and 9.

## File Structure

Backend (`backend/`):
- Create `app/services/results.py` — pure: `accuracy`, `limited_responses`, `ResultRow`, `plan_result_changes`.
- Create `app/services/variants.py` — pure: `fingerprint`, tokens, constants.
- Create `app/services/administrations.py` — DB helpers: `visible_clauses`, `get_administration`, `MAX_SECTIONS`.
- Create `app/services/generation.py` — the extracted shared generation service.
- Create `app/services/variant_generation.py` — DB-backed variant preview/save logic.
- Create `app/api/administrations.py`, `app/api/results.py`, `app/api/variants.py`.
- Create `alembic/versions/0005_results_and_variants.py`.
- Modify `app/models/bank.py`, `app/models/__init__.py`, `app/schemas/__init__.py`, `app/main.py`, `app/api/assessments.py`, `app/api/generate.py`.
- Create tests: `tests/test_results_logic.py`, `tests/test_variants_logic.py`, `tests/test_migration_0005.py`, `tests/test_administrations_api.py`, `tests/test_results_api.py`, `tests/test_variants_api.py`. Modify `tests/test_permissions.py`.

Frontend (`frontend/src/`):
- Create `lib/results.ts`, `pages/AdministrationPage.tsx`, `pages/ResultsPage.tsx`, `components/RecordUse.tsx`, `components/UsagePanel.tsx`.
- Modify `api/types.ts`, `api/queries.ts` (only if needed), `main.tsx`, `components/Layout.tsx`, `pages/AssessmentBuilder.tsx`, `pages/QuestionDetail.tsx`; regenerate `openapi.json` and `api/schema.d.ts`.

Docs: modify `HANDOFF.md`.

Backend commands run from `backend/` with `.venv/bin/python`. DB-backed tests need a throwaway Postgres (never production) on a port that is not in use, for example:

```bash
docker run -d --rm --name sb-testdb-rv -p 127.0.0.1:54332:5432 \
  -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine
export TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test
```

Check `docker ps` first and do not reuse or stop a container you did not start. Stop yours (`docker stop sb-testdb-rv`) when finished.

---

### Task 1: Results rules (pure)

**Files:**
- Create: `backend/app/services/results.py`
- Test: `backend/tests/test_results_logic.py`

**Interfaces:**
- Produces: `accuracy(correct, attempted) -> float | None`; `limited_responses(attempted) -> bool`; `LIMITED_RESPONSE_THRESHOLD = 10`; `ResultRow(section_id, item_id, correct, attempted)`; `ResultsError(ValueError)`; `plan_result_changes(rows, valid_section_ids, valid_item_ids) -> (upserts, clears)` where upserts are `(section_id, item_id, correct, attempted)` and clears are `(section_id, item_id)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_results_logic.py`:

```python
"""Pure rules for results: accuracy, the limited-response hint, and batch validation."""

import pytest

from app.services.results import ResultRow, ResultsError, accuracy, limited_responses, plan_result_changes


def test_accuracy_is_computed_and_no_data_is_none_not_zero():
    assert accuracy(12, 30) == pytest.approx(0.4)
    assert accuracy(0, 30) == 0.0
    assert accuracy(0, 30) is not None
    assert accuracy(0, 0) is None


@pytest.mark.parametrize(("attempted", "expected"), [(0, False), (1, True), (9, True), (10, False), (30, False)])
def test_limited_responses_flips_between_9_and_10_and_ignores_no_data(attempted, expected):
    assert limited_responses(attempted) is expected


SECTIONS, ITEMS = {1, 2}, {10, 11}


def plan(*rows):
    return plan_result_changes([ResultRow(*r) for r in rows], SECTIONS, ITEMS)


def test_valid_rows_split_into_upserts_and_clears():
    upserts, clears = plan((1, 10, 5, 10), (2, 10, 0, 7), (1, 11, None, None))
    assert upserts == [(1, 10, 5, 10), (2, 10, 0, 7)]
    assert clears == [(1, 11)]


@pytest.mark.parametrize(
    ("row", "fragment"),
    [
        ((3, 10, 1, 2), "section 3"),
        ((1, 99, 1, 2), "question 99"),
        ((1, 10, 1, 0), "at least 1"),
        ((1, 10, 3, 2), "between 0 and attempted"),
        ((1, 10, -1, 2), "between 0 and attempted"),
        ((1, 10, None, 5), "both correct and attempted"),
        ((1, 10, 5, None), "both correct and attempted"),
    ],
)
def test_invalid_rows_are_rejected(row, fragment):
    with pytest.raises(ResultsError, match=fragment):
        plan(row)


def test_duplicate_section_item_rows_are_rejected():
    with pytest.raises(ResultsError, match="duplicate"):
        plan((1, 10, 1, 2), (1, 10, 2, 3))


def test_one_bad_row_rejects_the_whole_batch():
    with pytest.raises(ResultsError):
        plan((1, 10, 5, 10), (1, 11, 9, 2))
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_results_logic.py -q -p no:cacheprovider`
Expected: ERROR — `ModuleNotFoundError: No module named 'app.services.results'`.

- [ ] **Step 3: Implement**

Create `backend/app/services/results.py`:

```python
"""Pure arithmetic and validation for section results. No database access."""

from dataclasses import dataclass

LIMITED_RESPONSE_THRESHOLD = 10


def accuracy(correct: int, attempted: int) -> float | None:
    """correct / attempted, or None when there is no data. No data is never reported as 0."""
    return None if attempted <= 0 else correct / attempted


def limited_responses(attempted: int) -> bool:
    """Display hint for small totals. No data (0 attempted) is 'no data', not 'limited'."""
    return 0 < attempted < LIMITED_RESPONSE_THRESHOLD


@dataclass(frozen=True)
class ResultRow:
    section_id: int
    item_id: int
    correct: int | None
    attempted: int | None


class ResultsError(ValueError):
    """The message is safe to show to the teacher."""


def plan_result_changes(
    rows: list[ResultRow], valid_section_ids: set[int], valid_item_ids: set[int]
) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int]]]:
    """Validate a whole batch before anything is written.

    Returns (upserts, clears). Upserts are (section_id, item_id, correct, attempted); clears are
    (section_id, item_id). Raises ResultsError on the first problem; the caller writes nothing.
    """
    seen: set[tuple[int, int]] = set()
    upserts: list[tuple[int, int, int, int]] = []
    clears: list[tuple[int, int]] = []
    for number, row in enumerate(rows, start=1):
        where = f"Row {number}"
        if row.section_id not in valid_section_ids:
            raise ResultsError(f"{where}: section {row.section_id} does not belong to this administration")
        if row.item_id not in valid_item_ids:
            raise ResultsError(f"{where}: question {row.item_id} does not belong to this administration")
        key = (row.section_id, row.item_id)
        if key in seen:
            raise ResultsError(f"{where}: duplicate entry for the same section and question")
        seen.add(key)
        if row.correct is None and row.attempted is None:
            clears.append(key)
            continue
        if row.correct is None or row.attempted is None:
            raise ResultsError(f"{where}: enter both correct and attempted, or clear both")
        if row.attempted < 1:
            raise ResultsError(f"{where}: attempted must be at least 1")
        if not 0 <= row.correct <= row.attempted:
            raise ResultsError(f"{where}: correct must be between 0 and attempted")
        upserts.append((row.section_id, row.item_id, row.correct, row.attempted))
    return upserts, clears
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_results_logic.py -q -p no:cacheprovider`
Expected: `16 passed`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check app/services/results.py tests/test_results_logic.py
.venv/bin/ruff format app/services/results.py tests/test_results_logic.py
git add app/services/results.py tests/test_results_logic.py
git commit -m "feat: add pure results accuracy and batch validation rules"
```

---

### Task 2: Variant fingerprints and signed tokens (pure)

**Files:**
- Create: `backend/app/services/variants.py`
- Test: `backend/tests/test_variants_logic.py`

**Interfaces:**
- Produces: constants `TOKEN_TTL_SECONDS=1800`, `MAX_BATCH=20`, `LINEAGE_CEILING=50`, `MAX_ATTEMPTS=25`; `fingerprint(question_type, stem, choices, answer, stimulus) -> str`; `candidate_seed(nonce, parent_id, attempt) -> str`; `issue_token(*, user_id, parent_id, parent_version_id, seed, family_key, family_version, now=None) -> str`; `verify_token(token, *, user_id, now=None) -> CandidateToken` (fields `token_id, expires_at, user_id, parent_id, parent_version_id, seed, family_key, family_version`); `TokenError(ValueError)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_variants_logic.py`:

```python
"""Pure rules for variants: content fingerprints and signed preview tokens."""

import pytest

from app.services import variants as v

CHOICES = [
    {"label": "A", "text": "Logistic growth", "correct": True, "rationale": "r1"},
    {"label": "B", "text": "Exponential growth", "correct": False, "rationale": "r2"},
    {"label": "C", "text": "Linear growth", "correct": False, "rationale": "r3"},
]
STIM = {"kind": "survey", "title": "Deer", "tables": [{"rows": [{"year": 1, "n": 10}]}]}


def fp(**over):
    args = {
        "question_type": "multiple_choice",
        "stem": "Which model fits?",
        "choices": CHOICES,
        "answer": "A. Logistic growth",
        "stimulus": STIM,
    }
    args.update(over)
    return v.fingerprint(**args)


def test_reordering_and_relabelling_choices_does_not_change_the_fingerprint():
    shuffled = [
        {"label": "A", "text": "Linear growth", "correct": False, "rationale": "x"},
        {"label": "B", "text": "Logistic growth", "correct": True, "rationale": "y"},
        {"label": "C", "text": "Exponential growth", "correct": False, "rationale": "z"},
    ]
    assert fp(choices=shuffled, answer="B. Logistic growth") == fp()


def test_whitespace_in_the_stem_is_ignored():
    assert fp(stem="  Which   model fits? ") == fp()


@pytest.mark.parametrize(
    "change",
    [
        {"stem": "Which model best fits?"},
        {"question_type": "constructed_response", "choices": [], "answer": "Logistic growth"},
        {"stimulus": {**STIM, "title": "Elk"}},
        {"stimulus": None},
        {"choices": [{**CHOICES[0], "correct": False}, {**CHOICES[1], "correct": True}, CHOICES[2]]},
    ],
)
def test_any_content_change_changes_the_fingerprint(change):
    assert fp(**change) != fp()


def test_different_scenario_with_the_same_answer_is_a_different_fingerprint():
    assert fp(stem="Which model fits the elk data?", stimulus={**STIM, "title": "Elk"}) != fp()


def token(**over):
    args = {
        "user_id": 7,
        "parent_id": 3,
        "parent_version_id": 9,
        "seed": "v-abc-3-0",
        "family_key": "population-carrying-capacity",
        "family_version": "1.0.0",
        "now": 1_000_000,
    }
    args.update(over)
    return v.issue_token(**args)


def test_token_round_trips_and_carries_its_fields():
    t = v.verify_token(token(), user_id=7, now=1_000_100)
    assert (t.parent_id, t.parent_version_id, t.seed, t.family_version) == (3, 9, "v-abc-3-0", "1.0.0")
    assert t.expires_at == 1_000_000 + v.TOKEN_TTL_SECONDS


def test_tokens_have_unique_ids():
    assert (
        v.verify_token(token(), user_id=7, now=1_000_001).token_id
        != v.verify_token(token(), user_id=7, now=1_000_001).token_id
    )


def test_expired_token_is_rejected():
    with pytest.raises(v.TokenError, match="expired"):
        v.verify_token(token(), user_id=7, now=1_000_000 + v.TOKEN_TTL_SECONDS + 1)


def test_another_users_token_is_rejected():
    with pytest.raises(v.TokenError, match="different user"):
        v.verify_token(token(), user_id=8, now=1_000_001)


def test_tampered_payload_or_signature_is_rejected():
    raw, sig = token().split(".")
    flipped = raw[:-1] + ("A" if raw[-1] != "A" else "B")
    with pytest.raises(v.TokenError):
        v.verify_token(f"{flipped}.{sig}", user_id=7, now=1_000_001)
    with pytest.raises(v.TokenError):
        v.verify_token(f"{raw}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}", user_id=7, now=1_000_001)


@pytest.mark.parametrize("bad", ["", "abc", "a.b.c", "."])
def test_malformed_tokens_are_rejected(bad):
    with pytest.raises(v.TokenError):
        v.verify_token(bad, user_id=7, now=1_000_001)


def test_candidate_seed_fits_the_generate_seed_pattern():
    import re

    seed = v.candidate_seed("0123456789abcdef", 123456, 24)
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,64}", seed)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_variants_logic.py -q -p no:cacheprovider`
Expected: ERROR — `ImportError: cannot import name 'variants' from 'app.services'`.

- [ ] **Step 3: Implement**

Create `backend/app/services/variants.py`:

```python
"""Variant content fingerprints and signed preview tokens. Pure functions; no database access."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

TOKEN_TTL_SECONDS = 30 * 60
MAX_BATCH = 20
LINEAGE_CEILING = 50
MAX_ATTEMPTS = 25

_SPACE = re.compile(r"\s+")


def _norm(text: str | None) -> str:
    return _SPACE.sub(" ", text or "").strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(
    question_type: str, stem: str, choices: list[dict], answer: str, stimulus: dict[str, Any] | None
) -> str:
    """Identity of a question's content for variant distinctness.

    Answer-choice labels and order are ignored, so a reshuffle cannot pass as a new question. The
    correct answer of a multiple-choice item is taken from its choices, never from the labelled answer
    string. This proves the output differs structurally; it says nothing about difficulty.
    """
    if question_type == "multiple_choice":
        pairs = sorted([_norm(c["text"]), bool(c["correct"])] for c in choices)
        answer_text = next((_norm(c["text"]) for c in choices if c["correct"]), "")
    else:
        pairs = []
        answer_text = _norm(answer)
    payload = {"t": question_type, "s": _norm(stem), "c": pairs, "a": answer_text, "x": stimulus}
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def candidate_seed(nonce: str, parent_id: int, attempt: int) -> str:
    return f"v-{nonce}-{parent_id}-{attempt}"


class TokenError(ValueError):
    """The message is safe to show to the teacher."""


@dataclass(frozen=True)
class CandidateToken:
    token_id: str
    expires_at: int
    user_id: int
    parent_id: int
    parent_version_id: int
    seed: str
    family_key: str
    family_version: str


def _key() -> bytes:
    from app.core.config import get_settings

    return hashlib.sha256(("variant-token:" + get_settings().jwt_secret).encode()).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(raw: str) -> str:
    return _b64(hmac.new(_key(), raw.encode(), hashlib.sha256).digest())


def issue_token(
    *,
    user_id: int,
    parent_id: int,
    parent_version_id: int,
    seed: str,
    family_key: str,
    family_version: str,
    now: int | None = None,
) -> str:
    issued = int(time.time()) if now is None else now
    body = {
        "tid": secrets.token_hex(8),
        "exp": issued + TOKEN_TTL_SECONDS,
        "uid": user_id,
        "pid": parent_id,
        "pvid": parent_version_id,
        "seed": seed,
        "fk": family_key,
        "fv": family_version,
    }
    raw = _b64(_canonical(body).encode())
    return f"{raw}.{_sign(raw)}"


def verify_token(token: str, *, user_id: int, now: int | None = None) -> CandidateToken:
    parts = token.split(".")
    if len(parts) != 2:
        raise TokenError("Malformed candidate token")
    raw, sig = parts
    if not hmac.compare_digest(sig, _sign(raw)):
        raise TokenError("Invalid candidate token")
    try:
        body = json.loads(_unb64(raw))
        parsed = CandidateToken(
            token_id=body["tid"],
            expires_at=int(body["exp"]),
            user_id=int(body["uid"]),
            parent_id=int(body["pid"]),
            parent_version_id=int(body["pvid"]),
            seed=body["seed"],
            family_key=body["fk"],
            family_version=body["fv"],
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenError("Malformed candidate token") from exc
    current = int(time.time()) if now is None else now
    if parsed.expires_at < current:
        raise TokenError("This candidate has expired; preview again")
    if parsed.user_id != user_id:
        raise TokenError("This candidate was created for a different user")
    return parsed
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_variants_logic.py -q -p no:cacheprovider`
Expected: `18 passed`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check app/services/variants.py tests/test_variants_logic.py
.venv/bin/ruff format app/services/variants.py tests/test_variants_logic.py
git add app/services/variants.py tests/test_variants_logic.py
git commit -m "feat: add variant content fingerprints and signed candidate tokens"
```

### Task 3: Models and migration 0005

**Files:**
- Modify: `backend/app/models/bank.py`, `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0005_results_and_variants.py`
- Test: `backend/tests/test_migration_0005.py`

**Interfaces:**
- Produces ORM classes `Administration` (fields `id, assessment_id, label, administered_on, owner_id, deleted_at, created_at, updated_at`; relationships `assessment, owner, sections, items`), `AdministrationItem` (`id, administration_id, source_assessment_item_id, question_id, question_version_id, position`; relationships `question, question_version`), `AdministrationSection` (`id, administration_id, name`), `ItemResult` (`id, section_id, administration_item_id, correct, attempted`), and `Question.variant_of_id`. All exported from `app.models`.

- [ ] **Step 1: Write the failing migration test**

Create `backend/tests/test_migration_0005.py`:

```python
"""0005 adds the results tables and questions.variant_of_id, and downgrades cleanly."""

from sqlalchemy import create_engine, inspect

from tests.conftest import BACKEND
from tests.test_migration_0003 import scratch_url  # noqa: F401  (pytest fixture)

NEW_TABLES = {"administrations", "administration_items", "administration_sections", "item_results"}


def _alembic(url: str, target: str, monkeypatch, *, down: bool = False) -> None:
    from alembic import command
    from alembic.config import Config
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        (command.downgrade if down else command.upgrade)(cfg, target)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_upgrade_adds_tables_and_column_and_downgrade_removes_them(scratch_url, monkeypatch):  # noqa: F811  (fixture imported above)
    _alembic(scratch_url, "0004_bundle_generation_runs", monkeypatch)
    eng = create_engine(scratch_url)
    assert not NEW_TABLES & set(inspect(eng).get_table_names())
    assert "variant_of_id" not in {c["name"] for c in inspect(eng).get_columns("questions")}

    _alembic(scratch_url, "head", monkeypatch)
    insp = inspect(eng)
    assert NEW_TABLES <= set(insp.get_table_names())
    assert "variant_of_id" in {c["name"] for c in insp.get_columns("questions")}
    indexed = {tuple(i["column_names"]) for i in insp.get_indexes("administrations")}
    assert ("owner_id", "administered_on") in indexed
    assert ("variant_of_id",) in {tuple(i["column_names"]) for i in insp.get_indexes("questions")}
    result_checks = {c["name"] for c in insp.get_check_constraints("item_results")}
    assert {"ck_item_results_attempted_positive", "ck_item_results_correct_range"} <= result_checks

    _alembic(scratch_url, "0004_bundle_generation_runs", monkeypatch, down=True)
    insp = inspect(eng)
    assert not NEW_TABLES & set(insp.get_table_names())
    assert "variant_of_id" not in {c["name"] for c in insp.get_columns("questions")}

    _alembic(scratch_url, "head", monkeypatch)  # upgrade again after a downgrade
    assert NEW_TABLES <= set(inspect(eng).get_table_names())
    eng.dispose()
```

- [ ] **Step 2: Run to verify failure** (needs `TEST_DATABASE_URL`)

Run: `.venv/bin/python -m pytest tests/test_migration_0005.py -q -p no:cacheprovider`
Expected: FAIL — the new tables are absent after upgrading to head.

- [ ] **Step 3: Add the models**

In `backend/app/models/bank.py`: change `from datetime import datetime` to `from datetime import date, datetime`, and add `Date` to the `sqlalchemy` import list. In `class Question`, directly after the `owner_id` column, add:

```python
    variant_of_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
```

Append after `class AssessmentItem` (before `class AuditEvent`):

```python
class Administration(Base):
    """An assessment actually given. Its items are a snapshot, so later assessment edits never change it."""

    __tablename__ = "administrations"
    __table_args__ = (
        Index("ix_administrations_owner_date", "owner_id", "administered_on"),
        Index("ix_administrations_assessment", "assessment_id", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="RESTRICT"))
    label: Mapped[str] = mapped_column(Text)
    administered_on: Mapped[date] = mapped_column(Date)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assessment: Mapped[Assessment] = relationship()
    owner: Mapped[User] = relationship()
    sections: Mapped[list["AdministrationSection"]] = relationship(
        order_by="AdministrationSection.id", cascade="all, delete-orphan"
    )
    items: Mapped[list["AdministrationItem"]] = relationship(
        order_by="AdministrationItem.position", cascade="all, delete-orphan"
    )


class AdministrationItem(Base):
    """One assessment item as it stood when the use was recorded: exact question, version and position."""

    __tablename__ = "administration_items"
    __table_args__ = (
        UniqueConstraint("administration_id", "position", name="uq_administration_items_position"),
        Index("ix_administration_items_question", "question_id"),
        Index("ix_administration_items_version", "question_version_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    administration_id: Mapped[int] = mapped_column(ForeignKey("administrations.id", ondelete="CASCADE"))
    # Deliberately not a foreign key: removing the item from the assessment later must not erase this record.
    source_assessment_item_id: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    question_version_id: Mapped[int] = mapped_column(ForeignKey("question_versions.id"))
    position: Mapped[int] = mapped_column(Integer)

    question: Mapped[Question] = relationship()
    question_version: Mapped[QuestionVersion] = relationship()


class AdministrationSection(Base):
    """A group tested, such as 'Period 2'. Names are unique within an administration, ignoring case."""

    __tablename__ = "administration_sections"
    # The functional unique index on (administration_id, lower(name)) also serves lookups by administration_id.
    __table_args__ = (Index("uq_administration_sections_name", "administration_id", text("lower(name)"), unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    administration_id: Mapped[int] = mapped_column(ForeignKey("administrations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)


class ItemResult(Base):
    """Correct/attempted totals for one section on one item. No row means no data, never zero."""

    __tablename__ = "item_results"
    __table_args__ = (
        UniqueConstraint("section_id", "administration_item_id", name="uq_item_results_section_item"),
        Index("ix_item_results_item", "administration_item_id"),
        CheckConstraint("attempted >= 1", name="ck_item_results_attempted_positive"),
        CheckConstraint("correct >= 0 AND correct <= attempted", name="ck_item_results_correct_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("administration_sections.id", ondelete="CASCADE"))
    administration_item_id: Mapped[int] = mapped_column(ForeignKey("administration_items.id", ondelete="CASCADE"))
    correct: Mapped[int] = mapped_column(Integer)
    attempted: Mapped[int] = mapped_column(Integer)
```

In `backend/app/models/__init__.py` add `Administration, AdministrationItem, AdministrationSection, ItemResult` to the `from app.models.bank import (...)` list and to `__all__` (keep alphabetical order).

- [ ] **Step 4: Write the migration**

Create `backend/alembic/versions/0005_results_and_variants.py`:

```python
"""Administrations, per-section item results, and question variant links."""

import sqlalchemy as sa

from alembic import op

revision = "0005_results_and_variants"
down_revision = "0004_bundle_generation_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "administrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("administered_on", sa.Date(), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_administrations_owner_date", "administrations", ["owner_id", "administered_on"])
    op.create_index("ix_administrations_assessment", "administrations", ["assessment_id", "deleted_at"])

    op.create_table(
        "administration_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "administration_id", sa.Integer(), sa.ForeignKey("administrations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_assessment_item_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("question_version_id", sa.Integer(), sa.ForeignKey("question_versions.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("administration_id", "position", name="uq_administration_items_position"),
    )
    op.create_index("ix_administration_items_question", "administration_items", ["question_id"])
    op.create_index("ix_administration_items_version", "administration_items", ["question_version_id"])

    op.create_table(
        "administration_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "administration_id", sa.Integer(), sa.ForeignKey("administrations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.create_index(
        "uq_administration_sections_name",
        "administration_sections",
        ["administration_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "item_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "section_id", sa.Integer(), sa.ForeignKey("administration_sections.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "administration_item_id",
            sa.Integer(),
            sa.ForeignKey("administration_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("attempted", sa.Integer(), nullable=False),
        sa.UniqueConstraint("section_id", "administration_item_id", name="uq_item_results_section_item"),
        sa.CheckConstraint("attempted >= 1", name="ck_item_results_attempted_positive"),
        sa.CheckConstraint("correct >= 0 AND correct <= attempted", name="ck_item_results_correct_range"),
    )
    op.create_index("ix_item_results_item", "item_results", ["administration_item_id"])

    op.add_column("questions", sa.Column("variant_of_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_questions_variant_of_id", "questions", "questions", ["variant_of_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_questions_variant_of_id", "questions", ["variant_of_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_variant_of_id", table_name="questions")
    op.drop_constraint("fk_questions_variant_of_id", "questions", type_="foreignkey")
    op.drop_column("questions", "variant_of_id")
    op.drop_index("ix_item_results_item", table_name="item_results")
    op.drop_table("item_results")
    op.drop_index("uq_administration_sections_name", table_name="administration_sections")
    op.drop_table("administration_sections")
    op.drop_index("ix_administration_items_version", table_name="administration_items")
    op.drop_index("ix_administration_items_question", table_name="administration_items")
    op.drop_table("administration_items")
    op.drop_index("ix_administrations_assessment", table_name="administrations")
    op.drop_index("ix_administrations_owner_date", table_name="administrations")
    op.drop_table("administrations")
```

- [ ] **Step 5: Run to verify pass, then the whole suite for regressions**

Run: `.venv/bin/python -m pytest tests/test_migration_0005.py -q -p no:cacheprovider`
Expected: `1 passed`.
Run: `.venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: all previously passing tests still pass (the test DB is created from migrations, so `0005` also runs there).

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check app tests
.venv/bin/ruff format app/models/bank.py alembic/versions/0005_results_and_variants.py tests/test_migration_0005.py
git add app/models alembic/versions/0005_results_and_variants.py tests/test_migration_0005.py
git commit -m "feat: add administrations, item results, and question variant link (migration 0005)"
```

---

### Task 4: Administrations API, assessment locking, and access rules

**Files:**
- Modify: `backend/app/schemas/__init__.py`, `backend/app/api/assessments.py`, `backend/app/main.py`, `backend/tests/test_permissions.py`
- Create: `backend/app/services/administrations.py`, `backend/app/api/administrations.py`
- Test: `backend/tests/test_administrations_api.py`

**Interfaces:**
- Consumes: `plan_result_changes`, `ResultRow`, `ResultsError`, `accuracy`, `limited_responses` (Task 1); models (Task 3); `can_modify`, `is_moderator`, `record_audit`, `not_found`, `get_actor`.
- Produces:
  - `visible_clauses(user) -> list` (SQLAlchemy where-clauses: non-deleted, plus owner match for non-moderators) and `get_administration(db, user, administration_id, *, lock=False, include_deleted=False)` (404 `Administration not found` when missing or not accessible), `MAX_SECTIONS = 12`.
  - Routes: `POST/GET /api/assessments/{assessment_id}/administrations`; `GET/PATCH/DELETE /api/administrations/{administration_id}`; `POST /api/administrations/{administration_id}/restore`; `POST /api/administrations/{administration_id}/sections`; `PATCH/DELETE /api/administrations/{administration_id}/sections/{section_id}`; `PUT /api/administrations/{administration_id}/results`.
  - Schemas: `AdministrationCreate`, `AdministrationUpdate`, `SectionName`, `ResultRowIn`, `ResultsBatch`, `SectionOut`, `ResultOut`, `AccuracyOut`, `AdministrationItemOut`, `AdministrationSummary`, `AdministrationDetail`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_administrations_api.py`:

```python
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
    assert out["results"] == [{"section_id": d["sections"][0]["id"], "item_id": d["items"][0]["id"], "correct": 8, "attempted": 10}]


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
```

Also add the new routes to `POLICY_COVERED` in `backend/tests/test_permissions.py` (inside the dict, after the assessments entries):

```python
    ("POST", "/api/assessments/{assessment_id}/administrations"): "creates; owner = caller",
    ("PATCH", "/api/administrations/{administration_id}"): "test_administration_mutation_matrix",
    ("DELETE", "/api/administrations/{administration_id}"): "test_administration_mutation_matrix",
    ("POST", "/api/administrations/{administration_id}/restore"): "test_soft_delete_hides_and_restore_returns",
    ("POST", "/api/administrations/{administration_id}/sections"): "test_administration_mutation_matrix",
    ("PATCH", "/api/administrations/{administration_id}/sections/{section_id}"): "test_sections_can_be_added_renamed_and_removed_with_their_results",
    ("DELETE", "/api/administrations/{administration_id}/sections/{section_id}"): "test_sections_can_be_added_renamed_and_removed_with_their_results",
    ("PUT", "/api/administrations/{administration_id}/results"): "test_administration_mutation_matrix",
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_administrations_api.py -q -p no:cacheprovider -x`
Expected: FAIL — `404`/`405` on the first `POST .../administrations`.

- [ ] **Step 3: Add the schemas**

In `backend/app/schemas/__init__.py`, ensure the imports include `date` (from `datetime`), `field_validator` and `StrictInt` (from `pydantic`). Append at the end of the file:

```python
# ---- results and variants ----------------------------------------------------------------------


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 60:
        raise ValueError("Section names must be 1-60 characters")
    return cleaned


class AdministrationCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    administered_on: date
    sections: list[str] = Field(min_length=1, max_length=12)

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Give this use a label")
        return cleaned

    @field_validator("sections")
    @classmethod
    def _sections(cls, value: list[str]) -> list[str]:
        cleaned = [_clean_name(v) for v in value]
        if len({v.lower() for v in cleaned}) != len(cleaned):
            raise ValueError("Section names must be different from each other")
        return cleaned


class AdministrationUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    administered_on: date | None = None

    @field_validator("label")
    @classmethod
    def _label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Give this use a label")
        return cleaned


class SectionName(BaseModel):
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value)


class ResultRowIn(BaseModel):
    section_id: int
    item_id: int
    correct: StrictInt | None = None
    attempted: StrictInt | None = None


class ResultsBatch(BaseModel):
    rows: list[ResultRowIn] = Field(min_length=1, max_length=500)


class SectionOut(BaseModel):
    id: int
    name: str


class ResultOut(BaseModel):
    section_id: int
    item_id: int
    correct: int
    attempted: int


class AccuracyOut(BaseModel):
    correct: int
    attempted: int
    accuracy: float | None
    limited_responses: bool


class AdministrationItemOut(BaseModel):
    id: int
    position: int
    question_id: int
    question_version_id: int
    pinned_version_no: int
    standard_code: str
    course_name: str
    dok: int
    question_type: QuestionType
    stem: str
    stimulus_title: str | None
    totals: AccuracyOut


class AdministrationSummary(BaseModel):
    id: int
    assessment_id: int
    assessment_title: str
    label: str
    administered_on: date
    owner: OwnerOut
    section_count: int
    item_count: int
    items_with_data: int
    created_at: datetime
    deleted_at: datetime | None


class AdministrationDetail(AdministrationSummary):
    sections: list[SectionOut]
    items: list[AdministrationItemOut]
    results: list[ResultOut]
```

- [ ] **Step 4: Add the shared helpers**

Create `backend/app/services/administrations.py`:

```python
"""Database helpers shared by the administration, results, and usage routes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policy import can_modify, is_moderator
from app.models import Administration, User
from app.services.bank import not_found

MAX_SECTIONS = 12


def visible_clauses(user: User) -> list:
    """Where-clauses for the administrations a user may see: not deleted, and their own unless a moderator."""
    clauses = [Administration.deleted_at.is_(None)]
    if not is_moderator(user):
        clauses.append(Administration.owner_id == user.id)
    return clauses


def get_administration(
    db: Session, user: User, administration_id: int, *, lock: bool = False, include_deleted: bool = False
) -> Administration:
    """Load an administration the user may access, or raise 404 so colleagues' records cannot be enumerated."""
    stmt = select(Administration).where(Administration.id == administration_id)
    if not include_deleted:
        stmt = stmt.where(Administration.deleted_at.is_(None))
    if lock:
        stmt = stmt.with_for_update()
    admin = db.scalar(stmt)
    if admin is None or not can_modify(user, admin.owner_id):
        raise not_found("Administration")
    return admin
```

- [ ] **Step 5: Lock the assessment row in the existing mutators**

In `backend/app/api/assessments.py` make three small edits.

1. Change the `_load` signature line to add a `lock` flag:

```python
def _load(db: Session, assessment_id: int, *, include_deleted: bool = False, lock: bool = False) -> Assessment:
```

2. In `_load`, directly above the line `a = db.scalar(stmt)`, insert:

```python
    if lock:
        stmt = stmt.with_for_update(of=Assessment)
```

3. Replace the body of `_load_for_change` so it takes the lock:

```python
def _load_for_change(db: Session, assessment_id: int, actor: Actor) -> Assessment:
    a = _load(db, assessment_id, lock=True)
    require_modify(actor.user, a.owner_id, "assessment")
    return a
```

(`selectinload` options issue separate SELECTs, so `FOR UPDATE OF assessments` locks only the assessment row.)

- [ ] **Step 6: Write the router**

Create `backend/app/api/administrations.py`:

```python
"""Administrations: recording that an assessment was given, and per-section results."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import Actor, get_actor, get_current_user
from app.models import (
    Administration,
    AdministrationItem,
    AdministrationSection,
    Assessment,
    AssessmentItem,
    ItemResult,
    Question,
    Standard,
    User,
)
from app.schemas import (
    AccuracyOut,
    AdministrationCreate,
    AdministrationDetail,
    AdministrationItemOut,
    AdministrationSummary,
    AdministrationUpdate,
    OwnerOut,
    ResultOut,
    ResultsBatch,
    SectionName,
    SectionOut,
)
from app.services.administrations import MAX_SECTIONS, get_administration, visible_clauses
from app.services.audit import record_audit
from app.services.bank import not_found
from app.services.results import ResultRow, ResultsError, accuracy, limited_responses, plan_result_changes

router = APIRouter(tags=["administrations"])


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, message)


def _accuracy_out(correct: int, attempted: int) -> AccuracyOut:
    return AccuracyOut(
        correct=correct,
        attempted=attempted,
        accuracy=accuracy(correct, attempted),
        limited_responses=limited_responses(attempted),
    )


def _summaries(db: Session, admins: list[Administration]) -> list[AdministrationSummary]:
    ids = [a.id for a in admins]
    if not ids:
        return []
    sections = dict(
        db.execute(
            select(AdministrationSection.administration_id, func.count())
            .where(AdministrationSection.administration_id.in_(ids))
            .group_by(AdministrationSection.administration_id)
        ).all()
    )
    items = dict(
        db.execute(
            select(AdministrationItem.administration_id, func.count())
            .where(AdministrationItem.administration_id.in_(ids))
            .group_by(AdministrationItem.administration_id)
        ).all()
    )
    with_data = dict(
        db.execute(
            select(AdministrationItem.administration_id, func.count(func.distinct(ItemResult.administration_item_id)))
            .join(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
            .where(AdministrationItem.administration_id.in_(ids))
            .group_by(AdministrationItem.administration_id)
        ).all()
    )
    return [
        AdministrationSummary(
            id=a.id,
            assessment_id=a.assessment_id,
            assessment_title=a.assessment.title,
            label=a.label,
            administered_on=a.administered_on,
            owner=OwnerOut.model_validate(a.owner),
            section_count=sections.get(a.id, 0),
            item_count=items.get(a.id, 0),
            items_with_data=with_data.get(a.id, 0),
            created_at=a.created_at,
            deleted_at=a.deleted_at,
        )
        for a in admins
    ]


def _detail(db: Session, admin: Administration) -> AdministrationDetail:
    db.refresh(admin)
    sections = db.scalars(
        select(AdministrationSection)
        .where(AdministrationSection.administration_id == admin.id)
        .order_by(AdministrationSection.id)
    ).all()
    items = db.scalars(
        select(AdministrationItem)
        .where(AdministrationItem.administration_id == admin.id)
        .order_by(AdministrationItem.position)
        .options(
            selectinload(AdministrationItem.question_version),
            selectinload(AdministrationItem.question).options(
                selectinload(Question.standard).selectinload(Standard.course),
                selectinload(Question.stimulus),
            ),
        )
    ).all()
    results = (
        db.scalars(select(ItemResult).where(ItemResult.administration_item_id.in_([i.id for i in items]))).all()
        if items
        else []
    )
    totals: dict[int, list[int]] = {}
    for r in results:
        t = totals.setdefault(r.administration_item_id, [0, 0])
        t[0] += r.correct
        t[1] += r.attempted
    summary = _summaries(db, [admin])[0]
    return AdministrationDetail(
        **summary.model_dump(),
        sections=[SectionOut(id=s.id, name=s.name) for s in sections],
        items=[
            AdministrationItemOut(
                id=i.id,
                position=i.position,
                question_id=i.question_id,
                question_version_id=i.question_version_id,
                pinned_version_no=i.question_version.version_no,
                standard_code=i.question.standard.code,
                course_name=i.question.standard.course.name,
                dok=i.question_version.dok,
                question_type=i.question_version.question_type,
                stem=i.question_version.stem,
                stimulus_title=i.question.stimulus.title if i.question.stimulus else None,
                totals=_accuracy_out(*totals.get(i.id, [0, 0])),
            )
            for i in items
        ],
        results=[
            ResultOut(section_id=r.section_id, item_id=r.administration_item_id, correct=r.correct, attempted=r.attempted)
            for r in sorted(results, key=lambda r: (r.administration_item_id, r.section_id))
        ],
    )


@router.post(
    "/assessments/{assessment_id}/administrations", response_model=AdministrationDetail, status_code=status.HTTP_201_CREATED
)
def record_use(
    assessment_id: int, body: AdministrationCreate, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    """Freeze the assessment's current items and record that it was given. Owned by the caller."""
    assessment = db.scalar(
        select(Assessment).where(Assessment.id == assessment_id, Assessment.deleted_at.is_(None)).with_for_update()
    )
    if assessment is None:
        raise not_found("Assessment")
    # One statement, taken after the row lock: the snapshot is a single coherent assessment state.
    items = db.scalars(
        select(AssessmentItem).where(AssessmentItem.assessment_id == assessment_id).order_by(AssessmentItem.position)
    ).all()
    if not items:
        raise _unprocessable("Add at least one question to the assessment before recording a use")
    admin = Administration(
        assessment_id=assessment.id, label=body.label, administered_on=body.administered_on, owner_id=actor.user.id
    )
    admin.sections = [AdministrationSection(name=name) for name in body.sections]
    admin.items = [
        AdministrationItem(
            source_assessment_item_id=it.id,
            question_id=it.question_id,
            question_version_id=it.question_version_id,
            position=it.position,
        )
        for it in items
    ]
    db.add(admin)
    db.flush()
    record_audit(
        db,
        actor,
        "administration.create",
        target_type="administration",
        target_id=admin.id,
        detail={"assessment_id": assessment.id, "sections": len(body.sections), "items": len(items)},
    )
    db.commit()
    return _detail(db, admin)


@router.get("/assessments/{assessment_id}/administrations", response_model=list[AdministrationSummary])
def list_administrations(
    assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[AdministrationSummary]:
    if db.scalar(select(Assessment.id).where(Assessment.id == assessment_id, Assessment.deleted_at.is_(None))) is None:
        raise not_found("Assessment")
    admins = db.scalars(
        select(Administration)
        .where(Administration.assessment_id == assessment_id, *visible_clauses(user))
        .options(selectinload(Administration.assessment), selectinload(Administration.owner))
        .order_by(Administration.administered_on.desc(), Administration.id.desc())
    ).all()
    return _summaries(db, list(admins))


@router.get("/administrations/{administration_id}", response_model=AdministrationDetail)
def get_detail(
    administration_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AdministrationDetail:
    return _detail(db, get_administration(db, user, administration_id))


@router.patch("/administrations/{administration_id}", response_model=AdministrationDetail)
def update_administration(
    administration_id: int,
    body: AdministrationUpdate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    fields = body.model_fields_set
    if "label" in fields and body.label is not None:
        admin.label = body.label
    if "administered_on" in fields and body.administered_on is not None:
        admin.administered_on = body.administered_on
    record_audit(
        db,
        actor,
        "administration.update",
        target_type="administration",
        target_id=admin.id,
        detail={"fields": sorted(fields)},
    )
    db.commit()
    return _detail(db, admin)


@router.delete("/administrations/{administration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_administration(
    administration_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> Response:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    admin.deleted_at = datetime.now(UTC)
    record_audit(db, actor, "administration.delete", target_type="administration", target_id=admin.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/administrations/{administration_id}/restore", response_model=AdministrationDetail)
def restore_administration(
    administration_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True, include_deleted=True)
    admin.deleted_at = None
    record_audit(db, actor, "administration.restore", target_type="administration", target_id=admin.id)
    db.commit()
    return _detail(db, admin)


def _section(admin: Administration, section_id: int) -> AdministrationSection:
    section = next((s for s in admin.sections if s.id == section_id), None)
    if section is None:
        raise not_found("Section")
    return section


@router.post(
    "/administrations/{administration_id}/sections",
    response_model=AdministrationDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_section(
    administration_id: int, body: SectionName, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    if len(admin.sections) >= MAX_SECTIONS:
        raise _unprocessable(f"An administration can have at most {MAX_SECTIONS} sections")
    if body.name.lower() in {s.name.lower() for s in admin.sections}:
        raise _unprocessable("There is already a section with that name")
    admin.sections.append(AdministrationSection(name=body.name))
    record_audit(db, actor, "administration.sections", target_type="administration", target_id=admin.id, detail={"op": "add"})
    db.commit()
    return _detail(db, admin)


@router.patch("/administrations/{administration_id}/sections/{section_id}", response_model=AdministrationDetail)
def rename_section(
    administration_id: int,
    section_id: int,
    body: SectionName,
    db: Session = Depends(get_db),
    actor: Actor = Depends(get_actor),
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    section = _section(admin, section_id)
    if body.name.lower() in {s.name.lower() for s in admin.sections if s.id != section.id}:
        raise _unprocessable("There is already a section with that name")
    section.name = body.name
    record_audit(db, actor, "administration.sections", target_type="administration", target_id=admin.id, detail={"op": "rename"})
    db.commit()
    return _detail(db, admin)


@router.delete("/administrations/{administration_id}/sections/{section_id}", response_model=AdministrationDetail)
def delete_section(
    administration_id: int, section_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    admin = get_administration(db, actor.user, administration_id, lock=True)
    section = _section(admin, section_id)
    if len(admin.sections) <= 1:
        raise _unprocessable("An administration needs at least one section")
    db.delete(section)  # its results go with it (ON DELETE CASCADE)
    record_audit(db, actor, "administration.sections", target_type="administration", target_id=admin.id, detail={"op": "remove"})
    db.commit()
    return _detail(db, admin)


@router.put("/administrations/{administration_id}/results", response_model=AdministrationDetail)
def save_results(
    administration_id: int, body: ResultsBatch, db: Session = Depends(get_db), actor: Actor = Depends(get_actor)
) -> AdministrationDetail:
    """Atomic batch: every row is validated before anything is written. A null pair clears a cell."""
    admin = get_administration(db, actor.user, administration_id, lock=True)
    section_ids = {s.id for s in admin.sections}
    item_ids = {i.id for i in admin.items}
    try:
        upserts, clears = plan_result_changes(
            [ResultRow(r.section_id, r.item_id, r.correct, r.attempted) for r in body.rows], section_ids, item_ids
        )
    except ResultsError as exc:
        raise _unprocessable(str(exc)) from exc
    existing = {
        (r.section_id, r.administration_item_id): r
        for r in db.scalars(select(ItemResult).where(ItemResult.section_id.in_(section_ids)))
    }
    for key in clears:
        if key in existing:
            db.delete(existing[key])
    for section_id, item_id, correct, attempted in upserts:
        row = existing.get((section_id, item_id))
        if row is None:
            db.add(ItemResult(section_id=section_id, administration_item_id=item_id, correct=correct, attempted=attempted))
        else:
            row.correct, row.attempted = correct, attempted
    record_audit(
        db,
        actor,
        "administration.results",
        target_type="administration",
        target_id=admin.id,
        detail={"rows": len(upserts), "cleared": len(clears)},
    )
    db.commit()
    return _detail(db, admin)
```

- [ ] **Step 7: Register the router**

In `backend/app/main.py` change the import to include `administrations` and the loop to:

```python
from app.api import admin, administrations, assessments, auth, generate, health, questions, standards
...
for module in (standards, generate, questions, assessments, administrations, admin):
    protected.include_router(module.router)
```

(The results and variants routers are added to this tuple in Tasks 5 and 7.)

- [ ] **Step 8: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_administrations_api.py tests/test_permissions.py -q -p no:cacheprovider`
Expected: all pass. If a lock test is flaky on a slow machine, raise the `time.sleep(0.8)` to `1.5`; do not remove the assertion that the request waited.
Run the whole suite: `.venv/bin/python -m pytest -q -p no:cacheprovider` — everything still passes (the assessment mutators now lock the row).

- [ ] **Step 9: Lint and commit**

```bash
.venv/bin/ruff check app tests
.venv/bin/ruff format app/api/administrations.py app/services/administrations.py app/api/assessments.py app/schemas/__init__.py tests/test_administrations_api.py tests/test_permissions.py
git add app tests
git commit -m "feat: record assessment use with per-section results, access rules, and row locking"
```

---

### Task 5: Review summary and question usage

**Files:**
- Create: `backend/app/api/results.py`
- Modify: `backend/app/schemas/__init__.py`, `backend/app/main.py`
- Test: `backend/tests/test_results_api.py`

**Interfaces:**
- Consumes: `visible_clauses` (Task 4), the models, `accuracy`, `limited_responses`.
- Produces: `GET /api/results/summary` and `GET /api/questions/{question_id}/usage`; schemas `SummaryRow`, `ResultsSummaryPage`, `QuestionRef`, `UsageEntry`, `UsagePage`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_results_api.py`:

```python
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
    assert first["total"] >= 3 and len(first["items"]) == 1 and first["items"][0]["question_id"] != second["items"][0]["question_id"]
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_results_api.py -q -p no:cacheprovider -x`
Expected: FAIL — `404` for `/api/results/summary`.

- [ ] **Step 3: Add the schemas**

Append to `backend/app/schemas/__init__.py`:

```python
class SummaryRow(BaseModel):
    question_id: int
    standard_id: int
    standard_code: str
    course_name: str
    family_key: str | None
    template_key: str | None
    stem: str
    dok: int
    question_type: QuestionType
    times_used: int
    last_used: date | None
    correct: int
    attempted: int
    accuracy: float | None
    limited_responses: bool


class ResultsSummaryPage(BaseModel):
    items: list[SummaryRow]
    total: int
    limit: int
    offset: int


class QuestionRef(BaseModel):
    id: int
    status: QuestionStatus
    standard_code: str


class UsageEntry(BaseModel):
    administration_id: int
    label: str
    administered_on: date
    assessment_id: int
    assessment_title: str
    pinned_version_no: int
    is_current_version: bool
    correct: int
    attempted: int
    accuracy: float | None
    limited_responses: bool


class UsagePage(BaseModel):
    items: list[UsageEntry]
    total: int
    limit: int
    offset: int
    parent: QuestionRef | None
    variants: list[QuestionRef]
```

- [ ] **Step 4: Write the router**

Create `backend/app/api/results.py`:

```python
"""Review surfaces: the question summary across visible administrations, and per-question usage."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    Administration,
    AdministrationItem,
    Assessment,
    ItemResult,
    Question,
    QuestionVersion,
    Standard,
    User,
)
from app.schemas import QuestionRef, ResultsSummaryPage, SummaryRow, UsageEntry, UsagePage
from app.services.administrations import visible_clauses
from app.services.bank import not_found
from app.services.results import accuracy, limited_responses

router = APIRouter(tags=["results"])


@router.get("/results/summary", response_model=ResultsSummaryPage)
def results_summary(
    course_id: int | None = None,
    standard_id: int | None = None,
    family_key: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResultsSummaryPage:
    """Questions appearing in at least one visible, non-deleted administration. Aggregate figures only."""
    stmt = (
        select(
            AdministrationItem.question_id.label("question_id"),
            func.count(func.distinct(Administration.id)).label("times_used"),
            func.max(Administration.administered_on).label("last_used"),
            func.coalesce(func.sum(ItemResult.correct), 0).label("correct"),
            func.coalesce(func.sum(ItemResult.attempted), 0).label("attempted"),
        )
        .select_from(AdministrationItem)
        .join(Administration, Administration.id == AdministrationItem.administration_id)
        .join(Question, Question.id == AdministrationItem.question_id)
        .join(Standard, Standard.id == Question.standard_id)
        .outerjoin(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
        .where(*visible_clauses(user))
        .group_by(AdministrationItem.question_id)
    )
    if standard_id is not None:
        stmt = stmt.where(Question.standard_id == standard_id)
    if course_id is not None:
        stmt = stmt.where(Standard.course_id == course_id)
    if family_key is not None:
        stmt = stmt.where(Question.family_key == family_key)
    grouped = stmt.subquery()
    total = db.scalar(select(func.count()).select_from(grouped)) or 0
    ratio = cast(grouped.c.correct, Numeric) / func.nullif(grouped.c.attempted, 0)
    ordered = (
        select(grouped)
        .order_by(case((grouped.c.attempted == 0, 1), else_=0), ratio, grouped.c.question_id)
        .limit(limit)
        .offset(offset)
    )
    page = db.execute(ordered).all()
    questions = {
        q.id: q
        for q in db.scalars(
            select(Question)
            .where(Question.id.in_([r.question_id for r in page]))
            .options(selectinload(Question.versions), selectinload(Question.standard).selectinload(Standard.course))
        )
    }
    items = []
    for r in page:
        q = questions[r.question_id]
        v = q.current_version
        items.append(
            SummaryRow(
                question_id=q.id,
                standard_id=q.standard_id,
                standard_code=q.standard.code,
                course_name=q.standard.course.name,
                family_key=q.family_key,
                template_key=q.template_key,
                stem=v.stem,
                dok=v.dok,
                question_type=v.question_type,
                times_used=r.times_used,
                last_used=r.last_used,
                correct=r.correct,
                attempted=r.attempted,
                accuracy=accuracy(r.correct, r.attempted),
                limited_responses=limited_responses(r.attempted),
            )
        )
    return ResultsSummaryPage(items=items, total=total, limit=limit, offset=offset)


def _ref(q: Question) -> QuestionRef:
    return QuestionRef(id=q.id, status=q.status, standard_code=q.standard.code)


@router.get("/questions/{question_id}/usage", response_model=UsagePage)
def question_usage(
    question_id: int,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UsagePage:
    """Every visible, non-deleted administration a question appeared in, with the pinned version used."""
    question = db.scalar(select(Question).options(selectinload(Question.standard)).where(Question.id == question_id))
    if question is None:
        raise not_found("Question")
    stmt = (
        select(
            Administration.id.label("administration_id"),
            Administration.label.label("label"),
            Administration.administered_on.label("administered_on"),
            Assessment.id.label("assessment_id"),
            Assessment.title.label("assessment_title"),
            QuestionVersion.version_no.label("version_no"),
            func.coalesce(func.sum(ItemResult.correct), 0).label("correct"),
            func.coalesce(func.sum(ItemResult.attempted), 0).label("attempted"),
        )
        .select_from(AdministrationItem)
        .join(Administration, Administration.id == AdministrationItem.administration_id)
        .join(Assessment, Assessment.id == Administration.assessment_id)
        .join(QuestionVersion, QuestionVersion.id == AdministrationItem.question_version_id)
        .outerjoin(ItemResult, ItemResult.administration_item_id == AdministrationItem.id)
        .where(AdministrationItem.question_id == question_id, *visible_clauses(user))
        .group_by(Administration.id, Assessment.id, QuestionVersion.id, AdministrationItem.id)
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Administration.administered_on.desc(), Administration.id.desc()).limit(limit).offset(offset)
    ).all()
    parent = None
    if question.variant_of_id is not None:
        parent_row = db.scalar(
            select(Question).options(selectinload(Question.standard)).where(Question.id == question.variant_of_id)
        )
        parent = _ref(parent_row) if parent_row else None
    variants = db.scalars(
        select(Question)
        .options(selectinload(Question.standard))
        .where(Question.variant_of_id == question_id)
        .order_by(Question.id)
    ).all()
    return UsagePage(
        items=[
            UsageEntry(
                administration_id=r.administration_id,
                label=r.label,
                administered_on=r.administered_on,
                assessment_id=r.assessment_id,
                assessment_title=r.assessment_title,
                pinned_version_no=r.version_no,
                is_current_version=r.version_no == question.current_version_no,
                correct=r.correct,
                attempted=r.attempted,
                accuracy=accuracy(r.correct, r.attempted),
                limited_responses=limited_responses(r.attempted),
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
        parent=parent,
        variants=[_ref(v) for v in variants],
    )
```

In `backend/app/main.py` add `results` to the import and the loop tuple: `for module in (standards, generate, questions, assessments, administrations, results, admin):`.

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_results_api.py -q -p no:cacheprovider`
Expected: all pass. If `test_usage_is_paginated...` orders equal dates unexpectedly, the second sort key `Administration.id.desc()` already breaks ties.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check app tests
.venv/bin/ruff format app/api/results.py app/schemas/__init__.py tests/test_results_api.py
git add app tests
git commit -m "feat: add results summary and per-question usage endpoints"
```

### Task 6: Extract the shared generation service

A pure refactor: variants must call exactly the code the generate endpoints call. Existing tests pin the behavior.

**Files:**
- Create: `backend/app/services/generation.py`
- Modify: `backend/app/api/generate.py`
- Test: `backend/tests/test_generation_service.py`

**Interfaces:**
- Produces: `eocep_blocked_templates(std, family) -> set[str]` and `generate_for_request(db, req: GenerateRequest, seed: str) -> (Standard, QuestionFamily, dict)`; the same behavior and `HTTPException`s the private `_generate` had.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_generation_service.py`:

```python
"""The extracted generation service behaves exactly like the preview endpoint."""

from tests.test_api import _generate


def test_service_output_matches_the_preview_endpoint(client, db):
    from app.schemas import GenerateRequest
    from app.services.generation import generate_for_request

    _, body = _generate(client, "biology-1", "B-LS2-1", "population-carrying-capacity", seed="svc")
    api_out = client.post("/api/generate/preview", json=body).json()
    _, family, out = generate_for_request(db, GenerateRequest(**body), "svc")
    assert family.key == "population-carrying-capacity"
    assert [g["parameters"] for g in out["groups"]] == [g["parameters"] for g in api_out["groups"]]
    assert [q["stem"] for g in out["groups"] for q in g["questions"]] == [
        q["stem"] for g in api_out["groups"] for q in g["questions"]
    ]
    assert out["options"]["generation_mode"] == "classroom"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_generation_service.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.generation'`.

- [ ] **Step 3: Create the service** (a move of `_eocep_blocked_templates` and `_generate` from `api/generate.py`, bodies unchanged)

Create `backend/app/services/generation.py`:

```python
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
```

- [ ] **Step 4: Point `api/generate.py` at the service**

In `backend/app/api/generate.py` delete the local `_eocep_blocked_templates` and `_generate` functions, and add:

```python
from app.services.generation import generate_for_request as _generate
```

Then let ruff remove imports that are now unused (`get_standard`, `resolve_family`, and anything else it reports); keep `observable_text`, `generate_set`, `GenerationError`, `Standard` — the bundle path still uses them.

- [ ] **Step 5: Run the new test and the whole suite**

Run: `.venv/bin/python -m pytest tests/test_generation_service.py -q -p no:cacheprovider` → `1 passed`.
Run: `.venv/bin/python -m pytest -q -p no:cacheprovider` → everything passes unchanged (the EOCEP and bundle generate tests are the regression net).

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff check app tests
.venv/bin/ruff format app/services/generation.py app/api/generate.py tests/test_generation_service.py
git add app tests
git commit -m "refactor: extract shared generation service from the generate routes"
```

---

### Task 7: Variants preview and save

**Files:**
- Create: `backend/app/services/variant_generation.py`, `backend/app/api/variants.py`
- Modify: `backend/app/schemas/__init__.py`, `backend/app/main.py`, `backend/tests/test_permissions.py`
- Test: `backend/tests/test_variants_api.py`

**Interfaces:**
- Consumes: `fingerprint`, `candidate_seed`, `issue_token`, `verify_token`, `TokenError`, `MAX_BATCH`, `LINEAGE_CEILING`, `MAX_ATTEMPTS` (Task 2); `generate_for_request` (Task 6); `save_generated`, `not_found`, `record_audit`; `Question.variant_of_id` (Task 3).
- Produces: `unavailable_reason(parent) -> str | None`; `preview_variants(db, actor, ids) -> list[dict]`; `save_variants(db, actor, tokens) -> (created_ids, parent_ids)`; routes `POST /api/questions/variants/preview` and `POST /api/questions/variants/save`; schemas `VariantPreviewRequest`, `VariantCandidate`, `VariantRecord`, `VariantPreviewOut`, `VariantSaveRequest`, `VariantSaveOut`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_variants_api.py`:

```python
"""Linked variants: preview persists nothing, save re-derives from signed tokens, distinctness and locking."""

import time
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update

from app.models import AuditEvent, GenerationRun, Question
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
    assert single.status_code == 200 and single.json()["records"][0]["status"] == "unavailable"  # never 422 by batch size


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


def test_audit_event_names_ids_and_counts_but_no_content(anon, db):
    qid = make_question(anon, "regular")
    vid, rec = make_variant(anon, qid)
    db.expire_all()
    event = db.scalars(select(AuditEvent).where(AuditEvent.action == "question.variants").order_by(AuditEvent.id.desc())).first()
    assert event.detail == {"parents": [qid], "created": [vid], "count": 1}
    assert rec["candidate"]["stem"] not in str(event.detail)


def test_save_batch_is_capped(anon):
    assert save(anon, ["x"] * 21).status_code == 422
```

Also add to `POLICY_COVERED` in `backend/tests/test_permissions.py`:

```python
    ("POST", "/api/questions/variants/preview"): "read-only preview",
    ("POST", "/api/questions/variants/save"): "creates; owner = caller",
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_variants_api.py -q -p no:cacheprovider -x`
Expected: FAIL — 404/405 on `/api/questions/variants/preview` (or `ModuleNotFoundError` for `variant_generation`).

- [ ] **Step 3: Add the schemas**

Append to `backend/app/schemas/__init__.py`:

```python
class VariantPreviewRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1, max_length=100)


class VariantCandidate(BaseModel):
    question_type: QuestionType
    dok: int
    stem: str
    choices: list[dict[str, Any]]
    answer: str
    explanation: str
    stimulus: dict[str, Any] | None


class VariantRecord(BaseModel):
    parent_id: int
    status: Literal["candidate", "unavailable"]
    reason: str | None = None
    candidate: VariantCandidate | None = None
    candidate_token: str | None = None


class VariantPreviewOut(BaseModel):
    records: list[VariantRecord]


class VariantSaveRequest(BaseModel):
    tokens: list[str] = Field(min_length=1, max_length=100)


class VariantSaveOut(BaseModel):
    question_ids: list[int]
    parent_ids: list[int]
```

- [ ] **Step 4: Write the variant service**

Create `backend/app/services/variant_generation.py`:

```python
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
    return {"parent_id": parent_id, "status": "unavailable", "reason": reason, "candidate": None, "candidate_token": None}


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
```

- [ ] **Step 5: Write the router and register it**

Create `backend/app/api/variants.py`:

```python
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
```

In `backend/app/main.py` add `variants` to the import and put it **before** `questions` in the tuple so its literal paths win:

```python
for module in (standards, generate, variants, questions, assessments, administrations, results, admin):
```

(`test_save_batch_is_capped` sends 21 tokens: the schema allows up to 100, so the route's own cap returns 422.)

- [ ] **Step 6: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_variants_api.py tests/test_permissions.py -q -p no:cacheprovider`
Expected: all pass. Two known sensitivities: (a) `test_lineage_ceiling` relies on `monkeypatch.setattr` reaching the module global that `preview_variants` reads — keep `LINEAGE_CEILING` imported at module level in `variant_generation.py`; (b) if the recursive CTE errors, use the documented alias form (`lineage.alias()`) — the tests will show it.
Run the whole suite: `.venv/bin/python -m pytest -q -p no:cacheprovider`.

- [ ] **Step 7: Lint and commit**

```bash
.venv/bin/ruff check app tests
.venv/bin/ruff format app/services/variant_generation.py app/api/variants.py app/schemas/__init__.py app/main.py tests/test_variants_api.py tests/test_permissions.py
git add app tests
git commit -m "feat: add linked variants with signed preview tokens and lineage-wide distinctness"
```

### Task 8: API types and the pure results module (frontend)

**Files:**
- Modify: `frontend/openapi.json`, `frontend/src/api/schema.d.ts` (regenerated), `frontend/src/api/types.ts`
- Create: `frontend/src/lib/results.ts`

**Interfaces:**
- Consumes: the backend routes and schemas from Tasks 4, 5, 7.
- Produces: `AdministrationSummary`, `AdministrationDetail`, `AdministrationItem`, `ResultsSummaryPage`, `SummaryRow`, `UsagePage`, `VariantRecord` types; and in `lib/results.ts`: `parseCell`, `sumCells`, `accuracyText`, `limitedResponses`, `LIMITED_RESPONSE_THRESHOLD`, types `CellInput`, `CellState`.

- [ ] **Step 1: Regenerate the API schema**

```bash
cd backend && .venv/bin/python scripts/dump_openapi.py
cd ../frontend && npm run gen:api
```

Expected: `frontend/openapi.json` and `frontend/src/api/schema.d.ts` now contain `AdministrationDetail`, `ResultsSummaryPage`, `UsagePage`, `VariantPreviewOut`.

- [ ] **Step 2: Add the type aliases**

In `frontend/src/api/types.ts`, after the `PrintQuestion` alias, add:

```ts
export type AdministrationSummary = S["AdministrationSummary"];
export type AdministrationDetail = S["AdministrationDetail"];
export type AdministrationItem = S["AdministrationItemOut"];
export type ResultsSummaryPage = S["ResultsSummaryPage"];
export type SummaryRow = S["SummaryRow"];
export type UsagePage = S["UsagePage"];
export type VariantRecord = S["VariantRecord"];
```

- [ ] **Step 3: Create the pure module**

Create `frontend/src/lib/results.ts`. Its rules mirror the API contract exactly (they are checked by the manual walkthrough in Task 11, since the project has no frontend test runner):

```ts
/** Result-grid rules. They mirror the API: blank is "no data", never 0; attempted >= 1; 0 <= correct <= attempted. */

export const LIMITED_RESPONSE_THRESHOLD = 10;

export interface CellInput {
  correct: string;
  attempted: string;
}

export type CellState =
  | { kind: "empty" }
  | { kind: "invalid"; message: string }
  | { kind: "valid"; correct: number; attempted: number };

const WHOLE_NUMBER = /^\d+$/;

export function parseCell(input: CellInput): CellState {
  const correct = input.correct.trim();
  const attempted = input.attempted.trim();
  if (correct === "" && attempted === "") return { kind: "empty" };
  if (correct === "" || attempted === "") {
    return { kind: "invalid", message: "Enter both correct and attempted, or clear both." };
  }
  if (!WHOLE_NUMBER.test(correct) || !WHOLE_NUMBER.test(attempted)) {
    return { kind: "invalid", message: "Use whole numbers." };
  }
  const c = Number(correct);
  const a = Number(attempted);
  if (a < 1) return { kind: "invalid", message: "Attempted must be at least 1." };
  if (c > a) return { kind: "invalid", message: "Correct cannot be more than attempted." };
  return { kind: "valid", correct: c, attempted: a };
}

/** Totals over the valid cells only; empty and invalid cells add nothing. */
export function sumCells(states: CellState[]): { correct: number; attempted: number } {
  let correct = 0;
  let attempted = 0;
  for (const s of states) {
    if (s.kind === "valid") {
      correct += s.correct;
      attempted += s.attempted;
    }
  }
  return { correct, attempted };
}

/** "—" when nothing was attempted (no data), otherwise a whole-number percentage. */
export function accuracyText(correct: number, attempted: number): string {
  return attempted <= 0 ? "—" : `${Math.round((correct / attempted) * 100)}%`;
}

/** Display hint only. No data (0) is "no data", not "limited". */
export function limitedResponses(attempted: number): boolean {
  return attempted > 0 && attempted < LIMITED_RESPONSE_THRESHOLD;
}
```

- [ ] **Step 4: Type-check and lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/openapi.json frontend/src/api frontend/src/lib/results.ts
git commit -m "feat: regenerate API types and add pure result-grid rules"
```

---

### Task 9: Record use and the results grid (frontend)

**Files:**
- Create: `frontend/src/components/RecordUse.tsx`, `frontend/src/pages/AdministrationPage.tsx`
- Modify: `frontend/src/pages/AssessmentBuilder.tsx`, `frontend/src/main.tsx`

**Interfaces:**
- Consumes: Task 8 types and `lib/results.ts`; `api`, `unwrap`, `queryClient`, `ui` components.
- Produces: route `/administrations/:id`; `<RecordUse a={AssessmentDetail} />`.

- [ ] **Step 1: Create the record-use form**

Create `frontend/src/components/RecordUse.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient } from "../api/queries";
import type { AssessmentDetail } from "../api/types";
import { ErrorNotice, Section } from "./ui";
import { formatDate } from "../lib/format";

function todayLocal(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

/** "Record use": an assessment has no finalized or printed state, so this is open for any assessment with questions. */
export default function RecordUse({ a }: { a: AssessmentDetail }) {
  const navigate = useNavigate();
  const [label, setLabel] = useState("");
  const [date, setDate] = useState(todayLocal());
  const [sections, setSections] = useState("");
  const names = sections
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const past = useQuery({
    queryKey: ["administrations", a.id],
    queryFn: () =>
      unwrap(
        api.GET("/api/assessments/{assessment_id}/administrations", { params: { path: { assessment_id: a.id } } }),
      ),
  });

  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/assessments/{assessment_id}/administrations", {
          params: { path: { assessment_id: a.id } },
          body: { label: label.trim(), administered_on: date, sections: names },
        }),
      ),
    onSuccess: (d) => {
      void queryClient.invalidateQueries({ queryKey: ["administrations", a.id] });
      navigate(`/administrations/${d.id}`);
    },
  });

  const empty = a.items.length === 0;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!empty && label.trim() && names.length) create.mutate();
  };

  return (
    <Section title="Record use" id="use-h">
      <p className="mb-2 text-sm text-muted">
        Record that you gave this assessment, then enter how each section did on each question. Your entries are
        visible to you and to administrators only.
      </p>
      {empty ? <p className="text-sm text-muted">Add questions to this assessment first.</p> : null}
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label htmlFor="ru-label" className="field-label">
            Label
          </label>
          <input
            id="ru-label"
            className="input"
            value={label}
            placeholder="Unit 3 quiz"
            disabled={empty}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="ru-date" className="field-label">
            Date given
          </label>
          <input
            id="ru-date"
            type="date"
            className="input"
            value={date}
            required
            disabled={empty}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="ru-sections" className="field-label">
            Sections <span className="font-normal text-muted">(comma-separated)</span>
          </label>
          <input
            id="ru-sections"
            className="input"
            value={sections}
            placeholder="Period 2, Period 4"
            disabled={empty}
            onChange={(e) => setSections(e.target.value)}
          />
        </div>
        <div aria-live="polite">
          <ErrorNotice error={create.error} />
        </div>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={empty || !label.trim() || names.length === 0 || create.isPending}
        >
          {create.isPending ? "Recording…" : "Record use"}
        </button>
      </form>
      {past.data && past.data.length > 0 ? (
        <div className="mt-4">
          <h3 className="mb-1 font-bold">Past uses</h3>
          <ul className="space-y-1 text-sm">
            {past.data.map((u) => (
              <li key={u.id}>
                <Link to={`/administrations/${u.id}`}>{u.label}</Link>{" "}
                <span className="text-muted">
                  {formatDate(u.administered_on)}, {u.items_with_data} of {u.item_count} questions have data
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Section>
  );
}
```

- [ ] **Step 2: Create the results grid page**

Create `frontend/src/pages/AdministrationPage.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, unwrap } from "../api/client";
import { queryClient } from "../api/queries";
import type { AdministrationDetail } from "../api/types";
import { ErrorNotice, Loading, Notice, PageHeader, Pill, Section } from "../components/ui";
import { formatDate } from "../lib/format";
import { accuracyText, limitedResponses, parseCell, sumCells, type CellInput, type CellState } from "../lib/results";

const EMPTY: CellInput = { correct: "", attempted: "" };
const cellKey = (sectionId: number, itemId: number) => `${sectionId}:${itemId}`;

function savedCells(d: AdministrationDetail): Record<string, CellInput> {
  const out: Record<string, CellInput> = {};
  for (const r of d.results) {
    out[cellKey(r.section_id, r.item_id)] = { correct: String(r.correct), attempted: String(r.attempted) };
  }
  return out;
}

export default function AdministrationPage() {
  const id = Number(useParams().id);
  const q = useQuery({
    queryKey: ["administration", id],
    queryFn: () =>
      unwrap(api.GET("/api/administrations/{administration_id}", { params: { path: { administration_id: id } } })),
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorNotice error={q.error} />;
  // Re-mount after every fetch/save so the grid starts from what the server holds.
  return <Grid key={q.dataUpdatedAt} d={q.data} />;
}

function Grid({ d }: { d: AdministrationDetail }) {
  const saved = useMemo(() => savedCells(d), [d]);
  const [cells, setCells] = useState<Record<string, CellInput>>(saved);
  const [newSection, setNewSection] = useState("");

  const cell = (s: number, i: number): CellInput => cells[cellKey(s, i)] ?? EMPTY;
  const setField = (s: number, i: number, field: keyof CellInput, value: string) =>
    setCells((prev) => ({ ...prev, [cellKey(s, i)]: { ...(prev[cellKey(s, i)] ?? EMPTY), [field]: value } }));

  const states = new Map<string, CellState>();
  for (const s of d.sections) for (const it of d.items) states.set(cellKey(s.id, it.id), parseCell(cell(s.id, it.id)));
  const anyInvalid = [...states.values()].some((s) => s.kind === "invalid");
  const changed = d.sections.flatMap((s) =>
    d.items
      .filter((it) => {
        const now = cell(s.id, it.id);
        const was = saved[cellKey(s.id, it.id)] ?? EMPTY;
        return now.correct.trim() !== was.correct || now.attempted.trim() !== was.attempted;
      })
      .map((it) => ({ s, it })),
  );

  const refresh = (fresh: AdministrationDetail) => {
    queryClient.setQueryData(["administration", d.id], fresh);
    void queryClient.invalidateQueries({ queryKey: ["results"] });
    void queryClient.invalidateQueries({ queryKey: ["administrations"] });
    void queryClient.invalidateQueries({ queryKey: ["usage"] });
  };

  const save = useMutation({
    mutationFn: () => {
      const rows = changed.map(({ s, it }) => {
        const st = states.get(cellKey(s.id, it.id))!;
        return st.kind === "valid"
          ? { section_id: s.id, item_id: it.id, correct: st.correct, attempted: st.attempted }
          : { section_id: s.id, item_id: it.id, correct: null, attempted: null };
      });
      return unwrap(
        api.PUT("/api/administrations/{administration_id}/results", {
          params: { path: { administration_id: d.id } },
          body: { rows },
        }),
      );
    },
    onSuccess: refresh,
  });

  const addSection = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/administrations/{administration_id}/sections", {
          params: { path: { administration_id: d.id } },
          body: { name: newSection.trim() },
        }),
      ),
    onSuccess: refresh,
  });

  const removeSection = useMutation({
    mutationFn: (sectionId: number) =>
      unwrap(
        api.DELETE("/api/administrations/{administration_id}/sections/{section_id}", {
          params: { path: { administration_id: d.id, section_id: sectionId } },
        }),
      ),
    onSuccess: refresh,
  });

  const submitSection = (e: FormEvent) => {
    e.preventDefault();
    if (newSection.trim()) addSection.mutate();
  };

  return (
    <>
      <PageHeader
        title={d.label}
        lead={
          <>
            {d.assessment_title}, given {formatDate(d.administered_on)}.{" "}
            <Link to={`/assessments/${d.assessment_id}`}>Back to the assessment</Link>
          </>
        }
      />
      <Notice tone="info">
        “Correct” means students who earned full credit; partial credit is not supported yet. Leave a cell blank when you
        have no data. Blank is different from 0.
      </Notice>
      <div className="my-3 flex flex-wrap items-center gap-3" aria-live="polite">
        <button
          type="button"
          className="btn btn-primary"
          disabled={anyInvalid || changed.length === 0 || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? "Saving…" : "Save results"}
        </button>
        {anyInvalid ? <span className="text-sm text-red-700">Fix the highlighted cells to save.</span> : null}
        {!anyInvalid && changed.length > 0 ? <span className="text-sm text-muted">Unsaved changes</span> : null}
        <ErrorNotice error={save.error ?? addSection.error ?? removeSection.error} />
      </div>

      <div className="panel mb-5 overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Correct and attempted counts by question and section</caption>
          <thead>
            <tr className="border-b border-line-soft text-left">
              <th scope="col" className="p-3">
                Question
              </th>
              {d.sections.map((s) => (
                <th key={s.id} scope="col" className="p-3">
                  {s.name}
                </th>
              ))}
              <th scope="col" className="p-3">
                All sections
              </th>
            </tr>
          </thead>
          <tbody>
            {d.items.map((it) => {
              const total = sumCells(d.sections.map((s) => states.get(cellKey(s.id, it.id))!));
              return (
                <tr key={it.id} className="border-b border-line-soft align-top">
                  <th scope="row" className="min-w-56 p-3 text-left font-normal">
                    <span className="font-bold">{it.position}.</span> {it.stem.slice(0, 110)}
                    {it.stem.length > 110 ? "…" : ""}
                    <div className="text-xs text-muted">
                      {it.standard_code}, DOK {it.dok}, version {it.pinned_version_no}
                    </div>
                  </th>
                  {d.sections.map((s) => {
                    const c = cell(s.id, it.id);
                    const st = states.get(cellKey(s.id, it.id))!;
                    const errId = `err-${s.id}-${it.id}`;
                    const invalid = st.kind === "invalid";
                    return (
                      <td key={s.id} className="p-3">
                        <div className="flex items-center gap-1">
                          <input
                            className="input w-16"
                            inputMode="numeric"
                            aria-label={`${s.name}, Question ${it.position}, correct`}
                            aria-invalid={invalid}
                            aria-describedby={invalid ? errId : undefined}
                            value={c.correct}
                            onChange={(e) => setField(s.id, it.id, "correct", e.target.value)}
                          />
                          <span aria-hidden="true">/</span>
                          <input
                            className="input w-16"
                            inputMode="numeric"
                            aria-label={`${s.name}, Question ${it.position}, attempted`}
                            aria-invalid={invalid}
                            aria-describedby={invalid ? errId : undefined}
                            value={c.attempted}
                            onChange={(e) => setField(s.id, it.id, "attempted", e.target.value)}
                          />
                        </div>
                        {invalid ? (
                          <p id={errId} className="mt-1 text-xs text-red-700">
                            {st.message}
                          </p>
                        ) : null}
                      </td>
                    );
                  })}
                  <td className="p-3 tabular-nums">
                    <div className="font-bold">
                      {total.attempted > 0 ? `${total.correct} / ${total.attempted}` : "—"}
                    </div>
                    <div>{accuracyText(total.correct, total.attempted)}</div>
                    {limitedResponses(total.attempted) ? <Pill>Limited response count</Pill> : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Section title="Sections" id="sections-h">
        <ul className="mb-3 flex flex-wrap gap-2">
          {d.sections.map((s) => (
            <li key={s.id} className="flex items-center gap-2 rounded border border-line-soft px-2 py-1">
              {s.name}
              {d.sections.length > 1 ? (
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  disabled={removeSection.isPending}
                  onClick={() => {
                    const warn = changed.length ? " Unsaved changes on this page will be lost." : "";
                    if (window.confirm(`Remove “${s.name}” and its results?${warn}`)) removeSection.mutate(s.id);
                  }}
                >
                  Remove
                </button>
              ) : null}
            </li>
          ))}
        </ul>
        <form onSubmit={submitSection} className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor="new-section" className="field-label">
              Add a section
            </label>
            <input
              id="new-section"
              className="input"
              value={newSection}
              placeholder="Period 6"
              onChange={(e) => setNewSection(e.target.value)}
            />
          </div>
          <button type="submit" className="btn" disabled={!newSection.trim() || addSection.isPending}>
            Add section
          </button>
        </form>
      </Section>
    </>
  );
}
```

- [ ] **Step 3: Wire the pieces in**

In `frontend/src/pages/AssessmentBuilder.tsx`: add `import RecordUse from "../components/RecordUse";` and, in the `<aside>` directly after `<Summary a={a} />`, add:

```tsx
          <RecordUse a={a} />
```

In `frontend/src/main.tsx`: add `import AdministrationPage from "./pages/AdministrationPage";` and, next to the `/assessments/:id` route, add:

```tsx
          { path: "/administrations/:id", element: <AdministrationPage /> },
```

- [ ] **Step 4: Type-check, lint, build**

Run: `cd frontend && npx tsc -b && npm run lint && npm run build`
Expected: clean. Fix any type errors against the generated schema names (for example if a generated property is optional); do not loosen types with `any`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: add record-use form and per-section results grid"
```

---

### Task 10: Review page, make practice, and the usage panel (frontend)

**Files:**
- Create: `frontend/src/pages/ResultsPage.tsx`, `frontend/src/components/UsagePanel.tsx`
- Modify: `frontend/src/main.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/pages/QuestionDetail.tsx`

**Interfaces:**
- Consumes: Task 8 types and helpers; `useCourses`, `useFamilies`, `useStandards`, `cleanQuery`.
- Produces: route `/results`; nav link "Results"; `<UsagePanel questionId={number} />`.

- [ ] **Step 1: Create the usage panel**

Create `frontend/src/components/UsagePanel.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, unwrap } from "../api/client";
import { accuracyText } from "../lib/results";
import { formatDate } from "../lib/format";
import { ErrorNotice, Loading, Pill, Section } from "./ui";

const PAGE = 10;

/** Where this question was used and how those classes did, by the exact version pinned at the time. */
export default function UsagePanel({ questionId }: { questionId: number }) {
  const [offset, setOffset] = useState(0);
  const q = useQuery({
    queryKey: ["usage", questionId, offset],
    queryFn: () =>
      unwrap(
        api.GET("/api/questions/{question_id}/usage", {
          params: { path: { question_id: questionId }, query: { limit: PAGE, offset } },
        }),
      ),
  });

  return (
    <Section title="Class results" id="usage-h">
      {q.isPending ? <Loading /> : null}
      <ErrorNotice error={q.error} />
      {q.data ? (
        <>
          {q.data.total === 0 ? (
            <p className="text-sm text-muted">Not recorded in any of your uses yet.</p>
          ) : (
            <ul className="divide-y divide-line-soft">
              {q.data.items.map((u) => (
                <li key={u.administration_id} className="py-2 text-sm">
                  <Link to={`/administrations/${u.administration_id}`} className="font-bold">
                    {u.label}
                  </Link>{" "}
                  <span className="text-muted">
                    {formatDate(u.administered_on)}, {u.assessment_title}. Version {u.pinned_version_no}
                    {u.is_current_version ? " (current)" : " (an earlier version)"}.
                  </span>
                  <div className="tabular-nums">
                    {u.attempted > 0 ? `${u.correct} / ${u.attempted}` : "No data"} {accuracyText(u.correct, u.attempted)}{" "}
                    {u.limited_responses ? <Pill>Limited response count</Pill> : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {q.data.total > PAGE ? (
            <div className="mt-2 flex gap-2">
              <button type="button" className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
                Newer
              </button>
              <button
                type="button"
                className="btn btn-sm"
                disabled={offset + PAGE >= q.data.total}
                onClick={() => setOffset(offset + PAGE)}
              >
                Older
              </button>
            </div>
          ) : null}
          {q.data.parent || q.data.variants.length ? (
            <div className="mt-3 text-sm">
              {q.data.parent ? (
                <p>
                  Variant of <Link to={`/questions/${q.data.parent.id}`}>question {q.data.parent.id}</Link>.
                </p>
              ) : null}
              {q.data.variants.length ? (
                <p>
                  New generated items from this one:{" "}
                  {q.data.variants.map((v, i) => (
                    <span key={v.id}>
                      {i ? ", " : ""}
                      <Link to={`/questions/${v.id}`}>{v.id}</Link>
                    </span>
                  ))}
                  .
                </p>
              ) : null}
              <p className="text-muted">
                A variant is a new generated item from the same family and template. Its results are recorded
                separately from the original’s.
              </p>
            </div>
          ) : null}
        </>
      ) : null}
    </Section>
  );
}
```

In `frontend/src/pages/QuestionDetail.tsx` add `import UsagePanel from "../components/UsagePanel";` and render `<UsagePanel questionId={d.id} />` directly after the `Used in assessments` `Section` (it uses `d` as the loaded question detail).

- [ ] **Step 2: Create the review page**

Create `frontend/src/pages/ResultsPage.tsx`:

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api, cleanQuery, unwrap } from "../api/client";
import { queryClient, useCourses, useFamilies, useStandards } from "../api/queries";
import type { SummaryRow, VariantRecord } from "../api/types";
import { CodeTag, Empty, ErrorNotice, Loading, Notice, PageHeader, Pill, Section } from "../components/ui";
import { formatDate } from "../lib/format";
import { accuracyText } from "../lib/results";

const PAGE = 25;
const MAX_SELECTION = 20;

export default function ResultsPage() {
  const courses = useCourses();
  const families = useFamilies();
  const [courseId, setCourseId] = useState("");
  const [standardId, setStandardId] = useState("");
  const [familyKey, setFamilyKey] = useState("");
  const [offset, setOffset] = useState(0);
  const standards = useStandards({ course_id: courseId ? Number(courseId) : null });

  const summary = useQuery({
    queryKey: ["results", "summary", courseId, standardId, familyKey, offset],
    queryFn: () =>
      unwrap(
        api.GET("/api/results/summary", {
          params: {
            query: cleanQuery({
              course_id: courseId ? Number(courseId) : undefined,
              standard_id: standardId ? Number(standardId) : undefined,
              family_key: familyKey || undefined,
              limit: PAGE,
              offset,
            }),
          },
        }),
      ),
  });

  const [selected, setSelected] = useState<Map<number, string>>(new Map());
  const [records, setRecords] = useState<VariantRecord[] | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [savedIds, setSavedIds] = useState<number[] | null>(null);

  const toggle = (row: SummaryRow) =>
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(row.question_id)) next.delete(row.question_id);
      else next.set(row.question_id, row.stem);
      return next;
    });

  const makePractice = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/questions/variants/preview", { body: { question_ids: [...selected.keys()] } })),
    onSuccess: (out) => {
      setRecords(out.records);
      setPicked(new Set(out.records.filter((r) => r.status === "candidate").map((r) => r.parent_id)));
      setSavedIds(null);
    },
  });

  const saveVariants = useMutation({
    mutationFn: () => {
      const tokens = (records ?? [])
        .filter((r) => r.status === "candidate" && picked.has(r.parent_id) && r.candidate_token)
        .map((r) => r.candidate_token as string);
      return unwrap(api.POST("/api/questions/variants/save", { body: { tokens } }));
    },
    onSuccess: (out) => {
      setSavedIds(out.question_ids);
      setRecords(null);
      setSelected(new Map());
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
      void queryClient.invalidateQueries({ queryKey: ["usage"] });
    },
  });

  const resetPaging = () => setOffset(0);
  const rows = summary.data?.items ?? [];
  const total = summary.data?.total ?? 0;

  return (
    <>
      <PageHeader
        title="Results"
        lead="Questions from your recorded uses, lowest accuracy first. Choose questions to get new generated items from the same family and template."
      />
      <Notice tone="info">
        A low percentage does not show why students missed a question. Worth checking: the wording and reading load, the
        question format, whether the content was taught, and whether the key or a choice is ambiguous.
      </Notice>

      <div className="my-4 grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="f-course" className="field-label">
            Course
          </label>
          <select
            id="f-course"
            className="input"
            value={courseId}
            onChange={(e) => {
              setCourseId(e.target.value);
              setStandardId("");
              resetPaging();
            }}
          >
            <option value="">All courses</option>
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.use_year})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-standard" className="field-label">
            Standard
          </label>
          <select
            id="f-standard"
            className="input"
            value={standardId}
            onChange={(e) => {
              setStandardId(e.target.value);
              resetPaging();
            }}
          >
            <option value="">All standards</option>
            {standards.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-family" className="field-label">
            Question family
          </label>
          <select
            id="f-family"
            className="input"
            value={familyKey}
            onChange={(e) => {
              setFamilyKey(e.target.value);
              resetPaging();
            }}
          >
            <option value="">All families</option>
            {families.data?.map((f) => (
              <option key={f.key} value={f.key}>
                {f.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <ErrorNotice error={summary.error} />
      {summary.isPending ? (
        <Loading />
      ) : rows.length === 0 ? (
        <Empty>No recorded uses match. Record a use from an assessment page, then enter results.</Empty>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Questions by accuracy across your recorded uses</caption>
            <thead>
              <tr className="border-b border-line-soft text-left">
                <th scope="col" className="p-3">
                  <span className="sr-only">Select</span>
                </th>
                <th scope="col" className="p-3">
                  Question
                </th>
                <th scope="col" className="p-3">
                  Correct / attempted
                </th>
                <th scope="col" className="p-3">
                  Uses
                </th>
                <th scope="col" className="p-3">
                  Last used
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.question_id} className="border-b border-line-soft align-top">
                  <td className="p-3">
                    <input
                      type="checkbox"
                      className="check"
                      aria-label={`Select question ${r.question_id}`}
                      checked={selected.has(r.question_id)}
                      disabled={!selected.has(r.question_id) && selected.size >= MAX_SELECTION}
                      onChange={() => toggle(r)}
                    />
                  </td>
                  <td className="min-w-64 p-3">
                    <Link to={`/questions/${r.question_id}`}>
                      {r.stem.slice(0, 120)}
                      {r.stem.length > 120 ? "…" : ""}
                    </Link>
                    <div className="mt-1">
                      <CodeTag code={r.standard_code} course={r.course_name} />
                    </div>
                  </td>
                  <td className="p-3 tabular-nums">
                    <div className="font-bold">{r.attempted > 0 ? `${r.correct} / ${r.attempted}` : "No data"}</div>
                    <div>{accuracyText(r.correct, r.attempted)}</div>
                    {r.limited_responses ? <Pill>Limited response count</Pill> : null}
                  </td>
                  <td className="p-3 tabular-nums">{r.times_used}</td>
                  <td className="p-3">{r.last_used ? formatDate(r.last_used) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > PAGE ? (
        <div className="my-3 flex items-center gap-2">
          <button type="button" className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
            Previous
          </button>
          <span className="text-sm text-muted">
            {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
          </span>
          <button
            type="button"
            className="btn btn-sm"
            disabled={offset + PAGE >= total}
            onClick={() => setOffset(offset + PAGE)}
          >
            Next
          </button>
        </div>
      ) : null}

      <div className="my-4 flex flex-wrap items-center gap-3" aria-live="polite">
        <button
          type="button"
          className="btn btn-primary"
          disabled={selected.size === 0 || makePractice.isPending}
          onClick={() => makePractice.mutate()}
        >
          {makePractice.isPending ? "Generating…" : `Make practice variants (${selected.size})`}
        </button>
        <span className="text-sm text-muted">
          Up to {MAX_SELECTION} at a time. Nothing is saved until you choose “Save selected variants”.
        </span>
        <ErrorNotice error={makePractice.error ?? saveVariants.error} />
      </div>

      {savedIds ? (
        <Notice tone="ok">
          Saved {savedIds.length} new generated {savedIds.length === 1 ? "item" : "items"}:{" "}
          {savedIds.map((id, i) => (
            <span key={id}>
              {i ? ", " : ""}
              <Link to={`/questions/${id}`}>question {id}</Link>
            </span>
          ))}
          . They are separate questions; results for them are recorded separately from the originals’.
        </Notice>
      ) : null}

      {records ? (
        <Section title="Review new generated items" id="variants-h">
          <p className="mb-3 text-sm text-muted">
            Each is a new generated item from the same family and template as its original. It may not be equivalent in
            difficulty. Tick the ones to keep.
          </p>
          <ul className="space-y-4">
            {records.map((r) => (
              <li key={r.parent_id} className="rounded border border-line-soft p-3">
                <p className="text-sm text-muted">Original (question {r.parent_id}): {selected.get(r.parent_id)}</p>
                {r.status === "unavailable" || !r.candidate ? (
                  <p className="mt-2 text-sm">
                    <strong>No new item available.</strong> {r.reason}
                  </p>
                ) : (
                  <div className="mt-2">
                    <label className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        className="check mt-1"
                        checked={picked.has(r.parent_id)}
                        onChange={() =>
                          setPicked((prev) => {
                            const next = new Set(prev);
                            if (next.has(r.parent_id)) next.delete(r.parent_id);
                            else next.add(r.parent_id);
                            return next;
                          })
                        }
                      />
                      <span>
                        <span className="font-bold">{r.candidate.stem}</span>
                        {r.candidate.choices.length ? (
                          <ul className="mt-1 space-y-0.5 text-sm">
                            {r.candidate.choices.map((c) => (
                              <li key={String(c.label)}>
                                {String(c.label)}. {String(c.text)}
                                {c.correct === true ? " ✓" : ""}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="mt-1 block text-sm">{r.candidate.answer}</span>
                        )}
                      </span>
                    </label>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              className="btn btn-primary"
              disabled={picked.size === 0 || saveVariants.isPending}
              onClick={() => saveVariants.mutate()}
            >
              {saveVariants.isPending ? "Saving…" : `Save selected variants (${picked.size})`}
            </button>
            <button type="button" className="btn" onClick={() => setRecords(null)}>
              Discard
            </button>
          </div>
        </Section>
      ) : null}
    </>
  );
}
```

- [ ] **Step 3: Route and navigation**

In `frontend/src/main.tsx` add `import ResultsPage from "./pages/ResultsPage";` and the route `{ path: "/results", element: <ResultsPage /> },` beside the assessments routes. In `frontend/src/components/Layout.tsx`, add `{ to: "/results", label: "Results" },` to `NAV` after the Assessments entry.

- [ ] **Step 4: Type-check, lint, build**

Run: `cd frontend && npx tsc -b && npm run lint && npm run build`
Expected: clean. If `c.label` or `c.text` do not type-check as `unknown`, keep the `String(...)` conversions; do not use `any`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: add results review, practice variants, and class-results panel"
```

---

### Task 11: Verification, docs, and deploy notes

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Full backend verification with zero skips**

Start your own throwaway Postgres (see File Structure for the command and port; check `docker ps` first), then:

```bash
cd backend
.venv/bin/ruff check app tests
TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54332/sb_test .venv/bin/python -m pytest -q -p no:cacheprovider -rs
```

Expected: all pass, `0 skipped`. Existing tests that count families, routes, or check `POLICY_COVERED` must still pass. Stop only the container you started.

- [ ] **Step 2: Frontend checks**

```bash
cd frontend && npx tsc -b && npm run lint && npm run build
```

Expected: clean.

- [ ] **Step 3: Manual walkthrough** (no frontend test runner exists, so this is the check for the grid's rules; run the app against a scratch database)

Record the outcome of each line in the PR description:

1. On an assessment with two questions, "Record use" is disabled when the assessment is empty, and enabled with a label and at least one section name.
2. In the grid, tab through the inputs and confirm a screen reader label such as “Period 2, Question 1, correct”.
3. Enter `12` / `30` in one cell: the overall shows `12 / 30` and `40%` before saving; reload without saving and it is gone.
4. Leave another cell blank: it shows `—`, never `0%`. Enter `0` / `30`: it shows `0%`.
5. Enter `31` / `30`, then `1` / `0`, then only one of the two: each shows its message, marks the cell invalid, and disables Save. Clear both and Save re-enables.
6. Enter `2` / `5` and `3` / `4` in two sections of one question (9 attempted): "Limited response count" appears; change to `3` / `5` (10): it disappears.
7. Save, reload, and confirm values persist; clear a saved cell, save, and confirm it returns to `—`.
8. Add a section, remove a section (confirm dialog appears), and confirm the last section has no Remove button.
9. As a second regular teacher, open the first teacher's `/administrations/<id>` URL: not found; `/results` shows none of their totals; as an admin, all are visible.
10. On `/results`, select two rows, "Make practice variants": candidates appear beside originals, nothing new appears in the question bank yet; untick one, "Save selected variants": exactly one new question exists, linked from the original's Class results panel.
11. Select a question from a bundle family (chemical-system-stability), if any exist: it shows "No new item available" with a reason while the rest of the batch still works.
12. Edit a question after using it: its Class results panel shows the earlier use as “an earlier version”.

Playwright is installed in `frontend` (with cached browsers) but there is no config or test file in the repo, so an automated grid smoke test is a possible follow-up, not part of this plan.

- [ ] **Step 4: Update HANDOFF.md**

In the "Implemented families"-adjacent areas of `HANDOFF.md`, add a short "Results and variants" section describing: the four new tables and `questions.variant_of_id` (migration 0005), the access rule (owner plus admin/power), the routes, that variants cover single-standard engine families only (bundle families return "unavailable"), the token/batch/lineage limits, and that results and usage are visible only to the owner and moderators.

- [ ] **Step 5: Commit**

```bash
git add HANDOFF.md
git commit -m "docs: record results tracking and linked variants in the handoff"
```

- [ ] **Step 6: Deploy note (do not run without the user's explicit go-ahead)**

Follow the documented flow: back up the database (`docker compose exec -T postgres pg_dump ...`), tag the current image for rollback, then `docker compose up -d --build`. The entrypoint applies migration `0005` on start. Verify with `docker compose ps` (healthy) and by checking the new tables exist. The migration adds tables and one nullable column and is reversible with `alembic downgrade 0004_bundle_generation_runs` (take the backup first because a downgrade drops recorded results).

---

## Self-Review (done while drafting)

- **Spec coverage:** data model and indexes — Task 3; snapshot, lock, ownership-by-recorder — Task 4; results validation, null-pair clear, strict ints, section rules — Tasks 1 and 4; summary universe/aggregate-only/pagination, usage per pinned version, access filtering, soft-delete exclusion — Task 5; preview-without-persisting, per-parent unavailable records, signed expiring user-bound tokens, informational parent version, fingerprint against the whole lineage, 409/422 contract, lineage ceiling, batch cap, single audit event, no content in audit — Tasks 2, 6, 7; UI (record use for any non-empty assessment, grid rules, limited response count, fixed caution, "Save selected variants", pinned version in the usage panel) — Tasks 8–10; error table and testing matrix — Tasks 4, 5, 7; manual verification of the grid — Task 11.
- **Non-goals respected:** no student data, no notes columns, no `students_tested`, no consumed-token table, no bundle variants, no LLM, no equivalence claims.
- **Placeholder scan:** none. Tasks 1 and 2 contain code that was run and passed during drafting (34 tests). The remaining backend, migration and frontend code was written against the repository as read during drafting but was not executed; each task is TDD and ends with a run step, and the Task 7 notes call out the two places most likely to need adjustment (the recursive CTE form and the monkeypatched module global).
- **Type consistency:** `plan_result_changes` returns `(section_id, item_id, correct, attempted)` upserts and `(section_id, item_id)` clears; the API maps `item_id` to `administration_item_id` consistently in `ResultOut`, the grid keys, and tests. `SummaryRow.standard_id` is added in Task 5 before the frontend uses filters. Token fields (`parent_version_id`) match between `issue_token`, `verify_token`, and provenance.
