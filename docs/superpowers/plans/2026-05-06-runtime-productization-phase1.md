# Runtime Productization Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the closed post-unlock backend into an operator-readable runtime productization surface without widening execution, memory, persona, browser, skill, frontend, or external harness authority.

**Architecture:** Add one pure read-model module under `amadeus_thread0/runtime/` that composes existing backend envelopes, post-baseline closure status, post-unlock lane readiness, preserved baseline status, and current-turn operator signals. Backend API/session/transport/CLI surfaces consume that read model; audits verify the shape and baseline preservation. This phase is readback-only.

**Tech Stack:** Python 3, LangGraph backend package, existing `BackendAPI` / `BackendSession`, pytest, local eval audit scripts, React/Vite frontend build as validation only.

---

## File Structure

- Create `amadeus_thread0/runtime/runtime_productization.py`
  - Pure read-model helpers for `Runtime Productization Phase 1`.
  - No graph execution, no memory writes, no tool execution, no browser execution.
- Modify `amadeus_thread0/runtime/backend_api.py`
  - Add `runtime_productization()` envelope.
  - Attach `operator_readback` to `assistant_turn` and `event_round`.
- Modify `amadeus_thread0/runtime/backend_session.py`
  - Add `operator_readback_view()` for CLI/frontend consumers that already hold a session.
- Modify `amadeus_thread0/runtime/transport_adapter.py`
  - Add `GET /api/runtime-productization`.
- Modify `amadeus_thread0/utils/cli_views.py`
  - Include compact operator readback in evolution summaries and compact summary lines.
- Create `evals/run_runtime_productization_audit.py`
  - Aggregates pure contract checks and report-backed preserved baselines.
- Create `tests/test_runtime_productization.py`
  - TDD coverage for pure read model.
- Modify `tests/test_backend_api.py`
  - TDD coverage for API envelope and turn payload attachment.
- Modify `tests/test_backend_session.py`
  - TDD coverage for session readback view.
- Modify `tests/test_transport_adapter.py`
  - TDD coverage for transport route.
- Modify `tests/test_cli_views.py`
  - TDD coverage for compact CLI line.
- Create `tests/test_runtime_productization_audit.py`
  - TDD coverage for audit aggregation and markdown.
- Modify `evals/run_preserved_baselines_audit.py`
  - Include `runtime_productization_phase1_ready` once the phase audit exists.
- Modify `tests/test_preserved_baselines_audit.py`
  - Assert the new category is counted.
- Modify `AGENTS.md`
  - Record `runtime_productization_phase1_ready` as a bounded readback/productization baseline.
- Modify `docs/engineering/PROJECT_STRUCTURE.md`
  - Document `runtime_productization.py` and audit entrypoint.
- Modify `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
  - Record productization readback contract.
- Modify `program.md`
  - Add run ledger entry.

### Task 1: Runtime Productization Read Model

**Files:**
- Create: `amadeus_thread0/runtime/runtime_productization.py`
- Test: `tests/test_runtime_productization.py`

- [x] **Step 1: Write failing tests**

Create tests asserting:

```python
from amadeus_thread0.runtime.runtime_productization import (
    RUNTIME_PRODUCTIZATION_READINESS,
    build_runtime_productization_readback,
    compact_operator_readback_line,
    evaluate_runtime_productization_contract,
)


