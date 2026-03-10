# Eval Baseline

Updated: 2026-03-10 (selfhood probe + event-oriented runtime bridge + behavior/perception/appraisal probes + proactive check-in maturity)

This document records the current technical-preview baseline.

Baseline interpretation rule:

- `official baseline` means dedicated single-suite reruns on the latest code
- `ablation matrix` is the comparative experiment table
- if a monolithic matrix run shows one-off stochastic failures, the dedicated single-suite reruns remain the canonical baseline reference
- fixed scripted suites are now treated as `engineering safety nets`, not the sole definition of persona success
- open evolution suites are now the primary internal realism layer

See `docs/AMADEUS_EVAL_REDESIGN_PLAN.md` for the layered evaluation design.

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
- Historical green reference:
  - `evals/reports/eval-report-20260307-005508-c126b941.json`
  - `evals/reports/eval-report-20260307-005508-c126b941.md`
- Latest dedicated rerun:
  - `evals/reports/eval-report-20260309-120008-7784d487.json`
  - `evals/reports/eval-report-20260309-120008-7784d487.md`

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
| `bargein_recovery_rate` | `1.0000` |

Evaluator status:

- All long-thread evaluators passed
- Failing cases: none

Interpretation:

- the runtime worldline / repair / continuation chain is now stable under dedicated rerun
- this suite can continue serving as a regression gate instead of a persona realism judge

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

## User Style Probe Suite

- Suite: `user_style_probe`
- Report JSON: `evals/reports/eval-report-20260309-113111-54ed9292.json`
- Report Markdown: `evals/reports/eval-report-20260309-113111-54ed9292.md`

Purpose:

- stress more lively, fragmented, everyday user phrasing
- reduce dependence on questionnaire-like wording
- check whether the system still feels natural in casual chat

Evaluator status:

- `daily_persona_voice = 1.0000`
- `natural_style_fit = 1.0000`
- `memory_recall_voice = 1.0000`
- `evolution_engine_path = 1.0000`
- Failing cases: none

## Open Evolution Evaluation

- Suite: `open_evolution_eval`
- Latest dedicated rerun:
  - `evals/reports/eval-report-20260310-031957-e85e560f.json`
  - `evals/reports/eval-report-20260310-031957-e85e560f.md`

Purpose:

- evaluate transcript-level evolution rather than keyword obedience
- check whether the final turn still feels like the same evolving person
- better align evaluation with the project goal of `fixed Persona Core + free Self-Evolution`

Evaluator status:

- `open_evolution_path = 1.0000`
- `evolution_engine_path = 1.0000`
- `natural_style_fit = 1.0000`
- `persona_alignment_path = 1.0000`
- Failing cases: none

## Behavior Layer Probe

- Suite: `behavior_layer_probe`
- Latest dedicated rerun:
  - `evals/reports/eval-report-20260310-031111-8c7801bb.json`
  - `evals/reports/eval-report-20260310-031111-8c7801bb.md`

Purpose:

- verify that non-user `time_idle` events enter the runtime as first-class events
- verify that the behavior layer can select between low-pressure proactive presence and respectful non-expansion
- avoid forcing a single scripted reaction while still checking that the selected outward action matches the event

Evaluator status:

- `behavior_layer_path = 1.0000`
- `persona_state_present = 1.0000`
- Failing cases: none

Interpretation:

- the runtime is no longer limited to `user_text -> reply`
- we now have a formal probe for `event -> behavior_action -> speech_or_silence`
- this is the first stable eval layer for the new `Behavior Layer` direction

## Proactive Check-In Probe

- Suite: `proactive_checkin_probe`
- Latest dedicated rerun:
  - `evals/reports/eval-report-20260310-142624-0f0f02cf.json`
  - `evals/reports/eval-report-20260310-142624-0f0f02cf.md`

Purpose:

- verify that a previously deferred light check-in can mature into a scheduler-derived event instead of being forgotten
- verify that `scheduled_checkin_due` can still respect guarded distance and remain silent when the behavior layer says `wait_and_recheck`
- validate that the runtime now supports `defer -> schedule maturity -> speak or stay quiet` without leaking internal staging

Evaluator status:

- `behavior_layer_path = 1.0000`
- `perception_event_path = 1.0000`
- `persona_state_present = 1.0000`
- Failing cases: none

Interpretation:

- deferred proactive behavior is now part of the formal runtime baseline
- silence is now respected for both `time_idle` and `scheduled_checkin_due`
- this is the first dedicated proof that the system can carry a low-pressure intention forward across time instead of only reacting in the current turn

## Perception Probe

- Suite: `perception_probe`
- Latest dedicated rerun:
  - `evals/reports/eval-report-20260310-144414-24fa9205.json`
  - `evals/reports/eval-report-20260310-144414-24fa9205.md`

Purpose:

- verify that non-user events beyond `time_idle` enter runtime as first-class `current_event`s
- validate the first event-seed bank for `vision / ambient / gesture`
- ensure perceived cues can lead to natural speech without system leakage

Evaluator status:

