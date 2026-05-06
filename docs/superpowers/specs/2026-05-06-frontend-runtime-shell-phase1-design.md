# Frontend Runtime Shell Phase 1 Design

## Purpose

Keep the frontend as a `backend.v1` contract consumer with buildable React/Vite runtime shell assets.

## Contract

- The frontend renders copied `backend.v1` envelopes and mock transport fixtures.
- It does not define memory, body, autonomy, or graph semantics.
- Future live transport must delegate semantics to `BackendAPI` / `BackendSession`.

## Explicit Blocks

- frontend-owned backend semantics
- alternate memory or body truth
- UI-driven backend architecture churn

## Completion Gate

`python evals/run_frontend_runtime_shell_audit.py` must report `frontend_runtime_shell_phase1_ready`.
