---
name: fisicapapa-implementation-planner
description: Plan and implement safe changes in Fisicapapa Web V2 and Cruncher V4.2. Use when working on Fisicapapa improvements involving Cruncher V4.2, resultados.json, scoring logic, data-quality validation, UI/UX interpretation, manual evaluators, diagnostics, or the web/cruncher data contract.
---

# Fisicapapa Implementation Planner

## First Move

Before editing any file, think in three layers:

1. Data contract
2. Cruncher logic
3. Web interpretation

Do not jump directly to code. Decide where the change belongs before touching files.

## Required Reading

Always read:

- `CODEX_HANDOFF_V4_2.md`
- `.skills/fisicapapa-v42/SKILL.md`

If the task involves UI/UX, also read:

- `.skills/ui-ux-pro-max-skill/SKILL.md`

If the task involves Python, scoring, or `resultados.json`, also read:

- `.skills/python-testing/SKILL.md`
- `.skills/verification-loop/SKILL.md`

## Planning Protocol

Before modifying code, write a short plan that includes:

- Problem detected
- Files involved
- Ownership: `cruncher`, `web`, `resultados.json contract`, `documentation`, or a combination
- Risk level: `low`, `medium`, or `high`
- Expected output
- Validation steps

Keep the plan brief, but make the ownership decision explicit.

## Ownership Rules

Only modify the cruncher when the change must originate from generated data.

The cruncher owns:

- `predictions`
- `generator_pool`
- `top_combinations`
- `number_scores`
- `manual_suggestion_seed`
- `physics_summary`
- `walk_forward`
- `feedback_loop`
- calibration metadata
- scores used as source of truth

The web owns:

- visualization
- manual evaluator
- comparison tools
- diagnostics
- human explanations
- visual warnings
- frontend-only verifiers
- UX flow

Use this decision rule:

- If a value must be reproducible across devices, put it in `resultados.json`.
- If a value is only for user guidance, display, comparison, or explanation, it can belong in the web.
- If a value changes ranking, Monte Carlo, model output, or walk-forward, it belongs in the cruncher and needs validation.

## Guardrails

Never break or reactivate legacy paths around:

- `local_cruncher_v4_2_calibrated.py`
- `local_cruncher_v4_deep_stacking.py`
- `run_pipeline()`
- `mat()` ball 56 mapping
- V4.2 output contract

Do not:

- Add frontend-only heuristics to the cruncher unless explicitly requested and validated out of sample.
- Mutate `resultados.json` from the web.
- Claim scores are real win probabilities.
- Reactivate V3.
- Hide missing data silently.
- Mix 0-1 and 0-100 scales without explicit normalization.
- Use duplicate scoring functions or silent fallbacks.
- Add magic constants without an explanation.
- Use patcher scripts or full file rewrites for normal edits.
- Reintroduce legacy imports.

Prefer:

- Small changes
- Pure functions
- Clearly named modules
- Diagnostics
- Explicit scale conversion
- Visible warnings
- Focused tests or validation scripts

## Required Validation

Before finishing, check all applicable items:

- `index.html` does not load V3 scripts.
- `feedback_loop.version === "V4.2"` is enforced.
- `manual_suggestion_seed` has 56 entries when JSON is valid.
- Physical panel shows real uses, not fake life percentages.
- `evaluateManualComboV4()` still works.
- `run_pipeline()` still exists.
- `mat()` maps ball 56 correctly.
- No `operational_confidence` remains.
- No `undefined` or `null` is visible in the UI.
- No score is presented as a guaranteed probability.

## PR Response

For PR-style summaries, include:

1. What problem was solved
2. Why the change belongs in web or cruncher
3. Files changed
4. Risks
5. How to test
6. What was intentionally not changed
7. Next recommended improvement
