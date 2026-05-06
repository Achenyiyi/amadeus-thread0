# External Executor Harness Phase 1 Plan

## Goal

Make future executor harnesses visible as disabled, fail-closed adapter candidates without widening execution authority.

## Tasks

- Add `amadeus_thread0/runtime/executor_harness_registry.py`.
- Keep `sandbox_runner` as the only `runtime_enabled` harness.
- Normalize external harness results as result-only readback.
- Add unit tests and a registry audit.

## Validation

- `python -m pytest tests/test_executor_harness_registry.py tests/test_external_executor_harness_audit.py -q`
- `python evals/run_external_executor_harness_audit.py --run-tag phase1-dev`
