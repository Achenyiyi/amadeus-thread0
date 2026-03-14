# Eval Asset Retention Plan

Updated: 2026-03-14

This document defines which evaluation assets are the current canonical references after the latest backend cleanup.

Retention rules:

- do not delete any report referenced by `README.md` or `docs/EVAL_BASELINE.md`
- prefer archive over delete for superseded reruns and one-off diagnostics
- keep subjective review packs even when a newer scripted suite exists; they are the realism review layer

## Keep: Current Canonical Baseline

These are the current default references and should remain in `evals/reports/`:

- `eval-report-20260314-003517-de7e1c24.{json,md}`  
  `daily_persona_probe`
- `eval-report-20260314-003845-0110b34d.{json,md}`  
  `open_evolution_eval`
- `eval-report-20260314-005203-78e97887.{json,md}`  
  `transfer_probe`
- `eval-report-20260314-013424-055b29b8.{json,md}`  
  `natural_long_thread`

## Keep: Subjective Review References

These should also remain in the root reports directory because they are the current realism review entry points:

- `subjective-review-pack-20260313-235109-c26f888c.{json,md}`
- `subjective-review-pack-20260314-000628-41945a51.{json,md}`
- `subjective-review-pack-20260314-001520-43529789.{json,md}`
- `subjective-review-pack-20260314-002238-8d1316cc.{json,md}`
- `subjective-review-pack-20260314-002743-9bedf77c.{json,md}`

## Keep: Supporting Green References

These are still useful for historical comparison or for areas not rerun in the final cleanup loop:

- `eval-report-20260311-195915-e41f9cdb.{json,md}`  
  `experience_probe`
- `eval-report-20260311-201717-1c5b98c5.{json,md}`  
  `user_style_probe`
- `eval-report-20260310-022019-40bb840e.{json,md}`  
  `selfhood_probe`
- `eval-report-20260311-200857-e7a4b411.{json,md}`  
  `behavior_layer_probe`
- `eval-report-20260311-200625-16188d67.{json,md}`  
  `dialogue_mode_counterpart_probe`
- `eval-report-20260310-163121-cd3db27f.{json,md}`  
  `behavior_agenda_probe`
- `eval-report-20260311-030547-3095ed19.{json,md}`  
  `behavior_queue_probe`
- `eval-report-20260311-181037-3f784643.{json,md}`  
  `behavior_queue_conflict_probe`
- `eval-report-20260310-170407-c03cdb32.{json,md}`  
  `agenda_conflict_probe`
- `eval-report-20260310-164000-dcbd9c77.{json,md}`  
  `proactive_checkin_probe`
- `eval-report-20260311-164632-48653069.{json,md}`  
  `counterpart_assessment_probe`
- `eval-report-20260310-150123-21c6aa4c.{json,md}`  
  `scheduled_life_probe`
- `eval-report-20260311-065737-67f3a42e.{json,md}`  
  `commitment_life_probe`
- `eval-report-20260311-171358-d2cc1510.{json,md}`  
  `commitment_maturity_probe`
- `eval-report-20260311-194643-4faf9584.{json,md}`  
  `relationship_life_timing_probe`
- `eval-report-20260311-175017-0bbec16a.{json,md}`  
  `self_activity_probe`
- `eval-report-20260311-175026-f080461b.{json,md}`  
  `self_activity_maturity_probe`
- `eval-report-20260311-183011-e834239e.{json,md}`  
  `perception_probe`
- `eval-report-20260311-182255-064afffc.{json,md}`  
  `perception_appraisal_probe`

## Archive: Superseded Final-Loop Reruns

These belong to the same refinement cycle but are no longer the canonical reference:

- `eval-report-20260314-005041-0ce09e60.*`
- `eval-report-20260314-010550-2e6859cb.*`
- `eval-report-20260314-012100-cb7fcd20.*`

Reason:

- they captured intermediate states before continuation recovery and scaffold-memory contamination were fully fixed
- they are now archived under `evals/reports/archive/2026-03-final-loop-superseded/`

## Archive: Pre-2026-03-14 Baseline Reports

Older green reports from 2026-03-09 to 2026-03-13 should be kept for thesis traceability, but they should no longer be presented as the default baseline once the new canonical reports exist.

Recommended action:

- move them into `evals/reports/archive/2026-03-pre-final-baseline/`
- preserve any files explicitly cited in thesis draft material until those citations are updated

## Do Not Delete Yet

Do not delete the following during the current phase:

- anything referenced by:
  - `README.md`
  - `docs/EVAL_BASELINE.md`
  - `docs/ABLATION_RESULTS.md`
  - `docs/thesis_draft/*`
- public benchmark bundle reports
- appraisal calibration reports
- user-study raw data
- subjective review packs

## Cleanup Order

1. Create `evals/reports/archive/2026-03-pre-final-baseline/` if it does not already exist.
2. Move superseded reruns there.
3. Re-run `git status`.
4. Verify every file referenced by `README.md` and `docs/EVAL_BASELINE.md` still exists.
5. Only then consider deleting obvious debug leftovers.
