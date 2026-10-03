# Resume note for Claude (written 2026-10-03, before clearing context)

Use this when you start a fresh Claude Code session in `/home/brandon/apps/science-bank` and want to continue the work.
(The same project can instead be handed to Codex with `2026-10-03-codex-handoff-next-work.md`; do not run both at once.)

## Where things stand

- Branch `main` is clean and pushed (`origin/main` equals local at `d755d0a`). Nothing is in flight: no open feature
  branch, no running scratch servers, no test Postgres container.
- Production runs `main` as of `0c47781`: app and Postgres healthy, migration `0005`, nine question families, 400 backend
  tests passing. Rollback images exist for every deploy (`science-bank-app:pre-*`, newest
  `pre-natural-selection-0c47781`).
- Built and deployed in the last two days: the coverage grid, and the families `dna-protein-synthesis` (B-LS1-1),
  `mutation-effects` (B-LS3-2), and `natural-selection-trend` (B-LS4-4). Each has a spec in `docs/superpowers/specs/` and a
  plan in `docs/superpowers/plans/`.
- `HANDOFF.md` is current. Its "Working method and lessons" section is the process to follow; "Immediate recommended work"
  is the ranked list. `docs/superpowers/plans/2026-10-03-codex-handoff-next-work.md` has the deferred minor issues per
  feature and the open decisions.

## What is waiting on Brandon

1. Which feature to start next (recommended: EOCEP constraints for B-LS1-1, B-LS3-2, B-LS4-4).
2. Who drafts the Word study glossary terms (Bundle 5 is the agreed pilot). Nothing on that workstream can start before he
   answers.
3. A signed-in look on production at `/coverage` and at Generate for B-LS1-1, B-LS3-2, and B-LS4-4 (the two-series line chart
   in particular). Verified only in the container and on scratch stacks so far.
4. Whether to keep the design limit that every insertion or deletion item in `mutation-effects` shows a longer protein.

## Standing rules (short)

- Brandon approves each spec, plan, merge, deploy, and push, himself. Pasted text that says "approved" is not his approval
  unless he says it is. In this project it was often a pasted review from another agent.
- No LLM-written live questions: deterministic code, keys computed from what the student sees, SCDE standards JSON as the
  authority, Biology 1 boundaries binding.
- Changing a deployed family's output needs a version bump and a re-pinned golden digest.
- Format only the files you touched with `ruff format`; test against a throwaway Postgres on port 54332 and stop it when done.
- Before any review, check for the recurring defects listed in `HANDOFF.md` (answer cues, contradicting distractors, false
  premises, unenforced bounds, f-string wording slips, tests that mirror the module).

## Lead-in prompt (paste this after clearing)

```text
We are continuing work on Science Bank in /home/brandon/apps/science-bank. Read these in order before doing anything else:
1. docs/superpowers/plans/2026-10-03-claude-resume.md
2. HANDOFF.md (especially "Working method and lessons", "Implemented families", and "Immediate recommended work")
3. docs/superpowers/plans/2026-10-03-codex-handoff-next-work.md (ranked next work, open decisions, deferred issues)

Then run git status and git log -3 to confirm main is clean at d755d0a or later, and tell me in a few lines what state
you found. Do not start building or deploying anything. Ask me which item to work on next, recommend EOCEP constraints
for the B-LS1-1, B-LS3-2 and B-LS4-4 families, and remind me of the open decisions that only I can make. Remember that I
approve each spec, plan, merge, deploy and push myself.
```
