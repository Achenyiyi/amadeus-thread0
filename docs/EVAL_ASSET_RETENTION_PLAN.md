# Eval Asset Retention Plan

Updated: 2026-03-09

This document defines which evaluation assets should be:

- kept as canonical references
- archived as iteration history
- withheld from deletion until a later cleanup pass

Rule of thumb:

- do **not** delete docs under `docs/` during the active thesis stage
- do **not** delete the latest green report for any suite that is referenced by `README.md` or `docs/EVAL_BASELINE.md`
- prefer `archive` over `delete` for older reports, failed reruns, and intermediate calibration outputs

## Keep: Canonical Reports

These are the current canonical references and should remain in-place:

- `evals/reports/eval-report-20260306-204132-c57f83bc.{json,md}`  
  `regression_isolated`
- `evals/reports/eval-report-20260309-120008-7784d487.{json,md}`  
  `long_thread`
- `evals/reports/eval-report-20260306-215635-57bb39c4.{json,md}`  
  `experience_probe`
- `evals/reports/eval-report-20260308-144829-024e5eb3.{json,md}`  
  `daily_persona_probe`
- `evals/reports/eval-report-20260309-113111-54ed9292.{json,md}`  
  `user_style_probe`
- `evals/reports/eval-report-20260309-105523-5db8a0ce.{json,md}`  
  `open_evolution_eval`
- `evals/reports/open-evolution-pairwise-20260309-151635-7d2b5957.{json,md}`  
  `open_evolution_pairwise_eval` diagnostic baseline
- `evals/reports/eval-report-20260308-184959-c26a2273.{json,md}`  
  `thesis_probe`
- `evals/reports/eval-report-20260308-132251-0fcc528e.{json,md}`  
  `evolution_probe`
- `evals/reports/eval-report-20260308-134937-b88d0dd5.{json,md}`  
  `transfer_probe`
- `evals/reports/eval-report-20260309-141604-e8a5b817.{json,md}`  
  `external_persona_probe`
- `evals/reports/eval-report-20260309-124754-ca26cf10.{json,md}`  
  `external_support_probe`
- `evals/reports/eval-report-20260309-142356-c1aec6ec.{json,md}`  
  `external_empathy_probe`
- `evals/reports/eval-report-20260309-141150-18349a5d.{json,md}`  
  `external_continuity_probe`
- `evals/reports/appraisal-calibration-20260309-122807-9d6b1bb4.{json,md}`  
  `GoEmotions appraisal calibration`
- `evals/reports/external-judge-sanity-20260309-142241-51768895.{json,md}`  
  external judge negative-control sanity
- `evals/reports/external-pairwise-sanity-20260309-143014-a2eeaf8a.{json,md}`  
  external judge pairwise-preference sanity
- `evals/reports/backend-check-20260308-131808-fe325aef.{json,md}`  
  backend reliability

## Keep: Thesis / Analysis References

These are still useful for thesis writing, ablation discussion, or historical comparison:

- `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.{json,md}`
- `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.{json,md}`
- `evals/reports/eval-report-20260307-022239-17048ce9.{json,md}`  
  legacy thesis baseline reference
- `evals/reports/eval-report-20260307-005508-c126b941.{json,md}`  
  earlier long-thread green reference

## Archive: Superseded Iteration Reports

These are useful as iteration history but should not be treated as the current baseline.
Recommended action: move into an `evals/reports/archive/` folder in a later cleanup pass.

Examples:

- earlier calibration attempts:
  - `appraisal-calibration-20260309-120800-48887970.*`
  - `appraisal-calibration-20260309-122344-4a5c6cbd.*`
- superseded support/empathy/continuity reruns:
  - `eval-report-20260309-121727-d4736d17.*`
  - `eval-report-20260309-124154-ad364809.*`
  - `eval-report-20260309-124457-6461b4b4.*`
  - `eval-report-20260309-125407-fb40259c.*`
  - `eval-report-20260309-125712-b0be673e.*`
  - `eval-report-20260309-133323-face29ec.*`
  - `eval-report-20260309-133548-27b03750.*`
  - `eval-report-20260309-134514-8354f398.*`
  - `eval-report-20260309-140606-ab65afd6.*`
  - `eval-report-20260309-140855-d666704c.*`
  - `external-judge-sanity-20260309-134015-0518999f.*`
  - `external-judge-sanity-20260309-134059-391784a6.*`
- intermediate reruns from the same refinement loop:
  - `eval-report-20260309-112853-7e60d76b.*`
  - `eval-report-20260309-112626-8b09afa6.*`
  - `eval-report-20260309-112145-c5f5d971.*`
  - `eval-report-20260309-110047-df8e4104.*`
  - `eval-report-20260309-104657-bb43cbaa.*`
  - `eval-report-20260309-070129-b90a0086.*`
  - older 2026-03-08 reruns tied to prompt/evaluator tightening
- open-evolution pairwise one-off diagnostics:
  - `evals/reports/archive/open_evolution_pairwise/*`
  - keep only the explicitly referenced baselines and the latest focused rerun in the root `evals/reports/`

## Archive: Ad-hoc Debug Artifacts

These should not stay mixed with canonical reports long-term, but they are still worth keeping until the thesis/defense materials are frozen:

- `evals/reports/long-thread-focus-20260309.json`
- `evals/reports/long-thread-focus-20260309-rerun.json`

## Do Not Delete Yet

The following should not be deleted during the current phase:

- anything referenced by:
  - `docs/EVAL_BASELINE.md`
  - `README.md`
  - `docs/ABLATION_RESULTS.md`
  - thesis draft files under `docs/thesis_draft/`
- any doc under `docs/`
- user-study raw data and generated packets
- `docs/PERSONA_SYSTEM_CONSTITUTION.md`
- `docs/ARCHITECTURE_ALIGNMENT_MAP.md`

## Cleanup Rule

When cleanup actually happens, do it in this order:

1. Create `evals/reports/archive/`
2. Move superseded iteration reports there
3. Re-run `git status`
4. Verify every file referenced by baseline docs still exists
5. Only then consider deleting obvious one-off debug leftovers
