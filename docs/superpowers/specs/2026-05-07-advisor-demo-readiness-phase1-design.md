# Advisor Demo Readiness Phase 1 Design

## Purpose

Advisor Demo Readiness Phase 1 turns the current Technical Preview RC and Operator Console RC into a final reviewer-facing readiness gate.

The phase answers one narrow question:

Can an advisor, reviewer, or demo operator follow the documented reproduction and demo path without inventing missing instructions, while all blocked runtime-authority surfaces remain closed?

This is a package/readback/audit gate. It is not a live demo certificate and does not claim that a human advisor session has already been run.

## Scope

Implement `advisor_demo_readiness.v1` as a deterministic readback over:

- latest ready `operator_console_rc.v1` evidence;
- required advisor/demo docs;
- reproduction commands described in those docs;
- demo script scenario coverage;
- blocked authority inherited from Operator Console RC.

The ready status is `advisor_demo_readiness_phase1_ready`.

The blocked status is `advisor_demo_readiness_phase1_blocked`.

## Required Assets

The audit checks that the following repository assets exist:

- `docs/ADVISOR_REPRO_RUNBOOK.md`
- `docs/DEMO_SCRIPT.md`
- `docs/TECHNICAL_PREVIEW_CHECKLIST.md`
- `docs/FINAL_DELIVERY_MANIFEST.md`
- `docs/EVAL_BASELINE.md`
- `docs/ABLATION_RESULTS.md`
- `docs/FAILURE_TAXONOMY.md`
- `user_study/README.md`
- `user_study/PROTOCOL.md`
- `user_study/FACILITATOR_SCRIPT.md`
- `user_study/EXECUTION_CHECKLIST.md`
- `user_study/CONSENT_TEMPLATE.md`

## Required Command Coverage

The docs must expose the current reproduction path:

- `python evals\run_technical_preview_rc_phase1_audit.py`
- `python evals\run_operator_console_rc_phase1_audit.py`
- `python evals\run_preserved_baselines_audit.py`
- `python evals\run_langsmith_evals.py --local-only`
- `python evals\run_probe_variance.py`

The audit reports missing command coverage separately from missing files.

## Demo Script Coverage

The demo script must cover the current fixed sequence:

1. role/persona consistency;
2. worldline commitment;
3. conflict repair / relationship evolution;
4. source-traceable retrieval;
5. interruption recovery;
6. memory guard interception.

The audit checks for the existing scenario headings and expected evidence terms rather than attempting to run an interactive demo.

## Authority Boundary

Advisor readiness must fail closed if Operator Console RC shows any widened authority:

- live capture enabled;
- external executor auto-enabled;
- dynamic skill registry auto-write enabled;
- multimodal model auto-call enabled;
- frontend semantics ownership;
- persona-core mutation;
- widened memory-write policy;
- HTTP server semantics ownership.

The phase also declares:

- `live_demo_observed=false`
- `manual_demo_required=true`
- `readiness_scope=package_ready_not_live_demo_certification`

## Outputs

The runtime helper emits:

- `schema`
- `overall_status`
- `readiness_status`
- `readiness_scope`
- `summary`
- `operator_console_rc_ref`
- `asset_inventory`
- `command_inventory`
- `demo_script_inventory`
- `authority_boundary`
- `next_actions`
- `failure_reasons`

The audit runner writes JSON and Markdown reports under:

- `evals/reports/advisor-demo-readiness-phase1-audit-*.json`
- `evals/reports/advisor-demo-readiness-phase1-audit-*.md`

## Non-Goals

This phase does not:

- run a live advisor/demo conversation;
- open live microphone, camera, or background screen capture;
- call multimodal model APIs;
- auto-write the dynamic skill registry;
- enable external executor harnesses beyond the preserved sandbox;
- mutate persona core;
- widen memory-write authority;
- add frontend-owned backend semantics;
- add a new HTTP server or streaming runtime;
- execute external mutations.