def test_readback_reports_ready_lanes_without_widening_authority():
    readback = build_runtime_productization_readback(
        post_baseline_status={
            "overall_status": "passed",
            "readiness_status": "post_baseline_closure_ready",
            "items": {
                "multimodal_input_capture": {"status": "implemented_ready", "runtime_available": True},
                "dynamic_skill_generation": {"status": "implemented_ready", "runtime_available": False},
                "external_executor_harnesses": {"status": "implemented_ready", "runtime_available": False},
                "frontend_runtime_shell": {"status": "implemented_ready", "runtime_available": True},
            },
        },
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        current_turn={
            "autonomy_mode": "assist",
            "action_packet_count": 2,
            "digital_body_consequence_kind": "sandbox_execution_completed",
            "procedural_recovery": {"recovery_kind": "adjust_bounded_command"},
        },
    )

    assert readback["readiness_status"] == RUNTIME_PRODUCTIZATION_READINESS
    assert readback["authority_boundary"]["external_mutation_requires_approval"] is True
    assert readback["authority_boundary"]["persona_core_mutation_allowed"] is False
    assert readback["lanes"]["dynamic_skill_generation"]["runtime_available"] is False
    assert readback["operator_snapshot"]["action_packet_count"] == 2
    assert readback["operator_snapshot"]["procedural_recovery_kind"] == "adjust_bounded_command"


