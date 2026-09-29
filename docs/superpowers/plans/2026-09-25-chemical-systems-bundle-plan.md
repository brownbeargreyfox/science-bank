# Stability & Change in Chemical Systems — Implementation Plan

## 1. Make cross-standard template citations explicit

- Add an optional standard-code field to `TemplateSpec` and its API schema.
- Keep existing single-standard families unchanged; their templates inherit the family binding.
- Update family citation validation and `/api/families` rendering to resolve a template against its
  declared standard, never an arbitrary first binding.

## 2. Add bundle-generation persistence and API

- Add nullable `question_family_runs.bundle_id` with a foreign key to imported bundles.
- Add bundle request/preview schemas and dedicated preview/save endpoints.
- Verify the selected bundle belongs to the family course and contains every required binding as a
  full (not partial) alignment.
- Save each question using the standard indicated by its template, while all group questions share
  a single persisted stimulus and carry per-standard provenance.

## 3. Implement the deterministic shared family

- Create `chemical-system-stability` at version `1.0.0` for C-PS1-5 and C-PS1-7.
- Draw only the curated Mg + HCl scenario, with rate trials and exact conservation arithmetic from
  one stored parameter set.
- Add C-PS1-5 and C-PS1-7 templates with named misconception distractors and a conservation
  explanation item.
- Pin deterministic output and test atom/mass/rate invariants independently.

## 4. Expose it in the UI

- Add supported-generator metadata to bundle responses and a Bundles-page entry point.
- Add bundle-aware state, preview rendering, saving, and regeneration URLs to Generate.
- Regenerate the typed OpenAPI client schema and run lint/build.

## 5. Verify and release

- Run lint, unit tests, and the throwaway-Postgres suite with zero skipped DB tests.
- Review deterministic previews across the seed suite for clear rate/conservation separation.
- Deploy only after the migration and bundle save/reload path pass; preserve an image rollback tag.

