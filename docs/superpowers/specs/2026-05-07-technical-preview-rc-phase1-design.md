# Technical Preview RC Phase 1 Design

## Goal

Establish a release-candidate readiness layer for the current backend-first technical preview after the post-unlock readback lanes have closed and `runtime_status_dashboard.NEXT_SPECS` is empty.

## Current Context

`main` has closed the rolling backend/readback phases through Dynamic Skill Candidate Runtime Phase 1. The runtime status dashboard now reports no current next specs, while preserving blocked authority for live capture, external executor auto-enablement, automatic dynamic skill registry writes, and multimodal model auto-calls.

The project therefore needs a release-candidate gate, not another authority unlock. The gate should make the current state reproducible and easy to cite without changing persona, memory, body, skill, browser, sandbox, frontend, HTTP, or multimodal semantics.

## Scope

Technical Preview RC Phase 1 adds:

- a pure `technical_preview_rc.v1` readiness readback module;
- an audit runner that composes latest existing evidence reports into one RC report;
- tests proving the RC gate fails closed when evidence is missing, `NEXT_SPECS` is not empty, or blocked authority widens;
- documentation updates for the delivery manifest, technical preview checklist, advisor runbook, backend handoff, project structure, and ledger.

## Out Of Scope

This phase must not add:

- live microphone, camera, or background screen capture;
- multimodal model API execution;
- automatic skill registry writes;
- frontend-owned backend semantics;
- external executor harness enablement beyond the preserved sandbox runner;
- persona-core mutation;
- autobiographical memory writes;
- new HTTP server ownership or streaming transport;
- new demo UI.

## Architecture

`amadeus_thread0.runtime.technical_preview_rc` is a read-only composition layer. It accepts existing audit/dashboard dictionaries and returns `technical_preview_rc.v1` with:

- evidence checks for preserved baselines, runtime dashboard, runtime productization phase 3, HTTP transport, approved artifact multimodal runtime, Chinese semantic naturalness, and dynamic skill candidate runtime;
- a `NEXT_SPECS == []` check;
- authority-boundary booleans derived from the runtime dashboard lanes;
- compact operator-facing status text.

`evals/run_technical_preview_rc_phase1_audit.py` loads the latest ready reports from `evals/reports`, builds a fresh runtime status dashboard from preserved/productization inputs, evaluates the RC gate, and writes JSON/Markdown reports. Missing reports are treated as evidence gaps, not hidden runtime changes.

## Success Criteria

- `tests/test_technical_preview_rc.py` proves the pure RC readback behavior.
- `tests/test_technical_preview_rc_audit.py` proves the audit runner loads evidence, fails honestly on missing reports, and renders authority boundaries.
- `python evals/run_technical_preview_rc_phase1_audit.py --run-tag rc-phase1-dev` emits `technical_preview_rc_phase1_ready` when current evidence is present.
- Existing preserved/productization tests remain green.
- Documentation names RC Phase 1 as readback/evidence-only.

## Risks

- Historical report absence can block the RC audit. This is acceptable; the correct fix is to generate or restore the missing evidence report, not to pretend readiness.
- Existing historical plans may still mention older next specs. The runtime dashboard and current-state docs are authoritative for present RC status.
- The RC gate must not be used as permission to unlock live capture, model calls, registry writes, or external harnesses.
