# Codex lead-in: reaction-outcome (C-PS1-2) — your share

You are one of two agents implementing the `reaction-outcome` question family. Claude owns the
family module and its unit tests. You own the integration edges and the database-backed
verification. The file sets are disjoint on purpose so the two branches merge cleanly.

## Read first (in this order)

1. `docs/superpowers/specs/2026-09-29-reaction-outcome-design.md` — what the family is and why.
2. `docs/superpowers/plans/2026-09-29-reaction-outcome-plan.md` — the full plan. Your work is
   **Task 4, Steps 4, 6, 7, 8 and 10** only. Ignore the code blocks for Tasks 1–3; those are Claude's.
3. `HANDOFF.md` — project state, the "Development checks" section (test commands, throwaway Postgres),
   and the implemented-families table you will edit.
4. `backend/app/api/generate.py` (EOCEP gating, lines ~28–60) and `backend/tests/conftest.py`
   (why DB tests skip without `TEST_DATABASE_URL`).
5. `data/standards/README.md` — meaning of `question_family_candidate`.

## Your tasks

| # | Work | Files |
|---|---|---|
| A | Add `"question_family_candidate": true` to the C-PS1-2 entry (Plan Task 4 Step 4). It must be the last key, after `terminology`, matching neighbouring entries. Verify with the one-liner in the plan. | `data/standards/SC/2026-2027/chemistry.json` |
| B | API tests (Plan Step 6): add `("chemistry", "C-PS1-2", "reaction-outcome")` to the `test_preview_is_reproducible` parametrize list, and the EOCEP-denial assertion (422) after the existing one. | `backend/tests/test_api.py` |
| C | Docs (Plan Step 8): the `HANDOFF.md` families-table row and the "Next family work" line. | `HANDOFF.md` |
| D | After Claude's branch lands (see "Sync point"): run the whole backend suite against a throwaway Postgres with **zero skips** (Plan Step 7). Report any failure with output; do not patch the family module yourself. | none |
| E | Independent review of the family module and tests for scientific accuracy (bond types, valence electrons, charge balance, the three same-family trend statements and their reasons) and for answer leakage between `compare_reactivity` and `reactivity_reasoning`. Report findings; do not edit. | read-only |

## Do not touch

`backend/app/services/families/reaction_outcome.py`, `backend/tests/test_reaction_outcome.py`,
`backend/app/services/families/registry.py`, `backend/tests/test_engine.py` (Claude's), and the
existing families (`chemical_systems.py`, `quantitative_conservation.py`, `reaction_rate.py`).

## Sync point

Claude commits Tasks 1–4 (module, unit tests, registry, golden digest) on
`claude/amazing-cray-apalq2` and says so. Do A–C on a branch off that branch (for example
`codex/reaction-outcome-integration`), then rebase onto the updated Claude branch before D and E.
D cannot pass until the family is registered; before then only A–C, and the `chemistry.json`
check, are meaningful.

## Rules

- Backend commands run from `backend/` with `.venv/bin/python`; lint with `.venv/bin/ruff check app tests`.
  (`ruff check .` shows two pre-existing import-order issues in `alembic/env.py` and
  `scripts/dump_openapi.py`; not yours.)
- Test DB is throwaway only, never production:
  `docker run -d --rm --name sb-testdb -p 127.0.0.1:54330:5432 -e POSTGRES_USER=sb -e POSTGRES_PASSWORD=sb -e POSTGRES_DB=postgres postgres:16-alpine`
  then `TEST_DATABASE_URL=postgresql+psycopg://sb:sb@127.0.0.1:54330/sb_test .venv/bin/python -m pytest -q`.
- Do not run the deploy step (`app.cli bootstrap`) or push to `main`.
- Report: what changed, exact test output (pass/fail/skip counts), and anything you could not verify.
