# Fisicapapa Agent Instructions

Before editing any file, every agent must read:

1. `CODEX_HANDOFF_V4_2.md`
2. `.skills/fisicapapa-v42/SKILL.md`
3. `.skills/fisicapapa-implementation-planner/SKILL.md`
4. `.skills/ui-ux-pro-max-skill/SKILL.md`
5. `.skills/python-patterns/SKILL.md`
6. `.skills/verification-loop/SKILL.md`
7. `.skills/documentation-lookup/SKILL.md`

If a skill file is missing, stop and report which one is missing.

## Project mode

This is not a SaaS product.
This is a personal analysis web app for Fisicapapa / Melate Pro V7.

Optimize for:
- personal decision-making;
- mobile readability;
- fast interpretation;
- visual clarity;
- safe V4.2 data handling;
- no accidental legacy/V3 behavior.

## Active architecture

Official runner:
- `local_cruncher_v4_2_calibrated.py`

Base engine:
- `local_cruncher_v4_deep_stacking.py`

Web V2:
- `index.html`
- `v4-clean-app.js`
- `v4-results-panels.js`
- `v4-under40-verifier.js`
- `v4-system-diagnostics.js`
- `v4-combo-comparator.js`
- `v4-visual-system.css`

Output:
- `resultados.json`

## Hard rules

- Do not reactivate V3.
- Do not modify the cruncher unless explicitly asked.
- Do not modify `resultados.json` from frontend.
- Do not change the official Score Neto V4 formula unless explicitly requested.
- Do not present any score as a guaranteed winning probability.
- Keep V4.2 validation strict.
- Keep calibrated physics: 2026-05-17 / draw 4214.
- Keep lifecycle reset after draw 4213.
- Keep the `<40` verifier frontend-only.
- Do not use `operational_confidence`.
- Do not show `undefined`, `null`, or `NaN` in UI.
- Prefer small surgical edits over full rewrites.

## Required skill usage report

Every PR must include:

1. Skills read.
2. Relevant rules extracted from each skill.
3. How those rules influenced the implementation.
4. Files changed.
5. Validation performed.
6. What was intentionally not changed.
7. New areas of opportunity discovered.
