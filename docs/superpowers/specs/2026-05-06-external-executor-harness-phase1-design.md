# External Executor Harness Phase 1 Design

## Purpose

Register future external executor harness families as fail-closed metadata while preserving the sandbox runner as the only enabled executor.

## Harness Boundary

External harnesses are result-only, approval-gated, disabled by default, and have no persona-memory ownership.

Tracked disabled families:

- `deep_agents`
- `codex_harness`
- `claude_harness`
- `openclaw_harness`

## Explicit Blocks

- arbitrary host shell
- package install
- networked execution without policy
- git mutation without packet approval
- persona memory writes by harness

## Completion Gate

`python evals/run_external_executor_harness_audit.py` must report `external_executor_harness_phase1_ready`.
