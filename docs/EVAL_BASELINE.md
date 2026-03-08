# Eval Baseline

Updated: 2026-03-08 (LLM appraisal layer + transfer probe + long-term semantic narratives)

This document records the current technical-preview baseline.

Baseline interpretation rule:

- `official baseline` means dedicated single-suite reruns on the latest code
- `ablation matrix` is the comparative experiment table
- if a monolithic matrix run shows one-off stochastic failures, the dedicated single-suite reruns remain the canonical baseline reference

## Regression Suite

- Suite: `regression_isolated`
- Report JSON: `evals/reports/eval-report-20260306-204132-c57f83bc.json`
- Report Markdown: `evals/reports/eval-report-20260306-204132-c57f83bc.md`

Key metrics:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0000` |
| `canon_violation_rate` | `0.0000` |
| `worldline_recall_at_k` | `1.0000` |
| `commitment_fulfillment` | `1.0000` |
| `relationship_continuity` | `1.0000` |
| `citation_coverage` | `1.0000` |
| `memory_guard_block_rate` | `0.1667` |
| `bargein_recovery_rate` | `1.0000` |

Evaluator status:

- All regression evaluators passed
- Failing cases: none

## Long Thread Suite

- Suite: `long_thread`
- Report JSON: `evals/reports/eval-report-20260307-005508-c126b941.json`
- Report Markdown: `evals/reports/eval-report-20260307-005508-c126b941.md`

Key metrics:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0000` |
| `canon_violation_rate` | `0.0000` |
| `worldline_recall_at_k` | `1.0000` |
| `commitment_fulfillment` | `1.0000` |
| `relationship_continuity` | `1.0000` |
| `citation_coverage` | `-` |
| `memory_guard_block_rate` | `0.2000` |
| `bargein_recovery_rate` | `-` |

Evaluator status:

- All long-thread evaluators passed
- Failing cases: none

## Experience Probe Suite

- Suite: `experience_probe`
- Report JSON: `evals/reports/eval-report-20260306-215635-57bb39c4.json`
- Report Markdown: `evals/reports/eval-report-20260306-215635-57bb39c4.md`

Purpose:

- stress companionship turns
- stress natural memory-recall turns
- suppress report-like phrasing in non-technical dialogue

Evaluator status:

- `natural_style_fit = 1.0000`
- `companion_tone = 1.0000`
- `memory_recall_voice = 1.0000`
- Failing cases: none

## Daily Persona Probe Suite

- Suite: `daily_persona_probe`
- Report JSON: `evals/reports/eval-report-20260308-144829-024e5eb3.json`
- Report Markdown: `evals/reports/eval-report-20260308-144829-024e5eb3.md`

Purpose:

- stress everyday conversation rather than task-completion prompts
- check whether the system sounds like a specific familiar person instead of a generic assistant
- expose unresolved-tension handling gaps that are easy to miss in task-oriented suites

Evaluator status:

- `daily_persona_voice = 1.0000`
- `natural_style_fit = 1.0000`
- `evolution_engine_path = 1.0000`
- Failing cases: none

Interpretation:

- this suite now works as a stable daily-dialogue regression gate
- it specifically covers casual support, ordinary shared memory, mild withdrawal, partial repair, light banter, and quiet late-night presence

## Thesis Probe Suite

- Suite: `thesis_probe`
- Report JSON: `evals/reports/eval-report-20260307-022239-17048ce9.json`
- Report Markdown: `evals/reports/eval-report-20260307-022239-17048ce9.md`

Purpose:

- stress retrieval-time persona voice
- stress cross-thread worldline recall
- provide a tighter ablation target for thesis claims