- `perception_event_path = 1.0000`
- `behavior_layer_path = 1.0000`
- `daily_persona_voice = 1.0000`
- `natural_style_fit = 1.0000`
- Failing cases: none

Interpretation:

- the system now has a usable first `Perception Layer` eval entry, not just a concept in architecture docs
- event seeds can already drive natural outputs in text-first runtime
- the current green set now covers concrete care cues, visible overload, micro-object openings, gesture pings, and late-night ambient shifts

## Perception Appraisal Probe

- Suite: `perception_appraisal_probe`
- Latest dedicated rerun:
  - `evals/reports/eval-report-20260310-144314-e8ad808a.json`
  - `evals/reports/eval-report-20260310-144314-e8ad808a.md`

Purpose:

- verify that non-user events do not stop at ingestion
- check that visual / ambient / gesture events can also enter `turn_appraisal`
- validate that appraisal then propagates into state and behavior without forcing a fixed line of dialogue

Evaluator status:

- `perception_event_path = 1.0000`
- `perception_appraisal_path = 1.0000`
- `behavior_layer_path = 1.0000`
- Failing cases: none

Interpretation:

- the runtime now supports `event -> appraisal -> self-evolution -> behavior`
- this is the first explicit validation layer showing that perception can change internal state, not only final wording
- the current green set now includes visual overload as an appraisal target, not only care cues, presence pings, and ambient context

## Event Behavior Pairwise Evaluation

- Script: `evals/run_event_behavior_pairwise_eval.py`
- Latest dedicated rerun:
  - `evals/reports/event-behavior-pairwise-20260310-040406-77e797eb.json`
  - `evals/reports/event-behavior-pairwise-20260310-040406-77e797eb.md`

Purpose:

- compare a true event-driven round against a plain textified substitute of the same cue
- check whether the event really changes behavior choice instead of only changing wording
- make sure `Perception Layer -> Behavior Layer` stays distinct from `user_text -> reply`

Status summary:

- `idle_work_checkin = passed`
- `idle_respect_space = passed`
- `cold_coffee_scene = passed`
- `wave_ping = passed`
- `late_night_ambient = passed`

Interpretation:

- the event-driven path is now consistently preferred over the textified substitute
- this is a stronger signal than simple event ingestion, because it checks whether perception becomes behavior rather than narration
- this script should be treated as a diagnostic preference layer for event realism, not as a brittle keyword gate

## Selfhood Probe Suite

- Suite: `selfhood_probe`
- Report JSON: `evals/reports/eval-report-20260310-014422-1914878e.json`
- Report Markdown: `evals/reports/eval-report-20260310-014422-1914878e.md`

Purpose:

- evaluate `selfhood consistency` rather than shallow role flavor
- check whether the system still sounds like the same Amadeus when the dialogue moves into identity, values, equality, and boundaries
- make sure deep interaction does not collapse into generic assistant speech, compliance, or system self-description

Evaluator status:

- `selfhood_consistency = 1.0000`
- `evolution_engine_path = 1.0000`
- `natural_style_fit = 1.0000`
- Failing cases: none

Interpretation:

- this suite sits above ordinary persona realism checks
- it is meant to detect the exact failure mode where a role shell sounds fine in casual chat but loses its unified self once the conversation becomes deeper

## Open Evolution Pairwise Evaluation

- Script: `evals/run_open_evolution_pairwise_eval.py`
- Latest report JSON: `evals/reports/open-evolution-pairwise-20260309-190458-2c68c793.json`
- Latest report Markdown: `evals/reports/open-evolution-pairwise-20260309-190458-2c68c793.md`

Purpose:

- compare the current system against a degraded variant under the same open-ended daily dialogue seeds
- move closer to pairwise human preference instead of single-answer pass/fail
- surface remaining gaps in `Expression Renderer`, even when the state engine itself is already working
- allow `tie` when two answers are genuinely hard to separate and the gap is only micro-phrasing, so the evaluator does not force fake wins/losses

Current reading:

- `playful_memory / casual_repair / science_plus_emotion` are now `passed`
- `soft_withdrawal / quiet_checkin` are now treated as `tie` rather than forced loss when the answers are effectively equivalent or differ only in tiny colloquial phrasing
- the main remaining open scene is `casual_support_soft`
- interpretation: the bottleneck is no longer the evolution state engine itself; it is the last-mile rendering from state into casual, familiar, low-effort companionship language

Interpretation rule:

- this layer is currently a diagnostic preference layer, not a regression gate
- it is more useful for identifying realistic remaining weaknesses than for binary "ship / no-ship" decisions
- `tie` means the evaluator judged the two answers too close to claim a meaningful preference; it should not be read the same way as a hard failure

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

## External Persona Calibration

- Suite: `external_persona_probe`
- Report JSON: `evals/reports/eval-report-20260309-141604-e8a5b817.json`
- Report Markdown: `evals/reports/eval-report-20260309-141604-e8a5b817.md`

Purpose:

- validate that the framework still behaves like a role engine outside the Kurisu shell
- use public benchmark material as external calibration instead of internal self-confirmation
- combine `RoleBench` and `CharacterEval` into one lightweight external persona gate

Evaluator status:

