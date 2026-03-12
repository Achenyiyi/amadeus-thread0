# Thesis Figure Map

Updated: 2026-03-12

This file maps current experiment assets to future thesis tables and figures. The goal is to remove ambiguity when writing the experiment chapter later.

## Section A. System Overview

### Figure A1. Overall System Pipeline

Use content from:

- `amadeus_thread0/graph.py`
- `docs/THESIS_BACKEND_EXECUTION_PLAN.md`

Recommended caption:

> Overall backend pipeline of Amadeus-K, including task draft, persona alignment, worldline retrieval, claim attribution, memory guard, and multimodal orchestration.

Key blocks to show:

1. user input
2. state update
3. retrieve context
4. task draft
5. persona align
6. OOC / canon guard
7. claim attribution
8. final text / optional TTS

### Figure A2. Memory Architecture

Use content from:

- `amadeus_thread0/memory_store.py`
- `docs/EVAL_BASELINE.md`

Recommended caption:

> Hierarchical memory layout of Amadeus-K, including identity facts, shared events, relationship timeline, commitments, conflict repair, and source references.

## Section B. Baseline Performance

### Table B1. Official Baseline Summary

Use:

- `docs/EVAL_BASELINE.md`

Metrics to include:

1. `ooc_rate`
2. `canon_violation_rate`
3. `worldline_recall_at_k`
4. `commitment_fulfillment`
5. `relationship_continuity`
6. `citation_coverage`
7. `memory_guard_block_rate`
8. `bargein_recovery_rate`

Rows:

1. `regression_isolated`
2. `long_thread`
3. `experience_probe`
4. `thesis_probe`

## Section C. Ablation Study

### Table C1. Subsystem Ablation Matrix

Use:

- `evals/reports/ablation-matrix-20260306-224514-5c1a1c70.json`
- `docs/ABLATION_RESULTS.md`

Rows to include:

1. baseline
2. `persona_off`
3. `worldline_off`
4. `claim_attribution_off`
5. `memory_guard_off`

Columns:

1. `persona_probe_voice`
2. `worldline_recall_at_k`
3. `commitment_fulfillment`
4. `relationship_continuity`
5. `citation_coverage`
6. `memory_guard_block_rate`

### Figure C2. Thesis Probe Variance Bands

Use:

- `evals/reports/probe-variance-thesis_probe-20260307-024213-ee70482d.json`

Recommended chart:

- grouped bar chart with error bars

Series:

1. baseline
2. `persona_off`
3. `worldline_off`

Metrics:

1. `persona_probe_voice`
2. `worldline_recall_at_k`
3. `commitment_fulfillment`

Recommended caption:

> Repeated `thesis_probe` results across three runs. Persona ablation primarily affects role-voice fidelity, while worldline ablation primarily affects cross-thread recall and commitment grounding.

### Figure C3. Long-Thread Worldline Comparison

Use:

- `eval-report-20260309-120008-7784d487.json`
- `eval-report-20260307-010246-e2288121.json`

Recommended chart:

- side-by-side bars

Metrics:

1. `worldline_recall_at_k`
2. `commitment_fulfillment`
3. `relationship_continuity`

Recommended caption:

> Long-thread comparison between the full system and `worldline_off`, showing that worldline memory contributes beyond isolated probes.

### Table C2. Transfer Semantic Evidence Ablation

Use:

- `evals/reports/eval-report-20260312-202523-956ce7ef.json`
- `evals/reports/eval-report-20260312-202553-40d6d7ee.json`
- `docs/thesis_assets/transfer_ablation_summary.md`

Rows:

1. baseline
2. `semantic_evidence_off`

Columns:

1. `not_empty`
2. `transfer_probe_path`
3. `transfer_state_path`
4. `transfer_semantic_profile_path`
5. `transfer_evidence_path`
6. `failing_cases`

Recommended caption:

> Transfer-probe ablation showing that reusable semantic evidence materially improves cross-shell carryover of boundary, selfhood, and agency signals.

## Section D. Qualitative Case Study

### Table D1. Persona Side-by-Side Example

Use:

- thesis probe baseline report: `eval-report-20260307-022239-17048ce9.json`
- persona-off samples from repeated variance run:
  - `eval-report-20260307-023341-61e3f1c9.json`
  - `eval-report-20260307-023609-bbdd0f11.json`
  - `eval-report-20260307-023847-6da34d2c.json`

Show:

1. same user prompt
2. baseline answer
3. persona-off answer
4. short analysis of the difference

Recommended analysis angle:

- baseline uses direct companion cue and natural source phrasing
- persona-off stays correct but loses role-voice sharpness

### Table D2. Worldline Recall Side-by-Side Example

Use:

- repeated variance report for `worldline_off`
- long-thread failing case `long_thread-008`

Show:

1. setup turns
2. baseline answer
3. worldline-off answer
4. missed commitment / missed relationship signal

### Table D3. Transfer Semantic Snapshots

Use:

- `docs/thesis_assets/transfer_semantic_snapshots.md`
- `evals/reports/eval-report-20260312-202523-956ce7ef.md`

Show:

1. transferred actor
2. transferred counterpart
3. dominant semantic narrative
4. active narratives
5. `self_directedness / boundary_assertiveness / equality_guard`

Recommended analysis angle:

- show that the engine remains interpretable after shell transfer
- emphasize that `明日香 / 赫萝` extend the suite beyond restrained personas

## Section E. User Study

### Table E1. User Study Design

Use:

- `user_study/PROTOCOL.md`
- `user_study/README.md`

Columns:

1. participant count
2. conditions
3. task blocks
4. measured dimensions
5. statistical method

### Table E2. User Study Rating Summary

Use future outputs from:

- `user_study/analyze_results.py`
- `user_study/results/thesis_exports/thesis-user-study-condition-*.csv`
- `user_study/results/thesis_exports/thesis-user-study-paired-*.csv`

Rows:

1. role fidelity
2. continuity
3. trustworthiness
4. companionship
5. controllability
6. overall score

Columns:

1. condition A mean/std
2. condition B mean/std
3. paired delta
4. significance

Recommended note:

- use `--system-a-label` and `--system-b-label` to replace raw `A/B` labels with thesis-facing system names

### Figure E3. User Study Preference Plot

Use future outputs from:

- `user_study/results/thesis_exports/thesis-user-study-paired-*.csv`

Recommended chart:

- per-dimension paired slope plot or grouped box plot

### Table E4. User Study Open Feedback Summary

Use future outputs from:

- `user_study/results/summary-comment-top-*.csv`
- `user_study/results/thesis_exports/ch4-user-study-insert-*.md`

Show:

1. top comment keywords
2. representative issue types
3. relation to persona / worldline / trust dimensions

## Section F. Reliability and Safety

### Table F1. Backend Reliability Checks

Use:

- `backend-check-20260306-125431-c2eedd64.json`

Rows:

1. `emotion_profiles`
2. `tts_render_plan`
3. `tts_push_segments`
4. `pending_fragment_paths`

### Table F2. Memory Safety Evidence

Use:

- `docs/ABLATION_RESULTS.md`
- regression baseline reports
- memory-guard-off matrix row

Show:

1. baseline `memory_guard_block_rate`
2. memory-guard-off `memory_guard_block_rate`
3. one qualitative blocked-write example

## Writing Rule

When drafting the thesis, keep this order:

1. baseline first
2. ablation second
3. repeated probes third
4. qualitative examples fourth
5. user study fifth

That order keeps the chapter defensible: from stable engineering evidence, to subsystem effect, to human-facing interpretation.