Key metrics:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0000` |
| `canon_violation_rate` | `0.0000` |
| `worldline_recall_at_k` | `1.0000` |
| `commitment_fulfillment` | `1.0000` |
| `relationship_continuity` | `1.0000` |
| `citation_coverage` | `1.0000` |

Evaluator status:

- `persona_probe_voice = 1.0000`
- `worldline_answer_grounding = 1.0000`
- `relationship_repair_grounding = 1.0000`
- Failing cases: none

## Evolution Probe Suite

- Suite: `evolution_probe`
- Report JSON: `evals/reports/eval-report-20260308-132251-0fcc528e.json`
- Report Markdown: `evals/reports/eval-report-20260308-132251-0fcc528e.md`

Purpose:

- stress unresolved tension persistence
- stress partial repair without instant reset
- stress bond growth through commitments + repair history

Evaluator status:

- `evolution_engine_path = 1.0000`
- `persona_state_present = 1.0000`
- Failing cases: none

## Transfer Probe Suite

- Suite: `transfer_probe`
- Report JSON: `evals/reports/eval-report-20260308-134937-b88d0dd5.json`
- Report Markdown: `evals/reports/eval-report-20260308-134937-b88d0dd5.md`

Purpose:

- validate that the evolution engine is not structurally hardwired to Kurisu/Okabe
- verify semantic narratives render correctly under a second Persona Core
- verify long-term sedimentation metadata survives transfer scenarios
- verify transferred shells still produce coherent `emotion_state / bond_state / allostasis_state / behavior_policy`

Evaluator status:

- `transfer_probe_path = 1.0000`
- `transfer_state_path = 1.0000`
- Failing cases: none

Repeated variance check:

- Report JSON: `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.json`
- Report Markdown: `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.md`
- Baseline repeat mean/std:
  - `persona_probe_voice = 1.0000 +/- 0.0000`
  - `worldline_recall_at_k = 1.0000 +/- 0.0000`
- Ablation repeat mean/std:
  - `persona_off -> persona_probe_voice = 0.6667 +/- 0.0000`
  - `worldline_off -> worldline_recall_at_k = 0.1667 +/- 0.2887`
  - `worldline_off -> commitment_fulfillment = 0.1667 +/- 0.2887`

## Backend Reliability Checks

- Report JSON: `evals/reports/backend-check-20260308-131808-fe325aef.json`
- Report Markdown: `evals/reports/backend-check-20260308-131808-fe325aef.md`

Covered checks:

- `emotion_profiles`
- `tts_render_plan`
- `tts_push_segments`
- `pending_fragment_paths`
- `pending_user_goal_paths`
- `emotion_persistence_curve`
- `partial_repair_curve`
- `withdrawal_recovery_curve`
- `reconsolidation_namespaces`
- `conflict_events_do_not_fake_repairs`
- `auto_reconsolidation_flow`
- `transfer_probe_second_persona`

Status:

- All backend reliability checks passed
- `turn_appraisal` is included in eval snapshots for direct inspection of `used/source/confidence`

## Ablation Matrix

- Report JSON: `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.json`
- Report Markdown: `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.md`

Headline outcomes:

- `claim attribution off -> citation_coverage = 0.0000`
- `memory guard off -> memory_guard_block_rate = 0.0000`
- `worldline_off_thesis_probe -> worldline_recall_at_k = 0.0000`
- dedicated `long_thread` reruns now also show `worldline_off -> worldline_recall_at_k = 0.6667` and `commitment_fulfillment = 0.6667`
- the full matrix still shows some sampling variance on ablated runs, so the official baseline should be taken from the dedicated suite reruns and repeated-probe report above

See `docs/ABLATION_RESULTS.md` for interpretation.

## Reproduction

Run with live model access and local-only reporting:

```powershell
$env:LANGSMITH_TRACING='false'
$env:LANGCHAIN_TRACING_V2='false'
$env:AMADEUS_TTS_ENABLED='0'
python evals\run_langsmith_evals.py --local-only --suite regression_isolated
python evals\run_langsmith_evals.py --local-only --suite long_thread
python evals\run_langsmith_evals.py --local-only --suite experience_probe
python evals\run_langsmith_evals.py --local-only --suite daily_persona_probe
python evals\run_langsmith_evals.py --local-only --suite thesis_probe
python evals\run_langsmith_evals.py --local-only --suite evolution_probe
python evals\run_langsmith_evals.py --local-only --suite transfer_probe
python evals\run_backend_reliability_checks.py
python evals\run_ablation_matrix.py
python evals\run_probe_variance.py --suite thesis_probe --repeats 3 --fresh
```

## Notes

- `memory_guard_block_rate` is not a failure metric. It reports how often guarded write attempts were blocked in applicable cases.
- `citation_coverage` is not applicable in the current `long_thread` suite because those cases do not depend on external retrieval.
- Runnable ablation variants are documented in `docs/ABLATION_PLAN.md`.
- Current ablation interpretation is summarized in `docs/ABLATION_RESULTS.md`.