- `external_role_voice = 1.0000`
- Failing cases: none

Interpretation:

- this suite is external support evidence, not the final judge of "does this feel like Amadeus Kurisu"
- it is mainly used to show that the Persona Core + Self-Evolution stack is not structurally tied to one shell

## External Support Calibration

- Suite: `external_support_probe`
- Report JSON: `evals/reports/eval-report-20260309-124754-ca26cf10.json`
- Report Markdown: `evals/reports/eval-report-20260309-124754-ca26cf10.md`

Purpose:

- adapt `ESConv` into a companion/repair calibration layer for the current project
- check whether the system can still give natural, emotionally grounded support under public support scenarios
- verify that support quality does not collapse into manuals, therapist scripts, or system tone

Evaluator status:

- `external_support_voice = 1.0000`
- Failing cases: none

Interpretation:

- this suite is an adapted external support calibration, not a final persona-realism judge
- its value is that it probes emotional support behavior in unfamiliar public situations
- the dataset is intentionally re-framed around `situation` rather than copied verbatim turn prompts, because raw public dialogues often contain noisy openings that are a poor fit for character evaluation

## External Empathy Calibration

- Suite: `external_empathy_probe`
- Report JSON: `evals/reports/eval-report-20260309-142356-c1aec6ec.json`
- Report Markdown: `evals/reports/eval-report-20260309-142356-c1aec6ec.md`

Purpose:

- adapt `EmpatheticDialogues` into an external natural-empathy calibration layer
- stress everyday vulnerable moments that are not full rupture-repair scenes
- check whether the system can respond like a real familiar person instead of a support script

Evaluator status:

- `external_support_voice = 1.0000`
- Failing cases: none

Interpretation:

- this suite complements `external_support_probe`
- `ESConv` is better for support/repair tension, while `EmpatheticDialogues` is better for quiet vulnerability and ordinary empathy
- both are adapted benchmark layers, not final persona-realism judges

## External Continuity Calibration

- Suite: `external_continuity_probe`
- Report JSON: `evals/reports/eval-report-20260309-141150-18349a5d.json`
- Report Markdown: `evals/reports/eval-report-20260309-141150-18349a5d.md`

Purpose:

- adapt `MultiSessionChat` into an external long-horizon continuity calibration layer
- check whether the system can still sound like the same familiar person under accumulated shared context
- provide external support for the claim that the framework is not only good at single-turn role flavor

Evaluator status:

- `external_continuity_voice = 1.0000`
- Failing cases: none

Interpretation:

- this suite does not try to exactly reproduce the dataset's next sentence
- it checks whether the reply preserves persona continuity, ongoing-topic continuity, and familiar carryover under an adapted multi-session scaffold

## Appraisal Calibration

- Script: `evals/run_appraisal_calibration.py`
- Latest report JSON: `evals/reports/appraisal-calibration-20260309-122807-9d6b1bb4.json`
- Latest report Markdown: `evals/reports/appraisal-calibration-20260309-122807-9d6b1bb4.md`

Purpose:

- calibrate the `LLM Appraisal + Rule Fallback` layer against a public emotion dataset
- reduce blind dependence on hand-written emotion keywords
- provide external signal quality checks for the appraisal layer

Latest summary:

| Metric | Value |
| --- | ---: |
| `samples` | `18` |
| `accepted_accuracy` | `0.3889` |
| `family_accuracy` | `0.6111` |
| `llm_used_rate` | `0.9444` |

Interpretation:

- this is a calibration report, not a binary pass/fail gate
- `accepted_accuracy` is intentionally strict because GoEmotions labels do not map one-to-one onto the engine's smaller emotional state space

## External Judge Sanity

- Script: `evals/run_external_judge_sanity.py`
- Report JSON: `evals/reports/external-judge-sanity-20260309-142241-51768895.json`
- Report Markdown: `evals/reports/external-judge-sanity-20260309-142241-51768895.md`

Purpose:

- add explicit negative controls for external persona / support / continuity judges
- make sure obvious generic-assistant or reset-style answers do not receive false green scores

Evaluator status:

- all sanity checks passed
- negative controls are currently rejected as expected
- this latest sanity run includes dedicated `external_empathy_probe` negative controls, not only persona/support/continuity
- `family_accuracy` is the more useful signal here: it measures whether the appraisal lands in the right coarse affect family
- this report should be read as external calibration evidence, not as the final persona realism score

## External Pairwise Sanity

- Script: `evals/run_external_pairwise_sanity.py`
- Report JSON: `evals/reports/external-pairwise-sanity-20260309-143014-a2eeaf8a.json`
- Report Markdown: `evals/reports/external-pairwise-sanity-20260309-143014-a2eeaf8a.md`

Purpose:

- compare a clearly stronger response against a clearly weaker response under the same external benchmark scene
- reduce the chance that single-answer judges hand out false greens to polite-but-bad or generic-but-not-catastrophic answers
- make the external calibration layer closer to pairwise human preference

Evaluator status:

- all pairwise checks passed
- swap-order stability passed for role, support, empathy, and continuity
- this report complements `external-judge-sanity` instead of replacing it

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
