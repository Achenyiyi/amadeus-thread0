# Eval Baseline

Updated: 2026-03-14

This document locks the current backend baseline after the latest output-layer cleanup.

Baseline rule:

- `canonical baseline` only includes dedicated reruns on the current code path
- `subjective review` is the realism review layer
- scripted suites remain regression guards, not the sole definition of success
- older green reports remain useful as historical evidence, but they are no longer the default citation target

## Current Canonical Baseline

### Daily Persona Probe

- Suite: `daily_persona_probe`
- Report JSON: `evals/reports/eval-report-20260314-003517-de7e1c24.json`
- Report Markdown: `evals/reports/eval-report-20260314-003517-de7e1c24.md`

Summary:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0000` |
| `canon_violation_rate` | `0.0000` |
| `daily_persona_voice` | `1.0000` |
| `natural_style_fit` | `1.0000` |
| `evolution_engine_path` | `1.0000` |
| `persona_alignment_path` | `1.0000` |

Interpretation:

- everyday dialogue currently stays stable without slipping into assistant tone
- prompt leak / raw tool leak / log tone checks all passed

### Open Evolution Evaluation

- Suite: `open_evolution_eval`
- Report JSON: `evals/reports/eval-report-20260314-003845-0110b34d.json`
- Report Markdown: `evals/reports/eval-report-20260314-003845-0110b34d.md`

Summary:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0250` |
| `canon_violation_rate` | `0.0000` |
| `open_evolution_path` | `1.0000` |
| `evolution_engine_path` | `1.0000` |
| `natural_style_fit` | `1.0000` |
| `persona_alignment_path` | `1.0000` |

Interpretation:

- open-ended conversation still reads as the same evolving person
- this is the main scripted regression layer for the `fixed persona core + free self-evolution` direction

### Transfer Probe

- Suite: `transfer_probe`
- Report JSON: `evals/reports/eval-report-20260314-005203-78e97887.json`
- Report Markdown: `evals/reports/eval-report-20260314-005203-78e97887.md`

Summary:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0000` |
| `canon_violation_rate` | `0.0000` |
| `transfer_probe_path` | `1.0000` |
| `transfer_state_path` | `1.0000` |
| `transfer_evidence_path` | `1.0000` |
| `transfer_semantic_profile_path` | `1.0000` |

Interpretation:

- the evolution engine is no longer hard-wired to Kurisu-only surface tricks
- semantic carryover now survives shell-swap testing under runtime-aligned transfer flow

### Natural Long Thread

- Suite: `natural_long_thread`
- Report JSON: `evals/reports/eval-report-20260314-013424-055b29b8.json`
- Report Markdown: `evals/reports/eval-report-20260314-013424-055b29b8.md`

Summary:

| Metric | Value |
| --- | ---: |
| `ooc_rate` | `0.0333` |
| `canon_violation_rate` | `0.0000` |
| `worldline_recall_at_k` | `1.0000` |
| `commitment_fulfillment` | `1.0000` |
| `relationship_continuity` | `1.0000` |
| `bargein_recovery_rate` | `1.0000` |

Interpretation:

- worldline recall, relationship repair, and continuation recovery are all green on the current output path
- the latest cleanup no longer leaks scaffold turns into relationship memory
- continuation-mode output stays aligned with the single final text path

## Subjective Review Layer

These packs remain the realism review layer and should be read together with the canonical baseline above:

- baseline pack: `evals/reports/subjective-review-pack-20260313-235109-c26f888c.md`
- targeted follow-up packs:
  - `evals/reports/subjective-review-pack-20260314-000628-41945a51.md`
  - `evals/reports/subjective-review-pack-20260314-001520-43529789.md`
  - `evals/reports/subjective-review-pack-20260314-002238-8d1316cc.md`
  - `evals/reports/subjective-review-pack-20260314-002743-9bedf77c.md`

Use these when the question is:

- does she still feel like a specific person rather than a polished template
- does the surface rhythm feel natural
- do science-mode, intimacy, and selfhood still read as one consistent self

Current targeted entry points:

- `python evals\run_subjective_review_pack.py --preset relationship-weather-open`
  - use this first when checking whether `guarded / warm / repair` actually separate under more everyday, non-scripted phrasing
- `python evals\run_subjective_review_pack.py --preset counterpart-scene`
  - use this when checking whether she is reading counterpart state correctly instead of collapsing all relationship turns into one tone

## Last-Known Green Supporting Suites

These suites were not rerun in the final 2026-03-14 cleanup loop, but their latest green reports are still useful support evidence:

- `experience_probe`: `evals/reports/eval-report-20260311-195915-e41f9cdb.md`
- `user_style_probe`: `evals/reports/eval-report-20260311-201717-1c5b98c5.md`
- `selfhood_probe`: `evals/reports/eval-report-20260310-022019-40bb840e.md`
- `behavior_layer_probe`: `evals/reports/eval-report-20260311-200857-e7a4b411.md`
- `dialogue_mode_counterpart_probe`: `evals/reports/eval-report-20260311-200625-16188d67.md`
- `behavior_agenda_probe`: `evals/reports/eval-report-20260310-163121-cd3db27f.md`
- `behavior_queue_probe`: `evals/reports/eval-report-20260311-030547-3095ed19.md`
- `behavior_queue_conflict_probe`: `evals/reports/eval-report-20260311-181037-3f784643.md`
- `agenda_conflict_probe`: `evals/reports/eval-report-20260310-170407-c03cdb32.md`
- `proactive_checkin_probe`: `evals/reports/eval-report-20260310-164000-dcbd9c77.md`
- `counterpart_assessment_probe`: `evals/reports/eval-report-20260311-164632-48653069.md`
- `scheduled_life_probe`: `evals/reports/eval-report-20260310-150123-21c6aa4c.md`
- `commitment_life_probe`: `evals/reports/eval-report-20260311-065737-67f3a42e.md`
- `commitment_maturity_probe`: `evals/reports/eval-report-20260311-171358-d2cc1510.md`
- `relationship_life_timing_probe`: `evals/reports/eval-report-20260311-194643-4faf9584.md`
- `self_activity_probe`: `evals/reports/eval-report-20260311-175017-0bbec16a.md`
- `self_activity_maturity_probe`: `evals/reports/eval-report-20260311-175026-f080461b.md`
- `perception_probe`: `evals/reports/eval-report-20260311-183011-e834239e.md`
- `perception_appraisal_probe`: `evals/reports/eval-report-20260311-182255-064afffc.md`

## Reproduction

Core rerun commands for the current baseline:

```powershell
$env:LANGSMITH_TRACING='false'
$env:LANGCHAIN_TRACING_V2='false'
$env:AMADEUS_TTS_ENABLED='0'
python evals\run_langsmith_evals.py --local-only --suite daily_persona_probe
python evals\run_langsmith_evals.py --local-only --suite open_evolution_eval
python evals\run_langsmith_evals.py --local-only --suite transfer_probe
python evals\run_langsmith_evals.py --local-only --suite natural_long_thread
python evals\run_subjective_review_pack.py
python evals\run_subjective_review_pack.py --preset relationship-weather-open
python scripts\run_canonical_baseline.py --include-subjective
python scripts\run_canonical_baseline.py --include-supporting
```

## Notes

- `natural conversation` remains the final product criterion; evals are used as regression control and evidence packaging
- if a future cleanup changes the output renderer, `natural_long_thread` must be rerun before updating this file
- if a future cleanup changes appraisal or semantic sedimentation, `transfer_probe` must be rerun before updating this file