def test_contract_fails_when_preserved_baselines_are_not_ready():
    readback = build_runtime_productization_readback(
        post_baseline_status={"overall_status": "passed", "readiness_status": "post_baseline_closure_ready", "items": {}},
        preserved_baselines={"overall_status": "failed", "readiness_status": "preserved_baselines_regressed"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
    )

    contract = evaluate_runtime_productization_contract(readback)

    assert contract["overall_status"] == "failed"
    assert "preserved_baselines_ready" in contract["failure_reasons"][0]


def test_compact_operator_readback_line_is_short_and_actionable():
    readback = build_runtime_productization_readback(
        post_baseline_status={"overall_status": "passed", "readiness_status": "post_baseline_closure_ready", "items": {}},
        preserved_baselines={"overall_status": "passed", "readiness_status": "preserved_baselines_ready"},
        post_unlock_roadmap={"overall_status": "passed", "readiness_status": "post_unlock_roadmap_ready"},
        current_turn={"autonomy_mode": "assist", "action_packet_count": 1, "digital_body_consequence_kind": "browser_takeover_requested"},
    )

    line = compact_operator_readback_line(readback)

    assert "productization=runtime_productization_phase1_ready" in line
    assert "autonomy=assist" in line
    assert "packets=1" in line
    assert "bodyfx=browser_takeover_requested" in line
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_runtime_productization.py -q`

Expected: FAIL because `amadeus_thread0.runtime.runtime_productization` does not exist.

- [x] **Step 3: Implement minimal read model**

Create `runtime_productization.py` with:

```python
from __future__ import annotations

from typing import Any

RUNTIME_PRODUCTIZATION_READINESS = "runtime_productization_phase1_ready"

def build_runtime_productization_readback(...): ...
def evaluate_runtime_productization_contract(...): ...
def compact_operator_readback_line(...): ...
```

The implementation must:

- copy only read-model inputs
- normalize lane rows from post-baseline status items
- expose `authority_boundary` booleans:
  - `external_mutation_requires_approval=True`
  - `memory_write_follows_existing_policy=True`
  - `persona_core_mutation_allowed=False`
  - `frontend_semantics_owner=False`
  - `dynamic_registry_write_auto_allowed=False`
  - `external_harness_runtime_auto_enabled=False`
- derive `operator_snapshot` from current-turn fields
- mark ready only when post-baseline, preserved baselines, and post-unlock roadmap are all ready

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_runtime_productization.py -q`

Expected: PASS.

### Task 2: Backend API, Session, And Transport Readback

**Files:**
- Modify: `amadeus_thread0/runtime/backend_api.py`
- Modify: `amadeus_thread0/runtime/backend_session.py`
- Modify: `amadeus_thread0/runtime/transport_adapter.py`
- Test: `tests/test_backend_api.py`
- Test: `tests/test_backend_session.py`
- Test: `tests/test_transport_adapter.py`

- [x] **Step 1: Write failing tests**

Add tests asserting:

- `BackendAPI.runtime_productization()` returns a `backend.v1` envelope with `readiness_status=runtime_productization_phase1_ready`.
- `build_turn_response()` and `build_event_round_response()` include `operator_readback`.
- `BackendSession.operator_readback_view()` returns the same readback shape.
- `GET /api/runtime-productization` delegates to the backend API instead of rebuilding schema in the adapter.

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_backend_api.py -k runtime_productization -q
python -m pytest tests/test_backend_session.py -k operator_readback -q
python -m pytest tests/test_transport_adapter.py -k runtime_productization -q
```

Expected: FAIL because methods/routes are missing.

- [x] **Step 3: Implement minimal integration**

Add imports from `runtime_productization.py`.

Implement:

- `BackendAPI._runtime_productization_payload(...)`
- `BackendAPI.runtime_productization()`
- include `operator_readback` in `assistant_turn` and `event_round`
- `BackendSession.operator_readback_view()`
- transport route `"/api/runtime-productization": ("GET", _read_route("runtime_productization"))`

- [x] **Step 4: Run tests to verify they pass**

Run the three focused commands again.

Expected: PASS.

### Task 3: CLI Summary Productization Line

**Files:**
- Modify: `amadeus_thread0/utils/cli_views.py`
- Test: `tests/test_cli_views.py`

- [x] **Step 1: Write failing test**

Add a test that passes `operator_readback` into `build_evolution_cli_summary(...)` and asserts `build_evolution_summary_line(...)` includes:

- `productization=runtime_productization_phase1_ready`
- `runtime=operator_readback`
- the current autonomy/body compact fields already present in the readback

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_views.py -k operator_readback -q`

Expected: FAIL because the summary ignores `operator_readback`.

- [x] **Step 3: Implement minimal CLI summary support**

Add an optional `operator_readback` parameter to `build_evolution_cli_summary`, persist it under `summary["operator_readback"]`, and make `build_evolution_summary_line` append `compact_operator_readback_line(...)`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_views.py -k operator_readback -q`

Expected: PASS.

### Task 4: Runtime Productization Audit

**Files:**
- Create: `evals/run_runtime_productization_audit.py`
- Test: `tests/test_runtime_productization_audit.py`
- Modify: `evals/run_preserved_baselines_audit.py`
- Modify: `tests/test_preserved_baselines_audit.py`

- [x] **Step 1: Write failing tests**

Add tests that:

- evaluate a ready audit from synthetic post-baseline, preserved-baselines, and post-unlock roadmap statuses
- render markdown with `runtime_productization_phase1_ready`
- ensure preserved-baselines audit includes `runtime_productization_phase1`

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_runtime_productization_audit.py -q
python -m pytest tests/test_preserved_baselines_audit.py -k runtime_productization -q
```

Expected: FAIL because the audit file and preserved-baseline spec are missing.

- [x] **Step 3: Implement audit**

Create `evals/run_runtime_productization_audit.py`:

- import `build_runtime_productization_readback`, `evaluate_runtime_productization_contract`
- load latest reports:
  - `post-baseline-closure-audit-*.json`
  - `preserved-baselines-audit-*.json`
  - `post-unlock-roadmap-audit-*.json`
- produce report fields:
  - `overall_status`
  - `readiness_status`
  - `operator_readback`
  - `contract`
  - `checks`
- render markdown table

Modify `evals/run_preserved_baselines_audit.py` to include the new audit prefix and readiness.

- [x] **Step 4: Run tests to verify they pass**

Run the two focused commands again.

Expected: PASS.

### Task 5: Documentation And Ledger

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/engineering/PROJECT_STRUCTURE.md`
- Modify: `docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md`
- Modify: `program.md`

- [x] **Step 1: Update docs**

Record:

- `runtime_productization_phase1_ready` as a readback/productization baseline
- no new runtime authority
- no second schema or frontend-owned backend semantics
- `runtime_productization.py` ownership
- audit entrypoint

- [x] **Step 2: Scan docs**

Run:

```powershell
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" docs\superpowers\plans\2026-05-06-runtime-productization-phase1.md AGENTS.md docs\engineering\PROJECT_STRUCTURE.md docs\engineering\AMADEUS_ARCHITECTURE_DECISIONS.md
```

Expected: no matches.

### Task 6: Final Verification And Merge

**Files:**
- All changed files

- [x] **Step 1: Run focused tests**

```powershell
python -m pytest tests/test_runtime_productization.py tests/test_backend_api.py tests/test_backend_session.py tests/test_transport_adapter.py tests/test_cli_views.py tests/test_runtime_productization_audit.py tests/test_preserved_baselines_audit.py -q
```

Expected: PASS.

- [x] **Step 2: Run required contract tests**

```powershell
python -m pytest tests/test_post_baseline_closure.py tests/test_post_baseline_closure_audit.py tests/test_preserved_baselines_audit.py -q
python -m pytest tests/test_backend_api.py tests/test_backend_session.py tests/test_cli_views.py tests/test_tool_approval_policy.py -q
```

Expected: PASS.

- [x] **Step 3: Run audits**

```powershell
python evals/run_post_baseline_closure_audit.py --run-tag runtime-productization-phase1
python evals/run_post_unlock_roadmap_audit.py --reports-dir evals/reports
python evals/run_runtime_productization_audit.py --reports-dir evals/reports
python evals/run_preserved_baselines_audit.py --reports-dir evals/reports
```

Expected:

- `post_baseline_closure_ready`
- `post_unlock_roadmap_ready`
- `runtime_productization_phase1_ready`
- `preserved_baselines_ready`

- [x] **Step 4: Compile and graph build**

```powershell
python -m py_compile amadeus_thread0/agent.py amadeus_thread0/graph.py amadeus_thread0/runtime/runtime_productization.py evals/run_runtime_productization_audit.py
python -c "from amadeus_thread0.agent import agent; print(type(agent).__name__)"
```

Expected: compile passes and graph build prints `CompiledStateGraph`.

- [x] **Step 5: Frontend build validation**

```powershell
npm --prefix frontend run build
```

Expected: PASS.

- [x] **Step 6: Diff checks**

```powershell
git diff --check
rg -n -e "T[B]D" -e "T[O]DO" -e "f[i]ll in" -e "implement la[t]er" amadeus_thread0/runtime/runtime_productization.py evals/run_runtime_productization_audit.py tests/test_runtime_productization.py tests/test_runtime_productization_audit.py docs/superpowers/plans/2026-05-06-runtime-productization-phase1.md
```

Expected: no diff errors except Windows LF-to-CRLF warnings; no placeholder matches.

- [x] **Step 7: Commit and merge**

```powershell
git status --short
git add AGENTS.md amadeus_thread0/runtime/runtime_productization.py amadeus_thread0/runtime/backend_api.py amadeus_thread0/runtime/backend_session.py amadeus_thread0/runtime/transport_adapter.py amadeus_thread0/utils/cli_views.py evals/run_runtime_productization_audit.py evals/run_preserved_baselines_audit.py tests/test_runtime_productization.py tests/test_backend_api.py tests/test_backend_session.py tests/test_transport_adapter.py tests/test_cli_views.py tests/test_runtime_productization_audit.py tests/test_preserved_baselines_audit.py docs/engineering/PROJECT_STRUCTURE.md docs/engineering/AMADEUS_ARCHITECTURE_DECISIONS.md docs/superpowers/plans/2026-05-06-runtime-productization-phase1.md program.md
git commit -m "feat: add runtime productization readback"
git -C E:\桌面\amadeus-thread0 merge --ff-only codex/runtime-productization-phase1
```

Expected: commit succeeds and local `main` fast-forwards.

## Self-Review

- Spec coverage: The plan covers read model, backend/session/transport integration, CLI readback, audit, preserved baseline inclusion, docs, verification, and merge.
- Placeholder scan: No placeholder-only implementation instructions are present; code-bearing tasks identify concrete functions and tests.
- Type consistency: The plan consistently uses `operator_readback`, `runtime_productization_phase1_ready`, `Runtime Productization Phase 1`, and the same three audit dependencies.
