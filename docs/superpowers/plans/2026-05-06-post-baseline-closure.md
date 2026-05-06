# Post-Baseline Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the selected post-baseline tails with minimal runtime additions, fail-closed policy gates, and one final readiness audit.

**Architecture:** Add a Python-callable transport adapter over `BackendAPI`, a runtime executor adapter over the existing sandbox runner, and static post-baseline closure policy helpers. The implementation preserves the existing LangGraph persona core, action-packet contract, digital-body truth, skills registry boundary, browser boundary, and sandbox phase-2 restrictions.

**Tech Stack:** Python 3, pytest, existing `BackendAPI` / `BackendSession`, existing sandbox runner, existing eval report format, no FastAPI/Flask/Uvicorn dependency.

---

## Tasks

- [x] Add failing tests for callable transport adapter, executor adapter, and closure policy/audit helpers.
- [x] Implement `amadeus_thread0.runtime.transport_adapter`.
- [x] Implement `amadeus_thread0.runtime.executor_adapter`.
- [x] Route `execute_workspace_command` through the executor adapter while preserving existing payload shape.
- [x] Implement `amadeus_thread0.runtime.post_baseline_closure`.
- [x] Implement `evals/run_executor_adapter_audit.py`.
- [x] Implement `evals/run_post_baseline_closure_audit.py`.
- [x] Run TTS presence timing audit enough times to prove closure.
- [x] Update engineering docs and `program.md`.
- [x] Run targeted pytest/audit validation.

## Validation Commands

```powershell
python -m pytest tests/test_transport_adapter.py tests/test_executor_adapter.py tests/test_post_baseline_closure.py -q
python -m pytest tests/test_executor_adapter_audit.py tests/test_post_baseline_closure_audit.py -q
python -m pytest tests/test_sandbox_execution_runtime.py tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py -q
python evals/run_tts_presence_timing_audit.py --run-tag post-baseline-closure-a
python evals/run_tts_presence_timing_audit.py --run-tag post-baseline-closure-b
python evals/run_tts_presence_timing_audit.py --run-tag post-baseline-closure-c
python evals/run_executor_adapter_audit.py --run-tag post-baseline-closure
python evals/run_chinese_surface_de_scaffold_audit.py --run-tag post-baseline-closure
python evals/run_post_baseline_closure_audit.py --run-tag final
```
